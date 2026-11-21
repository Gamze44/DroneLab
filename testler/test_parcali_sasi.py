"""
Parçalı şasi (zip) testleri: gövde analizi, zip okuyucu güvenliği, rol/adet önerisi,
dingil tahmini, özet ölçüler, kayıt ve API akışı.

Örnek zip'ler her testte geçici klasörde üretilir; gerçek veritabanına dokunulmaz.
"""

import math
from pathlib import Path
import zipfile

from fastapi.testclient import TestClient
import pytest
import trimesh

from arayuz.sunucu import sunucu_olustur
from cekirdek.arsiv_denetimi import ArsivDenetleyici
from cekirdek.ayarlar import VERITABANI_DOSYA_ADI
from cekirdek.hatalar import DosyaOkumaHatasi, GecersizDegerHatasi
from depolama.serilestirme import SasiSerilestirici
from depolama.veritabani import Veritabani
from drone.hedefler import DroneHedefleri
from elektronik.hesap.katsayilar import DINGIL_KATSAYISI
from sartname.kontrol import SartnameBaglami, SartnameKontrolcusu
from sartname.modeller import Buyukluk
from sasi.dingil import DingilHesaplayici, KolBaglantisi
from sasi.modeller import GeometriTuru, ParcaRolu, SasiGeometrisi, SasiOlculeri, SasiParcasi
from sasi.okuyucu_secici import OkuyucuSecici
from sasi.okuyucular.ag_okuyucu import AgOkuyucu
from sasi.okuyucular.zip_okuyucu import EN_FAZLA_SASI_PARCASI, ZipSasiOkuyucu
from sasi.parca_onerici import AYAK_SAYISI, ParcaOnerici
from sasi.parcali_olcu import ParcaliSasiOzetleyici

YENI_DRONE = {"ad": "Parçalı", "baslangic_turu": "sifirdan", "drone_turu": "quadcopter", "amac": "FPV yarış"}
KOL_OLCULERI = (24.4, 155.5, 5.0)
UST_PLAKA = (40.0, 170.0, 2.5)
ALT_PLAKA = (50.0, 176.0, 2.5)
DESTEK = (49.0, 18.0, 2.0)
# Mark4 7" benzeri: kollar ortada buluşur, R = 155,5 − 24,4/2.
MARK4_DINGIL_MM = 2 * (155.5 - 24.4 / 2)


def _stl(olculer: tuple[float, float, float], kopya: int = 1, kirinti: int = 0) -> bytes:
    """Yan yana dizilmiş kopya kutular (+ birkaç mm'lik kırıntı) içeren STL baytları."""
    aglar = []
    for i in range(kopya):
        kutu = trimesh.creation.box(extents=olculer)
        kutu.apply_translation((i * (olculer[0] + 10), 0, 0))
        aglar.append(kutu)
    for i in range(kirinti):
        k = trimesh.creation.box(extents=(2, 2, 2))
        k.apply_translation((-50 - i * 5, -100, 0))
        aglar.append(k)
    return trimesh.util.concatenate(aglar).export(file_type="stl")


def _zip(yol: Path, uyeler: dict[str, bytes], klasorler: tuple[str, ...] = ()) -> Path:
    with zipfile.ZipFile(yol, "w", zipfile.ZIP_DEFLATED) as z:
        for klasor in klasorler:
            z.writestr(klasor, b"")
        for ad, veri in uyeler.items():
            z.writestr(ad, veri)
    return yol


@pytest.fixture
def sasi_zip(tmp_path: Path) -> Path:
    """Mark4 benzeri parçalı şasi: üst/alt plaka, tek dosyada 4 kol, kol desteği, PDF ve sistem dosyası."""
    return _zip(
        tmp_path / "mark4.zip",
        {
            "Top.stl": _stl(UST_PLAKA),
            "parcalar/Bottom.stl": _stl(ALT_PLAKA),
            "7in Arms.stl": _stl(KOL_OLCULERI, kopya=4, kirinti=3),
            "Arm Suport.stl": _stl(DESTEK, kopya=2),
            "montaj.pdf": b"%PDF-1.4 sahte",
            "__MACOSX/._Top.stl": b"\x00\x05\x16\x07",
        },
        klasorler=("parcalar/",),
    )


def _okuyucu(**denetim: int) -> ZipSasiOkuyucu:
    secici = OkuyucuSecici()
    return ZipSasiOkuyucu(secici._parca_okuyucusu, ArsivDenetleyici(**denetim) if denetim else None)


# ---------- Gövde analizi ----------


def test_ozdes_govdeler_ve_tek_govde_olcusu_bulunur(tmp_path: Path) -> None:
    yol = tmp_path / "kollar.stl"
    yol.write_bytes(_stl(KOL_OLCULERI, kopya=4, kirinti=3))
    g = AgOkuyucu().oku(yol)
    assert g.govde_sayisi == 7 and g.ozdes_govde_sayisi == 4
    assert g.tek_govde_olculeri == pytest.approx(KOL_OLCULERI)


def test_tek_govdeli_dosyada_tek_olcu_dis_olcudur(stl_dosyasi: Path) -> None:
    g = AgOkuyucu().oku(stl_dosyasi)
    assert g.ozdes_govde_sayisi == 1 and g.tek_govde_olculeri == pytest.approx(g.olculer)


# ---------- Zip okuyucu ----------


def test_zip_parcalari_okunur_sistem_dosyalari_atlanir(sasi_zip: Path) -> None:
    sonuc = _okuyucu().oku(sasi_zip)
    adlar = [g.dosya_adi for g in sonuc.parcalar]
    # Klasör yolu gösterilmez; __MACOSX ve klasör girdileri parça sayılmaz.
    assert sorted(adlar) == ["7in Arms.stl", "Arm Suport.stl", "Bottom.stl", "Top.stl"]
    assert any("montaj.pdf" in u for u in sonuc.uyarilar)
    assert all(g.ag is None for g in sonuc.parcalar)


def test_zip_icindeki_ad_disk_yolu_olarak_kullanilmaz(tmp_path: Path) -> None:
    hedef_klasor = tmp_path / "zip"
    hedef_klasor.mkdir()
    yol = _zip(hedef_klasor / "kotu.zip", {"../../kacak.stl": _stl(UST_PLAKA), "..\\..\\kacak2.stl": _stl(ALT_PLAKA)})
    sonuc = _okuyucu().oku(yol)
    assert sorted(g.dosya_adi for g in sonuc.parcalar) == ["kacak.stl", "kacak2.stl"]
    assert not list(tmp_path.rglob("kacak*.stl"))


def test_parcasiz_zip_turkce_hata_verir(tmp_path: Path) -> None:
    yol = _zip(tmp_path / "bos.zip", {"oku_beni.txt": b"merhaba"})
    with pytest.raises(DosyaOkumaHatasi, match="okunabilen şasi parçası bulunamadı"):
        _okuyucu().oku(yol)


def test_zip_olmayan_dosya_bozuk_sayilir(tmp_path: Path) -> None:
    yol = tmp_path / "sahte.zip"
    yol.write_bytes(b"bu bir zip degil")
    with pytest.raises(DosyaOkumaHatasi):
        _okuyucu().oku(yol)


def test_cok_parcali_zip_reddedilir(tmp_path: Path) -> None:
    kucuk = _stl((10, 10, 10))
    yol = _zip(tmp_path / "cok.zip", {f"p{i}.stl": kucuk for i in range(EN_FAZLA_SASI_PARCASI + 1)})
    with pytest.raises(DosyaOkumaHatasi, match=f"en çok {EN_FAZLA_SASI_PARCASI}"):
        _okuyucu().oku(yol)


def test_zip_once_bomba_denetiminden_gecer(sasi_zip: Path) -> None:
    with pytest.raises(DosyaOkumaHatasi, match="olağan dışı"):
        _okuyucu(en_fazla_uye=2).oku(sasi_zip)


def test_bozuk_parca_atlanir_digerleri_okunur(tmp_path: Path) -> None:
    yol = _zip(tmp_path / "yarim.zip", {"Top.stl": _stl(UST_PLAKA), "Kirik.stl": b"solid x\nbozuk veri"})
    sonuc = _okuyucu().oku(yol)
    assert [g.dosya_adi for g in sonuc.parcalar] == ["Top.stl"]
    uyari = next(u for u in sonuc.uyarilar if "Kirik.stl" in u)
    assert "atlandı" in uyari and "parca_" not in uyari


# ---------- Rol ve adet önerisi ----------


@pytest.mark.parametrize(
    ("ad", "rol"),
    [
        ("7in Arms.stl", ParcaRolu.KOL),
        ("Arm Suport.stl", ParcaRolu.DIGER),
        ("Top.stl", ParcaRolu.GOVDE),
        ("BottomPlate.stl", ParcaRolu.GOVDE),
        ("Gövde Üst.stl", ParcaRolu.GOVDE),
        ("KOLLAR.3mf", ParcaRolu.KOL),
        ("landing_gear.stl", ParcaRolu.AYAK),
        ("Camera Mount.stl", ParcaRolu.DIGER),
        ("Head.stl", ParcaRolu.DIGER),
    ],
)
def test_rol_dosya_adindan_onerilir(ad: str, rol: ParcaRolu) -> None:
    assert ParcaOnerici().rol_oner(ad) is rol


def _g(ad: str, ozdes: int = 1) -> SasiGeometrisi:
    return SasiGeometrisi(dosya_adi=ad, tur=GeometriTuru.KATI, olculer=(10, 10, 10), ozdes_govde_sayisi=ozdes)


def test_kol_adedi_dosyadaki_kopya_ve_motor_sayisina_gore() -> None:
    onerici = ParcaOnerici()
    assert [p.adet for p in onerici.oner([_g("arm.stl")], 4)] == [4]
    assert [p.adet for p in onerici.oner([_g("arms.stl", ozdes=4)], 4)] == [1]
    assert [p.adet for p in onerici.oner([_g("arm_sol.stl"), _g("arm_sag.stl")], 4)] == [2, 2]
    assert [p.adet for p in onerici.oner([_g("arm.stl")], 6)] == [6]
    assert [p.adet for p in onerici.oner([_g("leg.stl"), _g("top.stl")], 4)] == [AYAK_SAYISI, 1]


# ---------- Dingil ----------


def _parca(olculer: tuple[float, float, float], rol: ParcaRolu, adet: int = 1, sira: int = 0) -> SasiParcasi:
    g = SasiGeometrisi(dosya_adi=f"{rol.value}.stl", tur=GeometriTuru.KATI, olculer=olculer,
                       hacim=olculer[0] * olculer[1] * olculer[2], tek_govde_olculeri=olculer)
    return SasiParcasi(sira=sira, geometri=g, rol=rol, adet=adet)


def test_merkez_baglantida_dingil_kol_boyundan() -> None:
    kol = _parca(KOL_OLCULERI, ParcaRolu.KOL)
    t = DingilHesaplayici().hesapla(kol, "mm", KolBaglantisi.MERKEZ)
    assert t.dingil_mm == pytest.approx(MARK4_DINGIL_MM)
    assert t.kol_boyu_mm == pytest.approx(155.5) and "tahmini" in t.aciklama


def test_dingil_birimi_cevirir_ve_dik_duran_kolu_tanir() -> None:
    dik_kol_cm = _parca((0.5, 2.44, 15.55), ParcaRolu.KOL)
    assert DingilHesaplayici().hesapla(dik_kol_cm, "cm", KolBaglantisi.MERKEZ).dingil_mm == pytest.approx(MARK4_DINGIL_MM)


def test_kenar_baglantida_govde_kosegeni_eklenir() -> None:
    kol, govde = _parca(KOL_OLCULERI, ParcaRolu.KOL), _parca(UST_PLAKA, ParcaRolu.GOVDE, sira=1)
    t = DingilHesaplayici().hesapla(kol, "mm", KolBaglantisi.KENAR, govde)
    beklenen = 2 * (math.hypot(40, 170) / 2 + 155.5 - 24.4 / 2 - 24.4)
    assert t.dingil_mm == pytest.approx(beklenen)
    with pytest.raises(GecersizDegerHatasi, match="gövde parçasını"):
        DingilHesaplayici().hesapla(kol, "mm", KolBaglantisi.KENAR)


# ---------- Özet ölçüler ----------


def test_ozet_hacmi_adetlerle_toplar_ve_dingilsiz_olcu_govdedir() -> None:
    parcalar = [_parca(UST_PLAKA, ParcaRolu.GOVDE), _parca(KOL_OLCULERI, ParcaRolu.KOL, adet=4, sira=1)]
    ozetleyici = ParcaliSasiOzetleyici()
    ozet = ozetleyici.ozet_geometri("s.zip", parcalar, [])
    assert ozet.hacim == pytest.approx(40 * 170 * 2.5 + 4 * 24.4 * 155.5 * 5)
    olculer = ozetleyici.olculeri_hesapla(ozet, parcalar, "mm", 4)
    assert (olculer.en_mm, olculer.boy_mm) == pytest.approx((40, 170))
    assert olculer.tahmini and olculer.dingil_bilinmiyor and olculer.parca_sayisi == 2


def test_dingil_verilince_dis_olcu_motor_yerlerinden() -> None:
    parcalar = [_parca(UST_PLAKA, ParcaRolu.GOVDE), _parca(KOL_OLCULERI, ParcaRolu.KOL, sira=1)]
    ozetleyici = ParcaliSasiOzetleyici()
    ozet = ozetleyici.ozet_geometri("s.zip", parcalar, [])
    olculer = ozetleyici.olculeri_hesapla(ozet, parcalar, "mm", 4, dingil_mm=300)
    yayilim = 300 * math.cos(math.pi / 4)
    assert olculer.en_mm == pytest.approx(yayilim + 24.4) and olculer.boy_mm == pytest.approx(yayilim + 24.4)
    assert not olculer.dingil_bilinmiyor


def test_sartname_boyutu_dingilsiz_parcali_sasida_olculemez() -> None:
    def olc(olculer: SasiOlculeri):
        baglam = SartnameBaglami([], 4, olculer, agirlik=None, ucus=None, hedefler=DroneHedefleri())  # type: ignore[arg-type]
        return SartnameKontrolcusu().olc(Buyukluk.BOYUT, baglam)

    dingilsiz = SasiOlculeri(birim="mm", en_mm=40, boy_mm=170, yukseklik_mm=5, parca_sayisi=3, tahmini=True)
    assert olc(dingilsiz).deger is None and "dingil" in olc(dingilsiz).neden
    dingilli = SasiOlculeri(birim="mm", en_mm=230, boy_mm=230, yukseklik_mm=5, parca_sayisi=3, tahmini=True, dingil_mm=290)
    assert olc(dingilli).deger == 230 and olc(dingilli).tahmini


# ---------- Kayıt ----------


def test_eski_kayitlar_yeni_alanlar_olmadan_okunur() -> None:
    s = SasiSerilestirici()
    eski_geometri = '{"dosya_adi": "a.stl", "tur": "kati", "olculer": [1, 2, 3]}'
    g = s.geometriyi_oku(eski_geometri)
    assert g.ozdes_govde_sayisi == 1 and g.tek_govde_olculeri is None
    o = s.olculeri_oku('{"birim": "mm", "en_mm": 1, "boy_mm": 2, "yukseklik_mm": 3}')
    assert o.dingil_mm is None and o.parca_sayisi == 0 and not o.tahmini and not o.dingil_bilinmiyor


# ---------- API ----------


@pytest.fixture
def istemci(tmp_path: Path) -> TestClient:
    return TestClient(sunucu_olustur(tmp_path / "veri", kur_getirici=lambda: b""))


def _yukle(istemci: TestClient, yol: Path) -> tuple[int, dict]:
    kimlik = istemci.post("/api/dronelar", json=YENI_DRONE).json()["kimlik"]
    yanit = istemci.post(f"/api/dronelar/{kimlik}/sasi", files={"dosya": (yol.name, yol.read_bytes())})
    assert yanit.status_code == 200, yanit.text
    return kimlik, yanit.json()["yukleme"]


def _k5(istemci: TestClient, kimlik: int) -> dict:
    return next(u for u in istemci.get(f"/api/dronelar/{kimlik}/elektronik").json()["uyum"] if u["kod"] == "K5")


def test_zip_yukleme_ve_dingil_akisi(istemci: TestClient, sasi_zip: Path) -> None:
    kimlik, y = _yukle(istemci, sasi_zip)
    assert y["parcali"] and len(y["parcalar"]) == 4
    roller = {p["dosya_adi"]: (p["rol"], p["adet"]) for p in y["parcalar"]}
    assert roller["7in Arms.stl"] == ("kol", 1) and roller["Arm Suport.stl"] == ("diger", 1)
    assert roller["Top.stl"][0] == "govde" and roller["Bottom.stl"][0] == "govde"
    assert y["oneri"]["birim"] == "mm"

    o = istemci.post(f"/api/dronelar/{kimlik}/sasi/birim", json={"birim": "mm"}).json()["olculer"]
    assert o["tahmini"] and o["dingil_bilinmiyor"] and o["etkin_dingil_mm"] is None
    ozet = istemci.get(f"/api/dronelar/{kimlik}/elektronik").json()
    assert ozet["sasi_gorunumu"] is None and ozet["sasi_dingil_bilinmiyor"] and ozet["sasi_olculeri_var"]

    pervane = {"tur": "pervane", "uretici": "HQ", "model": "7x4", "teknik": {"cap_inc": 7.0, "hatve_inc": 4.0}}
    istemci.post(f"/api/dronelar/{kimlik}/parcalar", json={"parca": pervane, "adet": 4})
    k5 = _k5(istemci, kimlik)
    assert k5["durum"] == "bilinmiyor" and "dingil" in k5["aciklama"]

    kol = next(p["sira"] for p in y["parcalar"] if p["rol"] == "kol")
    govde = next(p["sira"] for p in y["parcalar"] if p["rol"] == "govde")
    t = istemci.post(
        f"/api/dronelar/{kimlik}/sasi/dingil-hesapla", json={"kol_sira": kol, "govde_sira": govde, "baglanti": "merkez"}
    ).json()
    assert t["tahmini"] and t["dingil_mm"] == pytest.approx(MARK4_DINGIL_MM, rel=1e-3)
    # Hesaplamak kaydetmez; kullanıcı onaylamalı.
    assert istemci.get(f"/api/dronelar/{kimlik}").json()["sasi"]["olculer"]["dingil_mm"] is None

    o = istemci.put(f"/api/dronelar/{kimlik}/sasi/dingil", json={"dingil_mm": t["dingil_mm"], "kaynak": "hesap"}).json()["olculer"]
    assert o["dingil_kaynagi"] == "hesap" and o["etkin_dingil_mm"] == pytest.approx(t["dingil_mm"])
    assert o["en_mm"] > ALT_PLAKA[0]
    g = istemci.get(f"/api/dronelar/{kimlik}/elektronik").json()["sasi_gorunumu"]
    assert g["dingil_mm"] == pytest.approx(t["dingil_mm"])
    assert _k5(istemci, kimlik)["durum"] != "bilinmiyor"

    # Hesaplanmış dingil, birim değişince eski birimle yapıldığı için silinir.
    o = istemci.post(f"/api/dronelar/{kimlik}/sasi/birim", json={"birim": "cm"}).json()["olculer"]
    assert o["dingil_mm"] is None


def test_parca_adedi_degisince_hacim_yenilenir_dingil_korunur(istemci: TestClient, sasi_zip: Path) -> None:
    kimlik, y = _yukle(istemci, sasi_zip)
    istemci.post(f"/api/dronelar/{kimlik}/sasi/birim", json={"birim": "mm"})
    istemci.put(f"/api/dronelar/{kimlik}/sasi/dingil", json={"dingil_mm": 295, "kaynak": "elle"})
    destek = next(p for p in y["parcalar"] if p["dosya_adi"] == "Arm Suport.stl")
    once = istemci.get(f"/api/dronelar/{kimlik}").json()["sasi"]["olculer"]["hacim_mm3"]

    yanit = istemci.put(
        f"/api/dronelar/{kimlik}/sasi/parcalar", json={"parcalar": [{"sira": destek["sira"], "rol": "kol", "adet": 3}]}
    )
    assert yanit.status_code == 200, yanit.text
    sonra = yanit.json()
    assert sonra["olculer"]["hacim_mm3"] == pytest.approx(once + 2 * destek["hacim_ham"])
    assert sonra["olculer"]["dingil_mm"] == 295 and sonra["olculer"]["dingil_kaynagi"] == "elle"
    yeni = next(p for p in sonra["yukleme"]["parcalar"] if p["sira"] == destek["sira"])
    assert (yeni["rol"], yeni["adet"]) == ("kol", 3)
    # Elle girilen dingil birim değişse de korunur (mm cinsinden girilmiştir).
    o = istemci.post(f"/api/dronelar/{kimlik}/sasi/birim", json={"birim": "cm"}).json()["olculer"]
    assert o["dingil_mm"] == 295


@pytest.mark.parametrize(
    ("degisiklik", "mesaj"),
    [({"rol": "kol", "adet": 0}, "adet"), ({"rol": "kanat", "adet": 1}, "rol"), ({"rol": "kol", "adet": 1000}, "adet")],
)
def test_gecersiz_parca_degisikligi_turkce_reddedilir(
    istemci: TestClient, sasi_zip: Path, degisiklik: dict, mesaj: str
) -> None:
    kimlik, _ = _yukle(istemci, sasi_zip)
    yanit = istemci.put(f"/api/dronelar/{kimlik}/sasi/parcalar", json={"parcalar": [{"sira": 0, **degisiklik}]})
    assert yanit.status_code == 400 and mesaj in yanit.json()["hata"]


def test_tek_dosyada_dingil_elle_girilir_parca_islemi_reddedilir(istemci: TestClient, stl_dosyasi: Path) -> None:
    kimlik, y = _yukle(istemci, stl_dosyasi)
    assert not y["parcali"] and y["parcalar"] == []
    # Birim onaylanmadan dingil girilemez.
    assert istemci.put(f"/api/dronelar/{kimlik}/sasi/dingil", json={"dingil_mm": 300}).status_code == 400
    o = istemci.post(f"/api/dronelar/{kimlik}/sasi/birim", json={"birim": "mm"}).json()["olculer"]
    assert o["etkin_dingil_mm"] is not None and o["dingil_kaynagi"] is None and not o["tahmini"]

    o = istemci.put(f"/api/dronelar/{kimlik}/sasi/dingil", json={"dingil_mm": 300}).json()["olculer"]
    assert o["etkin_dingil_mm"] == 300 and o["en_mm"] == pytest.approx(250)
    assert istemci.put(f"/api/dronelar/{kimlik}/sasi/dingil", json={"dingil_mm": 5}).status_code == 400
    o = istemci.put(f"/api/dronelar/{kimlik}/sasi/dingil", json={"dingil_mm": None}).json()["olculer"]
    assert o["dingil_mm"] is None and o["etkin_dingil_mm"] == pytest.approx(math.hypot(250, 250) * DINGIL_KATSAYISI)

    yanit = istemci.put(f"/api/dronelar/{kimlik}/sasi/parcalar", json={"parcalar": []})
    assert yanit.status_code == 400 and "parçalı" in yanit.json()["hata"]


def test_yeni_dosya_parcalari_degistirir_drone_silinince_parcalar_silinir(
    tmp_path: Path, istemci: TestClient, sasi_zip: Path, stl_dosyasi: Path
) -> None:
    kimlik, _ = _yukle(istemci, sasi_zip)
    vt = Veritabani(tmp_path / "veri" / VERITABANI_DOSYA_ADI)

    def parca_sayisi() -> int:
        with vt.baglanti() as bag:
            return bag.execute("SELECT COUNT(*) FROM sasi_parcalari WHERE drone_kimlik = ?", (kimlik,)).fetchone()[0]

    assert parca_sayisi() == 4
    istemci.post(f"/api/dronelar/{kimlik}/sasi", files={"dosya": ("tek.stl", stl_dosyasi.read_bytes())})
    assert parca_sayisi() == 0
    istemci.post(f"/api/dronelar/{kimlik}/sasi", files={"dosya": ("mark4.zip", sasi_zip.read_bytes())})
    assert parca_sayisi() == 4
    istemci.delete(f"/api/dronelar/{kimlik}")
    assert parca_sayisi() == 0


def test_desteklenen_turlerde_zip_var() -> None:
    assert ".zip" in OkuyucuSecici().desteklenen_uzantilar
    OkuyucuSecici().denetle("sasi.zip")  # hata fırlatmamalı
