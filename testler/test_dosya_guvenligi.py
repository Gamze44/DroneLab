"""
Kötü amaçlı dosyalara karşı testler: zip bombası (DOCX/3MF), OBJ'deki ağ yolu
(NTLM sızıntısı), DXF blok çoğaltması ve şartname sayfa sınırının metinden önce denetimi.
"""

import io
from pathlib import Path
import time
import zipfile

import docx
import ezdxf
from fastapi.testclient import TestClient
from pypdf import PdfWriter
import pytest
import trimesh

from arayuz.sunucu import sunucu_olustur
from cekirdek.arsiv_denetimi import ArsivDenetleyici
from cekirdek.hatalar import DosyaOkumaHatasi, GecersizDegerHatasi
from sasi.okuyucular.ag_okuyucu import AgOkuyucu, DisDosyaEngelleyici
from sasi.okuyucular.dxf_okuyucu import EN_FAZLA_ACIK_PARCA, EN_FAZLA_DXF_OGESI, DxfOkuyucu
from sartname.metin_cikarici import SartnameMetinCikarici

BAYT_BIR_MB = 1024 * 1024
# İçinde yalnızca sıfır olan 2 MB'lık üye ~2 KB'a sıkışır (oran ~1000; sınır 100).
BOMBA_UYE_BOYUTU = 2 * BAYT_BIR_MB


def _zip_yaz(yol: Path, uyeler: dict[str, bytes], sikistirma: int = zipfile.ZIP_DEFLATED) -> Path:
    with zipfile.ZipFile(yol, "w", sikistirma) as arsiv:
        for ad, icerik in uyeler.items():
            arsiv.writestr(ad, icerik)
    return yol


# ---------- Arşiv denetimi ----------


def test_normal_word_belgesi_gecer(tmp_path: Path) -> None:
    belge = docx.Document()
    belge.add_paragraph("Kalkış ağırlığı en çok 1000 g. " * 200)
    yol = tmp_path / "normal.docx"
    belge.save(yol)
    ArsivDenetleyici().denetle(yol)  # hata fırlatmamalı


def test_yuksek_oranli_uye_reddedilir(tmp_path: Path) -> None:
    yol = _zip_yaz(tmp_path / "bomba.docx", {"word/document.xml": b"\0" * BOMBA_UYE_BOYUTU})
    with pytest.raises(DosyaOkumaHatasi, match="kat sıkıştırılmış"):
        ArsivDenetleyici().denetle(yol)


def test_acik_boyut_siniri(tmp_path: Path) -> None:
    yol = _zip_yaz(tmp_path / "buyuk.3mf", {"a.bin": b"\1" * BOMBA_UYE_BOYUTU}, zipfile.ZIP_STORED)
    with pytest.raises(DosyaOkumaHatasi, match="açılmış hali"):
        ArsivDenetleyici(en_buyuk_acik_mb=1).denetle(yol)


def test_uye_sayisi_siniri(tmp_path: Path) -> None:
    yol = _zip_yaz(tmp_path / "cok.docx", {f"{i}.xml": b"<a/>" for i in range(5)})
    with pytest.raises(DosyaOkumaHatasi, match="iç dosya var"):
        ArsivDenetleyici(en_fazla_uye=3).denetle(yol)


def test_zip_olmayan_dosya_turkce_hata(tmp_path: Path) -> None:
    yol = tmp_path / "sahte.docx"
    yol.write_bytes(b"bu bir zip degil")
    with pytest.raises(DosyaOkumaHatasi, match="bozuk"):
        ArsivDenetleyici().denetle(yol)


def test_bomba_3mf_acilmadan_reddedilir(tmp_path: Path) -> None:
    yol = _zip_yaz(tmp_path / "bomba.3mf", {"3D/3dmodel.model": b"\0" * BOMBA_UYE_BOYUTU})
    with pytest.raises(DosyaOkumaHatasi, match="olağan dışı"):
        AgOkuyucu().oku(yol)


def test_bomba_docx_yuklenemez(tmp_path: Path) -> None:
    istemci = TestClient(sunucu_olustur(tmp_path / "veri", kur_getirici=lambda: b""))
    bomba = _zip_yaz(tmp_path / "bomba.docx", {"word/document.xml": b"\0" * BOMBA_UYE_BOYUTU}).read_bytes()
    yanit = istemci.post("/api/sartnameler", files={"dosya": ("bomba.docx", bomba)}, data={"ad": "x"})
    assert yanit.status_code == 400
    assert "olağan dışı" in yanit.json()["hata"]
    assert istemci.get("/api/sartnameler").json() == []


# ---------- OBJ dış dosya (NTLM) ----------


def test_dis_dosya_engelleyici_dosya_sistemine_dokunmaz() -> None:
    engel = DisDosyaEngelleyici()
    with pytest.raises(FileNotFoundError):
        engel.get(r"\\203.0.113.7\paylasim\a.mtl")
    assert engel.keys() == [] and engel.namespaced("x") is engel


def test_obj_mtllib_ag_yolu_acilmaz(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # trimesh kendi çözücüsünü kullansaydı mtllib yolunu FilePathResolver ile açmaya çalışırdı.
    denemeler: list[str] = []

    def kaydet(self, ad: str) -> bytes:
        denemeler.append(ad)
        raise FileNotFoundError(ad)

    monkeypatch.setattr(trimesh.resolvers.FilePathResolver, "get", kaydet)
    (tmp_path / "yerel.mtl").write_text("newmtl a\nKd 1 0 0\n")
    yol = tmp_path / "sasi.obj"
    yol.write_text(
        "mtllib \\\\203.0.113.7\\paylasim\\a.mtl\nmtllib yerel.mtl\n"
        "v 0 0 0\nv 1 0 0\nv 0 1 0\nv 0 0 1\nf 1 2 3\nf 1 2 4\nf 1 3 4\nf 2 3 4\n"
    )
    g = AgOkuyucu().oku(yol)
    assert g.ucgen_sayisi == 4
    assert denemeler == []


# ---------- DXF çoğaltma ve uç durumlar ----------


def test_ic_ice_blok_cogaltmasi_erken_durdurulur(tmp_path: Path) -> None:
    belge = ezdxf.new()
    onceki = belge.blocks.new("B0")
    for i in range(10):
        onceki.add_line((i, 0), (i, 1))
    for seviye in range(1, 6):  # 10^6 çizgiye açılır
        blok = belge.blocks.new(f"B{seviye}")
        for i in range(10):
            blok.add_blockref(f"B{seviye - 1}", (i * 20, 0))
        onceki = blok
    belge.modelspace().add_blockref("B5", (0, 0))
    yol = tmp_path / "cogaltma.dxf"
    belge.saveas(yol)

    baslangic = time.perf_counter()
    with pytest.raises(DosyaOkumaHatasi, match=str(EN_FAZLA_DXF_OGESI)):
        DxfOkuyucu().oku(yol)
    assert time.perf_counter() - baslangic < 30


def test_cok_fazla_acik_parca_reddedilir(tmp_path: Path) -> None:
    belge = ezdxf.new()
    msp = belge.modelspace()
    for i in range(EN_FAZLA_ACIK_PARCA + 1):
        msp.add_line((i * 3, 0), (i * 3 + 1, 0))
    yol = tmp_path / "parcali.dxf"
    belge.saveas(yol)
    with pytest.raises(DosyaOkumaHatasi, match="açık çizgi parçası"):
        DxfOkuyucu().oku(yol)


def test_boyutsuz_cizim_turkce_hata(tmp_path: Path) -> None:
    belge = ezdxf.new()
    belge.modelspace().add_lwpolyline([(5, 5), (5, 5), (5, 5)], close=True)
    yol = tmp_path / "nokta.dxf"
    belge.saveas(yol)
    with pytest.raises(DosyaOkumaHatasi):
        DxfOkuyucu().oku(yol)


# ---------- Sayfa sınırı metinden önce ----------


def _pdf(sayfa_sayisi: int) -> bytes:
    yazici = PdfWriter()
    for _ in range(sayfa_sayisi):
        yazici.add_blank_page(width=612, height=792)
    tampon = io.BytesIO()
    yazici.write(tampon)
    return tampon.getvalue()


def test_sayfa_siniri_metin_cikarmadan_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def cagrilmamali(self, yol: Path) -> str:
        raise AssertionError("sınırı aşan belgeden metin çıkarılmamalı")

    monkeypatch.setattr(SartnameMetinCikarici, "cikar", cagrilmamali)
    istemci = TestClient(sunucu_olustur(tmp_path / "veri", kur_getirici=lambda: b""))
    yanit = istemci.post("/api/sartnameler", files={"dosya": ("uzun.pdf", _pdf(51))}, data={"ad": "x"})
    assert yanit.status_code == 400
    assert "51 sayfa" in yanit.json()["hata"]


def test_bozuk_pdf_yine_anlasilir_hata(tmp_path: Path) -> None:
    istemci = TestClient(sunucu_olustur(tmp_path / "veri", kur_getirici=lambda: b""))
    yanit = istemci.post("/api/sartnameler", files={"dosya": ("b.pdf", b"%PDF-1.4 bozuk")}, data={"ad": "x"})
    assert yanit.status_code == 400
    assert "okunamadı" in yanit.json()["hata"]


def test_sayfa_kaydi_olmayan_word_tahminle_denetlenir(tmp_path: Path) -> None:
    from sartname.sayfa_sayisi import SayfaSiniriDenetleyici

    yol = _zip_yaz(tmp_path / "kayitsiz.docx", {"word/document.xml": b"<a/>"})
    denetleyici = SayfaSiniriDenetleyici(en_fazla=2)
    assert denetleyici.on_denetle(yol) is None
    with pytest.raises(GecersizDegerHatasi, match="tahmini"):
        denetleyici.tahmini_denetle("kelime " * 5000)
