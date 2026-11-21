"""Şartname: belge okuma, madde doğrulama, Gemini ile çıkarım (sahte), kütüphane ve uyum raporu.

Gerçek Gemini isteği yapılmaz. Örnek PDF ve Word belgeleri test içinde üretilir.
"""

from pathlib import Path

import docx
from fastapi.testclient import TestClient
import pytest

from arastirma.saglayici import ArastirmaSaglayicisi
from arayuz.sunucu import sunucu_olustur
from cekirdek.hatalar import DesteklenmeyenDosyaHatasi, DosyaOkumaHatasi, GecersizDegerHatasi
from cekirdek.ayarlar import ANAHTAR_ORTAM_DEGISKENLERI, EN_FAZLA_SARTNAME_SAYFASI
from sartname.sayfa_sayisi import SayfaSayisi
from sartname.cikarim import MaddeDonusturucu
from sartname.metin_cikarici import SartnameMetinCikarici
from sartname.modeller import Buyukluk, Madde, SinirTuru

SAHTE_ANAHTAR = "AIzaSahteTestAnahtari_1234567890abcdef"


def basit_pdf(yol: Path, satirlar: list[str]) -> Path:
    """Tek sayfalı, metin içeren en küçük PDF'i elle yazar (yalnızca ASCII)."""
    akis = "BT /F1 12 Tf 72 720 Td 14 TL " + " ".join(f"({s}) Tj T*" for s in satirlar) + " ET"
    nesneler = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(akis)} >>\nstream\n{akis}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    govde, konumlar = "%PDF-1.4\n", []
    for i, n in enumerate(nesneler, start=1):
        konumlar.append(len(govde))
        govde += f"{i} 0 obj\n{n}\nendobj\n"
    xref = len(govde)
    govde += f"xref\n0 {len(nesneler) + 1}\n0000000000 65535 f \n" + "".join(f"{k:010d} 00000 n \n" for k in konumlar)
    govde += f"trailer\n<< /Size {len(nesneler) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    yol.write_bytes(govde.encode("latin-1"))
    return yol


def bos_pdf(yol: Path) -> Path:
    """Metni olmayan (taranmış belge gibi) PDF."""
    from pypdf import PdfWriter

    yazici = PdfWriter()
    yazici.add_blank_page(width=612, height=792)
    with yol.open("wb") as f:
        yazici.write(f)
    return yol


def word_belgesi(yol: Path) -> Path:
    belge = docx.Document()
    belge.add_paragraph("4.2 Hava aracının kalkış ağırlığı en fazla 2 kg olmalıdır.")
    tablo = belge.add_table(rows=1, cols=2)
    tablo.rows[0].cells[0].text = "Pil"
    tablo.rows[0].cells[1].text = "En fazla 4S"
    belge.save(str(yol))
    return yol


def cok_sayfali_pdf(yol: Path, sayfa: int) -> Path:
    """Verilen sayıda boş sayfası olan PDF."""
    from pypdf import PdfWriter

    yazici = PdfWriter()
    for _ in range(sayfa):
        yazici.add_blank_page(width=612, height=792)
    with yol.open("wb") as f:
        yazici.write(f)
    return yol


def word_sayfali(yol: Path, kelime: int, pages: int | None) -> Path:
    """
    Word belgesi üretir. pages verilirse docProps/app.xml'deki "Pages" o değer yapılır;
    None ise "Pages" alanı silinir (Word dışı araçların ürettiği dosyalar gibi).
    """
    import re
    import zipfile

    gecici = yol.with_suffix(".gecici.docx")
    belge = docx.Document()
    belge.add_paragraph(" ".join(["kelime"] * kelime))
    belge.save(str(gecici))
    with zipfile.ZipFile(gecici) as kaynak, zipfile.ZipFile(yol, "w", zipfile.ZIP_DEFLATED) as hedef:
        for oge in kaynak.infolist():
            veri = kaynak.read(oge.filename)
            if oge.filename == "docProps/app.xml":
                metin = veri.decode("utf-8")
                yeni = f"<Pages>{pages}</Pages>" if pages is not None else ""
                veri = re.sub(r"<Pages>\d+</Pages>", yeni, metin).encode("utf-8")
            hedef.writestr(oge, veri)
    gecici.unlink()
    return yol


# ---------- Metin çıkarma ----------


def test_word_paragraf_ve_tablo(tmp_path: Path) -> None:
    metin = SartnameMetinCikarici().cikar(word_belgesi(tmp_path / "s.docx"))
    assert "en fazla 2 kg" in metin and "Pil | En fazla 4S" in metin


def test_pdf_sayfa_isaretli(tmp_path: Path) -> None:
    metin = SartnameMetinCikarici().cikar(basit_pdf(tmp_path / "s.pdf", ["Madde 3.1 Agirlik en fazla 2000 g"]))
    assert metin.startswith("[Sayfa 1]") and "Agirlik en fazla 2000 g" in metin


def test_taranmis_pdf_bos_metin_bozuk_dosya_hata(tmp_path: Path) -> None:
    c = SartnameMetinCikarici()
    assert c.cikar(bos_pdf(tmp_path / "bos.pdf")) == ""
    bozuk = tmp_path / "bozuk.pdf"
    bozuk.write_bytes(b"bu bir pdf degil")
    with pytest.raises(DosyaOkumaHatasi):
        c.cikar(bozuk)
    with pytest.raises(DesteklenmeyenDosyaHatasi) as hata:
        c.uzantiyi_denetle("eski.doc")
    assert hata.value.rehber  # .doc için kaydetme rehberi


# ---------- Madde doğrulama ve dönüştürme ----------


def test_madde_kurallari() -> None:
    gps = Madde(aciklama="GPS zorunlu", buyukluk="gps", sinir_turu="zorunlu", deger=5)
    assert gps.deger is None  # parça maddesinde değer kullanılmaz
    with pytest.raises(GecersizDegerHatasi):
        Madde(aciklama="GPS", buyukluk="gps", sinir_turu="en_cok")
    with pytest.raises(GecersizDegerHatasi):
        Madde(aciklama="Ağırlık", buyukluk="kalkis_agirligi", sinir_turu="en_cok")  # değer yok
    with pytest.raises(GecersizDegerHatasi):
        Madde(aciklama="Ağırlık", buyukluk="kalkis_agirligi", sinir_turu="zorunlu", deger=1)
    assert Madde(aciklama="Failsafe olmalı", buyukluk="diger", sinir_turu="zorunlu").deger is None
    with pytest.raises(GecersizDegerHatasi):
        Madde(aciklama=" ", buyukluk="diger", sinir_turu="zorunlu")


def test_donusturucu_gecersizleri_atlar() -> None:
    sonuc = MaddeDonusturucu().donustur([
        {"aciklama": "En fazla 2 kg", "buyukluk": "kalkis_agirligi", "sinir_turu": "en_cok", "deger": 2000,
         "sinif": "kesin", "madde_no": "4.2", "sayfa": 3.0},
        {"aciklama": "Uydurma", "buyukluk": "uçuş hızı", "sinir_turu": "en_cok", "deger": 1, "sinif": "kesin"},
        {"aciklama": "Değersiz", "buyukluk": "boyut", "sinir_turu": "en_cok", "sinif": "kesin"},
        {"aciklama": "Sayfa bozuk", "buyukluk": "gps", "sinir_turu": "zorunlu", "sinif": "kesin", "sayfa": -2},
        "metin",
    ])
    assert sonuc.atlanan == 3 and len(sonuc.maddeler) == 2
    assert sonuc.maddeler[0].sayfa == 3 and sonuc.maddeler[0].onaylandi is False
    assert sonuc.maddeler[1].sayfa is None  # geçersiz sayfa maddeyi düşürmedi


# ---------- API ----------

MOTOR = {"tur": "motor", "uretici": "T-Motor", "model": "F60", "agirlik_g": 33.5,
         "teknik": {"kv": 1950, "min_s": 4, "maks_s": 6, "maks_akim_a": 35}}
PIL = {"tur": "pil", "uretici": "CNHL", "model": "1500 6S", "agirlik_g": 240,
       "teknik": {"hucre_sayisi_s": 6, "kapasite_mah": 1500, "kimya": "lipo"}}


class SahteSaglayici(ArastirmaSaglayicisi):
    def __init__(self, yanit: dict) -> None:
        self.yanit, self.istemler = yanit, []

    def json_uret(self, sistem_talimati: str, istem: str, sema: dict) -> dict:
        self.istemler.append(istem)
        return self.yanit


@pytest.fixture
def ortam(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    for ad in ANAHTAR_ORTAM_DEGISKENLERI:
        monkeypatch.delenv(ad, raising=False)
    sahte = SahteSaglayici({"maddeler": [
        {"aciklama": "Kalkış ağırlığı en fazla 2 kg", "buyukluk": "kalkis_agirligi", "sinir_turu": "en_cok",
         "deger": 2000, "sinif": "kesin", "madde_no": "4.2", "sayfa": 1},
        {"aciklama": "Geçersiz", "buyukluk": "boyut", "sinir_turu": "en_cok", "sinif": "kesin"},
    ]})
    istemci = TestClient(sunucu_olustur(tmp_path / "veri", saglayici_uretici=lambda a, m: sahte, kur_getirici=lambda: b""))
    dronelar = []
    for ad in ("X", "T"):
        k = istemci.post(
            "/api/dronelar", json={"ad": ad, "baslangic_turu": "sifirdan", "drone_turu": "quadcopter", "amac": "Yarışma (şartnameli)"}
        ).json()["kimlik"]
        istemci.put(f"/api/dronelar/{k}/sasi/agirlik", json={"agirlik_g": 300})
        dronelar.append(k)
    return istemci, dronelar, sahte, tmp_path


def _yukle(istemci: TestClient, yol: Path, ad: str = "Yarışma 2026", drone: int | None = None):
    with yol.open("rb") as f:
        veri = {"ad": ad} | ({"drone_kimlik": str(drone)} if drone is not None else {})
        return istemci.post("/api/sartnameler", files={"dosya": (yol.name, f)}, data=veri)


def test_kutuphane_ve_ikinci_dronea_ekleme(ortam) -> None:
    istemci, (x, t), _, tmp = ortam
    yanit = _yukle(istemci, word_belgesi(tmp / "y.docx"), drone=x)
    assert yanit.status_code == 200, yanit.text
    y = yanit.json()
    assert y["kullanan_drone_sayisi"] == 1 and y["metin_uzunlugu"] > 0
    assert istemci.get(f"/api/dronelar/{t}/sartname").json()["sartname"] is None

    # "t" dronu önceden yüklenmiş "y" şartnamesini kütüphaneden seçer.
    assert [s["ad"] for s in istemci.get("/api/sartnameler").json()] == ["Yarışma 2026"]
    assert istemci.put(f"/api/dronelar/{t}/sartname", json={"sartname_kimlik": y["kimlik"]}).status_code == 200
    assert istemci.get(f"/api/dronelar/{t}/sartname").json()["sartname"]["kullanan_drone_sayisi"] == 2

    # Kullanılan şartname silinemez; dronelardan kaldırınca silinir ve belge kopyası da gider.
    assert istemci.delete(f"/api/sartnameler/{y['kimlik']}").status_code == 400
    istemci.delete(f"/api/dronelar/{x}/sartname")
    istemci.delete(f"/api/dronelar/{t}/sartname")
    assert istemci.delete(f"/api/sartnameler/{y['kimlik']}").status_code == 200
    assert istemci.get("/api/sartnameler").json() == []
    assert not any((tmp / "veri" / "sartname_dosyalari").iterdir())


def test_sayfa_sayaci() -> None:
    import tempfile

    from sartname.sayfa_sayisi import SayfaSayaci

    with tempfile.TemporaryDirectory() as klasor:
        k = Path(klasor)
        assert SayfaSayaci().say(cok_sayfali_pdf(k / "a.pdf", 3), "") == SayfaSayisi(3)
        assert SayfaSayaci().say(word_sayfali(k / "b.docx", 10, pages=7), "") == SayfaSayisi(7)
        # Word sayfa bilgisi yoksa kelime sayısından tahmin: 1001 kelime / 500 → 3 sayfa (yukarı yuvarlanır)
        assert SayfaSayaci().say(word_sayfali(k / "c.docx", 1001, pages=None), "x " * 1001) == SayfaSayisi(3, tahmini=True)


def test_pdf_sayfa_siniri(ortam) -> None:
    istemci, (x, _), _, tmp = ortam
    assert _yukle(istemci, cok_sayfali_pdf(tmp / "elli.pdf", EN_FAZLA_SARTNAME_SAYFASI), drone=x).status_code == 200
    yanit = _yukle(istemci, cok_sayfali_pdf(tmp / "fazla.pdf", EN_FAZLA_SARTNAME_SAYFASI + 1), ad="Uzun")
    assert yanit.status_code == 400
    hata = yanit.json()["hata"]
    assert f"en çok {EN_FAZLA_SARTNAME_SAYFASI} sayfa" in hata and f"{EN_FAZLA_SARTNAME_SAYFASI + 1} sayfa" in hata
    assert "tahmini" not in hata  # PDF'te sayfa sayısı kesin
    assert [s["ad"] for s in istemci.get("/api/sartnameler").json()] == ["Yarışma 2026"]  # reddedilen kaydedilmedi
    assert len(list((tmp / "veri" / "sartname_dosyalari").iterdir())) == 1  # belge kopyası da yok


def test_word_sayfa_siniri_kayitli_ve_tahmini(ortam) -> None:
    istemci, _, _, tmp = ortam
    # Word'ün kaydettiği sayfa sayısı kullanılır (kelime az olsa bile).
    yanit = _yukle(istemci, word_sayfali(tmp / "kayitli.docx", 50, pages=60))
    assert yanit.status_code == 400 and "60 sayfa" in yanit.json()["hata"] and "tahmini" not in yanit.json()["hata"]
    # Sayfa bilgisi yoksa kelime sayısından tahmin edilir ve "tahmini" yazılır: 26.000 / 500 = 52 sayfa.
    yanit = _yukle(istemci, word_sayfali(tmp / "tahmin.docx", 26_000, pages=None))
    assert yanit.status_code == 400 and "52 sayfa" in yanit.json()["hata"] and "tahmini" in yanit.json()["hata"]
    assert _yukle(istemci, word_sayfali(tmp / "kisa.docx", 1_000, pages=None)).status_code == 200


def test_yukleme_hatalari(ortam) -> None:
    istemci, (x, _), _, tmp = ortam
    eski = tmp / "eski.doc"
    eski.write_bytes(b"x")
    yanit = _yukle(istemci, eski)
    assert yanit.status_code == 415 and yanit.json()["rehber"]
    yanit = _yukle(istemci, word_belgesi(tmp / "a.docx"), ad=" ")
    assert yanit.status_code == 400 and "ad" in yanit.json()["hata"]
    assert _yukle(istemci, word_belgesi(tmp / "b.docx"), drone=999).status_code == 404
    assert istemci.get("/api/sartnameler").json() == []


def test_gemini_cikarimi_ve_onay(ortam) -> None:
    istemci, (x, _), sahte, tmp = ortam
    sid = _yukle(istemci, word_belgesi(tmp / "y.docx"), drone=x).json()["kimlik"]
    assert istemci.post(f"/api/sartnameler/{sid}/cikar").status_code == 401  # anahtar yok, istek yapılmadı
    assert sahte.istemler == []

    istemci.put("/api/ayarlar/yapay-zeka", json={"anahtar": SAHTE_ANAHTAR})
    yanit = istemci.post(f"/api/sartnameler/{sid}/cikar")
    assert yanit.status_code == 200, yanit.text
    v = yanit.json()
    assert len(v["maddeler"]) == 1 and v["atlanan"] == 1 and v["bugun_kullanilan"] == 1
    assert v["maddeler"][0]["onaylandi"] is False
    assert "en fazla 2 kg" in sahte.istemler[0]  # belge metni modele gitti

    rapor = istemci.get(f"/api/dronelar/{x}/sartname").json()["rapor"]
    assert rapor[0]["durum"] == "onay_bekliyor"


def test_taranmis_belgede_cikarim_yapilmaz(ortam) -> None:
    istemci, (x, _), sahte, tmp = ortam
    istemci.put("/api/ayarlar/yapay-zeka", json={"anahtar": SAHTE_ANAHTAR})
    s = _yukle(istemci, bos_pdf(tmp / "t.pdf"), drone=x).json()
    assert s["metin_uzunlugu"] == 0
    yanit = istemci.post(f"/api/sartnameler/{s['kimlik']}/cikar")
    assert yanit.status_code == 400 and "elle" in yanit.json()["hata"]
    assert sahte.istemler == []


def test_uyum_raporu(ortam) -> None:
    istemci, (x, _), _, tmp = ortam
    sid = _yukle(istemci, basit_pdf(tmp / "y.pdf", ["Kurallar"]), drone=x).json()["kimlik"]
    istemci.post(f"/api/dronelar/{x}/parcalar", json={"parca": MOTOR, "adet": 4})
    istemci.post(f"/api/dronelar/{x}/parcalar", json={"parca": PIL, "adet": 1})
    maddeler = [
        {"madde_no": "4.2", "aciklama": "En fazla 500 g", "buyukluk": "kalkis_agirligi", "sinir_turu": "en_cok", "deger": 500, "sinif": "kesin", "onaylandi": True},
        {"madde_no": "4.3", "aciklama": "GPS zorunlu", "buyukluk": "gps", "sinir_turu": "zorunlu", "sinif": "kesin", "onaylandi": True},
        {"madde_no": "4.4", "aciklama": "En çok 6S", "buyukluk": "pil_hucre", "sinir_turu": "en_cok", "deger": 6, "sinif": "kesin", "onaylandi": True},
        {"madde_no": "5.1", "aciklama": "Failsafe olmalı", "buyukluk": "diger", "sinir_turu": "zorunlu", "sinif": "kesin", "onaylandi": True},
        {"madde_no": "7.1", "aciklama": "Uzun uçuş puan getirir", "buyukluk": "ucus_suresi", "sinir_turu": "en_az", "deger": 10, "sinif": "puanlanan", "onaylandi": True},
        {"madde_no": "4.5", "aciklama": "4 motor", "buyukluk": "motor_sayisi", "sinir_turu": "esit", "deger": 4, "sinif": "kesin", "onaylandi": False},
    ]
    assert istemci.put(f"/api/sartnameler/{sid}/maddeler", json={"maddeler": maddeler}).status_code == 200
    rapor = {r["madde"]["madde_no"]: r for r in istemci.get(f"/api/dronelar/{x}/sartname").json()["rapor"]}
    # 300 g şasi + 134 g motor + 240 g pil + %5 pay = 708,7 g > 500 g
    assert rapor["4.2"]["durum"] == "uygunsuz" and "fazla" in rapor["4.2"]["aciklama"] and rapor["4.2"]["tahmini"]
    assert rapor["4.3"]["durum"] == "uygunsuz" and rapor["4.3"]["tasarim"] == "yok"
    assert rapor["4.4"]["durum"] == "uygun" and rapor["4.4"]["tasarim"] == "6 S"
    assert rapor["5.1"]["durum"] == "bilinmiyor" and "elle" in rapor["5.1"]["aciklama"]
    assert rapor["7.1"]["durum"] == "bilgi"
    assert rapor["4.5"]["durum"] == "onay_bekliyor" and "uygun" in rapor["4.5"]["aciklama"]


def test_eksik_agirlikta_en_cok_siniri(ortam) -> None:
    """Ağırlığı bilinmeyen parça varsa toplam bir alt sınırdır: sınırın altındaysa 'doğrulanamıyor'."""
    istemci, (x, _), _, tmp = ortam
    sid = _yukle(istemci, word_belgesi(tmp / "y.docx"), drone=x).json()["kimlik"]
    istemci.post(f"/api/dronelar/{x}/parcalar", json={"parca": {"tur": "esc", "uretici": "E", "model": "1"}})
    madde = {"aciklama": "En fazla 2 kg", "buyukluk": "kalkis_agirligi", "sinir_turu": "en_cok", "deger": 2000, "sinif": "kesin", "onaylandi": True}
    istemci.put(f"/api/sartnameler/{sid}/maddeler", json={"maddeler": [madde]})
    r = istemci.get(f"/api/dronelar/{x}/sartname").json()["rapor"][0]
    assert r["durum"] == "bilinmiyor" and "daha yüksek olabilir" in r["aciklama"]


def test_madde_kaydetme_hatasi_satir_numarali(ortam) -> None:
    istemci, (x, _), _, tmp = ortam
    sid = _yukle(istemci, word_belgesi(tmp / "y.docx"), drone=x).json()["kimlik"]
    maddeler = [
        {"aciklama": "Tamam", "buyukluk": "gps", "sinir_turu": "zorunlu", "sinif": "kesin"},
        {"aciklama": "Değer yok", "buyukluk": "boyut", "sinir_turu": "en_cok", "sinif": "kesin"},
    ]
    yanit = istemci.put(f"/api/sartnameler/{sid}/maddeler", json={"maddeler": maddeler})
    assert yanit.status_code == 400 and yanit.json()["hata"].startswith("2. madde")
    assert istemci.get(f"/api/sartnameler/{sid}").json()["maddeler"] == []  # hiçbiri kaydedilmedi


def test_maliyet_maddesi(ortam) -> None:
    istemci, (x, _), _, tmp = ortam
    sid = _yukle(istemci, word_belgesi(tmp / "y.docx"), drone=x).json()["kimlik"]
    istemci.put(f"/api/dronelar/{x}/sasi/fiyat", json={"tutar": 1500})
    madde = {"aciklama": "Bütçe en çok 1000 TL", "buyukluk": "maliyet", "sinir_turu": "en_cok", "deger": 1000, "sinif": "kesin", "onaylandi": True}
    istemci.put(f"/api/sartnameler/{sid}/maddeler", json={"maddeler": [madde]})
    r = istemci.get(f"/api/dronelar/{x}/sartname").json()["rapor"][0]
    assert r["durum"] == "uygunsuz" and r["tasarim"] == "1500 TL"


def test_oneride_sartname_maddeleri_kullanilir(ortam) -> None:
    istemci, (x, _), _, tmp = ortam
    sid = _yukle(istemci, word_belgesi(tmp / "y.docx"), drone=x).json()["kimlik"]
    istemci.post(f"/api/dronelar/{x}/parcalar", json={"parca": MOTOR, "adet": 4})
    maddeler = [
        {"madde_no": "4.4", "aciklama": "En çok 4S", "buyukluk": "pil_hucre", "sinir_turu": "en_cok", "deger": 4, "sinif": "kesin", "onaylandi": True},
        {"madde_no": "9", "aciklama": "Onaysız", "buyukluk": "pil_hucre", "sinir_turu": "en_cok", "deger": 1, "sinif": "kesin", "onaylandi": False},
    ]
    istemci.put(f"/api/sartnameler/{sid}/maddeler", json={"maddeler": maddeler})

    sahte = SahteSaglayici({"adaylar": [
        {"uretici": "A", "model": "6S", "gerekce": "g", "teknik": {"hucre_sayisi_s": 6}},
        {"uretici": "B", "model": "4S", "gerekce": "g", "teknik": {"hucre_sayisi_s": 4}},
    ]})
    oneri_istemcisi = TestClient(sunucu_olustur(tmp / "veri", saglayici_uretici=lambda a, m: sahte, kur_getirici=lambda: b""))
    oneri_istemcisi.put("/api/ayarlar/yapay-zeka", json={"anahtar": SAHTE_ANAHTAR})
    v = oneri_istemcisi.post(f"/api/dronelar/{x}/oneriler", json={"tur": "pil"}).json()
    assert [a["parca"]["model"] for a in v["adaylar"]] == ["4S", "6S"]  # şartnameye uymayan sona
    assert v["adaylar"][1]["sartname_ihlalleri"][0]["madde_no"] == "4.4"
    istem = sahte.istemler[0]
    assert "şartnamesinin" in istem and "en çok 4" in istem and "Onaysız" not in istem
