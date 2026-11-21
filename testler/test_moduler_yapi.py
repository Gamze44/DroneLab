"""
Modülerlik düzenlemesinin sözleşme testleri: sunucunun arayüze hazır gönderdiği değerler
(mm/cm, eksik kodu, parça kimlikleri), merkezî birim dönüşümleri, ortak yardımcılar ve
parça serileştirmesinin hata ayrımı.
"""

from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from arayuz.sunucu import sunucu_olustur
from cekirdek.bicim import sayi_yaz
from cekirdek.birimler import BAYT_BIR_MB, BirimDonusturucu
from cekirdek.hatalar import GecersizDegerHatasi
from cekirdek.metin import metni_sadelestir
from elektronik.parcalar.serilestirme import ParcaSerilestirici
from maliyet.hesap import EKSIK_FIYAT_YOK, EKSIK_KUR_YOK

YENI_DRONE = {"ad": "Modül", "baslangic_turu": "sifirdan", "drone_turu": "quadcopter", "amac": "FPV yarış"}
MM_BIR_INC = 25.4


@pytest.fixture
def istemci(tmp_path: Path) -> TestClient:
    return TestClient(sunucu_olustur(tmp_path / "veri", kur_getirici=lambda: b""))


def _drone(istemci: TestClient) -> int:
    return istemci.post("/api/dronelar", json=YENI_DRONE).json()["kimlik"]


def test_sasi_gorunumu_mm_degerlerini_de_gonderir(istemci: TestClient, stl_dosyasi: Path) -> None:
    kimlik = _drone(istemci)
    istemci.post(f"/api/dronelar/{kimlik}/sasi", files={"dosya": ("sasi.stl", stl_dosyasi.read_bytes())})
    olculer = istemci.post(f"/api/dronelar/{kimlik}/sasi/birim", json={"birim": "mm"}).json()["olculer"]
    assert olculer["hacim_cm3"] == pytest.approx(olculer["hacim_mm3"] / 1000)
    assert olculer["alan_cm2"] is None

    g = istemci.get(f"/api/dronelar/{kimlik}/elektronik").json()["sasi_gorunumu"]
    assert g["pervane_cap_inc"] is None and g["pervane_cap_mm"] is None
    assert g["en_buyuk_pervane_mm"] == pytest.approx(g["en_buyuk_pervane_inc"] * MM_BIR_INC)

    pervane = {"tur": "pervane", "uretici": "HQ", "model": "5x4.3", "teknik": {"cap_inc": 5.1, "hatve_inc": 4.3}}
    istemci.post(f"/api/dronelar/{kimlik}/parcalar", json={"parca": pervane, "adet": 4})
    g = istemci.get(f"/api/dronelar/{kimlik}/elektronik").json()["sasi_gorunumu"]
    assert g["pervane_cap_inc"] == 5.1 and g["pervane_cap_mm"] == pytest.approx(5.1 * MM_BIR_INC)


def test_maliyet_kalemleri_kimligini_ve_eksik_kodunu_tasir(istemci: TestClient) -> None:
    kimlik = _drone(istemci)
    bag = istemci.post(
        f"/api/dronelar/{kimlik}/parcalar", json={"parca": {"tur": "motor", "uretici": "T", "model": "M"}, "adet": 4}
    ).json()
    istemci.put(f"/api/dronelar/{kimlik}/hedefler", json={"butce_tl": 1000})
    m = istemci.get(f"/api/dronelar/{kimlik}/maliyet").json()

    sasi, motor = m["kalemler"]
    assert sasi["tip"] == "sasi" and sasi["eksik_kodu"] == EKSIK_FIYAT_YOK
    assert motor["tip"] == "parca" and motor["parca_kimlik"] == bag["parca_kimlik"] and motor["bag_kimlik"] == bag["kimlik"]
    assert m["yerel_para_birimi"] == "TRY" and m["butce_kalan_tl"] == 1000

    istemci.put(f"/api/katalog/{bag['parca_kimlik']}/fiyat", json={"tutar": 10, "para_birimi": "USD"})
    motor = istemci.get(f"/api/dronelar/{kimlik}/maliyet").json()["kalemler"][1]
    assert motor["eksik_kodu"] == EKSIK_KUR_YOK  # sahte TCMB boş döner


def test_hedefler_ucu_ayni_adreste(istemci: TestClient) -> None:
    kimlik = _drone(istemci)
    yanit = istemci.put(f"/api/dronelar/{kimlik}/hedefler", json={"ucus_suresi_dk": 6, "yuk_g": 50})
    assert yanit.json() == {"ucus_suresi_dk": 6, "yuk_g": 50, "butce_tl": None, "itki_agirlik": None}
    assert istemci.put("/api/dronelar/999/hedefler", json={}).status_code == 404


def test_yapay_zeka_ayar_ucu_ayni_alanlarla(istemci: TestClient) -> None:
    d = istemci.get("/api/ayarlar/yapay-zeka").json()
    assert set(d) == {
        "anahtar_var", "anahtar_kaynagi", "model", "gunluk_sinir", "bugun_kullanilan", "modeller", "en_buyuk_gunluk_sinir",
    }


def test_merkezi_birim_donusumleri() -> None:
    assert BirimDonusturucu.gram_kuvvetini_newtona_cevir(1000) == pytest.approx(9.80665)
    assert BirimDonusturucu.newtonu_gram_kuvvetine_cevir(9.80665) == pytest.approx(1000)
    assert BirimDonusturucu.mah_i_ah_a_cevir(1500) == pytest.approx(1.5)
    assert BirimDonusturucu.saati_dakikaya_cevir(0.25) == pytest.approx(15)
    assert BirimDonusturucu.dakika_basinadan_saniye_basinaya_cevir(6000) == pytest.approx(100)
    assert BirimDonusturucu.mm2_yi_cm2_ye_cevir(250) == pytest.approx(2.5)
    assert BirimDonusturucu.birimi_normallestir(" MM ") == "mm"
    assert BAYT_BIR_MB == 1024 * 1024
    with pytest.raises(GecersizDegerHatasi):
        BirimDonusturucu.mah_i_ah_a_cevir(-1)


@pytest.mark.parametrize(
    ("metin", "beklenen"),
    [("DShot-600", "dshot600"), ("XT60", "xt60"), ("T-Motor F60 Pro V İnce", "tmotorf60province"), ("Çağrı", "cagri")],
)
def test_metin_sadelestirme_tek_kural(metin: str, beklenen: str) -> None:
    assert metni_sadelestir(metin) == beklenen


@pytest.mark.parametrize(("deger", "beklenen"), [(30.5, "30,5"), (4.0, "4"), (1.234, "1,23"), (None, "?")])
def test_sayi_yaz(deger: float | None, beklenen: str) -> None:
    assert sayi_yaz(deger) == beklenen


def test_eksik_zorunlu_alan_turkce_hata() -> None:
    with pytest.raises(GecersizDegerHatasi, match="Üretici, model"):
        ParcaSerilestirici.sozlukten_olustur("motor", {"model": "M"}, {})
    with pytest.raises(GecersizDegerHatasi, match="alt tür"):
        ParcaSerilestirici.sozlukten_olustur("diger", {"uretici": "U", "model": "M"}, {})


@pytest.mark.parametrize(
    "tablo",
    ["metin", [1, 2], [{"gerilim_v": 16}], [{"gerilim_v": 16, "gaz_yuzde": 50, "itki_g": 500, "bilinmeyen": 1}]],
)
def test_hatali_itki_tablosu_500_vermez(tablo: object) -> None:
    with pytest.raises(GecersizDegerHatasi, match="İtki tablosu"):
        ParcaSerilestirici.sozlukten_olustur("motor", {"uretici": "U", "model": "M"}, {"itki_tablosu": tablo})
