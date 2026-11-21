"""Drone hedefleri (uçuş süresi, yük, bütçe) ve itki tablosu girişi için testler."""

from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from arayuz.sunucu import sunucu_olustur
from cekirdek.hatalar import GecersizDegerHatasi
from drone.hedefler import DroneHedefleri

MOTOR = {"tur": "motor", "uretici": "T-Motor", "model": "F60", "agirlik_g": 33.5,
         "teknik": {"kv": 1950, "min_s": 4, "maks_s": 6, "maks_akim_a": 35}}
PERVANE = {"tur": "pervane", "uretici": "HQ", "model": "5.1x4.3x3", "agirlik_g": 4.5, "teknik": {"cap_inc": 5.1, "hatve_inc": 4.3}}
PIL = {"tur": "pil", "uretici": "CNHL", "model": "1500 6S", "agirlik_g": 240,
       "teknik": {"hucre_sayisi_s": 6, "kapasite_mah": 1500, "kimya": "lipo"}}


def test_hedef_denetimi() -> None:
    assert DroneHedefleri(yuk_g=0).yuk_g == 0  # yük sıfır olabilir
    for hatali in ({"ucus_suresi_dk": 0}, {"butce_tl": -1}, {"yuk_g": 1e9}, {"ucus_suresi_dk": "10"}):
        with pytest.raises(GecersizDegerHatasi):
            DroneHedefleri(**hatali)


@pytest.fixture
def ortam(tmp_path: Path):
    istemci = TestClient(sunucu_olustur(tmp_path / "veri", kur_getirici=lambda: b""))
    drone = istemci.post(
        "/api/dronelar", json={"ad": "Q", "baslangic_turu": "sifirdan", "drone_turu": "quadcopter", "amac": "FPV yarış"}
    ).json()["kimlik"]
    istemci.put(f"/api/dronelar/{drone}/sasi/agirlik", json={"agirlik_g": 120})
    motor = istemci.post(f"/api/dronelar/{drone}/parcalar", json={"parca": MOTOR, "adet": 4}).json()["parca_kimlik"]
    istemci.post(f"/api/dronelar/{drone}/parcalar", json={"parca": PERVANE, "adet": 4})
    pil = istemci.post(f"/api/dronelar/{drone}/parcalar", json={"parca": PIL, "adet": 1}).json()["parca_kimlik"]
    return istemci, drone, motor, pil


def _ozet(istemci: TestClient, drone: int) -> dict:
    return istemci.get(f"/api/dronelar/{drone}/elektronik").json()


def test_hedefler_kaydedilir_yuk_agirliga_eklenir(ortam) -> None:
    istemci, drone, _, _ = ortam
    once = _ozet(istemci, drone)["agirlik"]["toplam_g"]
    yanit = istemci.put(f"/api/dronelar/{drone}/hedefler", json={"ucus_suresi_dk": 60, "yuk_g": 200, "butce_tl": 5000})
    assert yanit.status_code == 200, yanit.text
    ozet = _ozet(istemci, drone)
    assert ozet["hedefler"] == {"ucus_suresi_dk": 60, "yuk_g": 200, "butce_tl": 5000, "itki_agirlik": None}
    assert ozet["agirlik"]["toplam_g"] == pytest.approx(once + 200)  # yük kablo payına katılmaz
    u = ozet["ucus"]
    assert u["hedef_ucus_suresi_dk"] == 60 and u["ucus_suresi_hedefe_ulasiyor_mu"] is False  # yarış dronu 60 dk uçamaz
    assert "+ yük" in u["toplam_agirlik_g"]["aciklama"]
    # Boş gönderilen hedef silinir.
    istemci.put(f"/api/dronelar/{drone}/hedefler", json={})
    assert _ozet(istemci, drone)["ucus"]["ucus_suresi_hedefe_ulasiyor_mu"] is None


def test_hedef_hatalari(ortam) -> None:
    istemci, drone, _, _ = ortam
    yanit = istemci.put(f"/api/dronelar/{drone}/hedefler", json={"butce_tl": -5})
    assert yanit.status_code == 400 and "Bütçe" in yanit.json()["hata"]
    assert istemci.put("/api/dronelar/999/hedefler", json={}).status_code == 404


def test_butce_maliyette_alinacaklarla_karsilastirilir(ortam) -> None:
    istemci, drone, motor, pil = ortam
    istemci.put(f"/api/dronelar/{drone}/hedefler", json={"butce_tl": 3000})
    istemci.put(f"/api/katalog/{motor}/fiyat", json={"tutar": 1000})  # 4 × 1000 = 4000
    m = istemci.get(f"/api/dronelar/{drone}/maliyet").json()
    assert m["butce_tl"] == 3000 and m["butce_kalan_tl"] == pytest.approx(-1000)
    istemci.patch(f"/api/dronelar/{drone}/parcalar/1", json={"durum": "elimde"})  # motorlar elde → harcama yok
    assert istemci.get(f"/api/dronelar/{drone}/maliyet").json()["butce_kalan_tl"] == pytest.approx(3000)


def test_itki_tablosu_kaydedilir_ve_ucus_hesabi_kullanir(ortam) -> None:
    istemci, drone, motor, _ = ortam
    assert "tahmin" in _ozet(istemci, drone)["ucus"]["toplam_itki_g"]["aciklama"]
    satirlar = [
        {"gerilim_v": 22.2, "pervane": "5.1x4.3x3", "gaz_yuzde": 50, "itki_g": 600, "akim_a": 8},
        {"gerilim_v": 22.2, "pervane": "5.1x4.3x3", "gaz_yuzde": 100, "itki_g": 1500, "akim_a": 35},
    ]
    yanit = istemci.put(f"/api/katalog/{motor}/itki-tablosu", json={"satirlar": satirlar})
    assert yanit.status_code == 200, yanit.text
    assert len(yanit.json()["teknik"]["itki_tablosu"]) == 2
    assert yanit.json()["dogrulandi"] is True  # elle girilen motorun durumu değişmedi
    u = _ozet(istemci, drone)["ucus"]
    assert u["toplam_itki_g"]["deger"] == 6000 and not u["toplam_itki_g"]["tahmini"]
    assert "itki tablosundan" in u["toplam_itki_g"]["aciklama"]
    # Boş liste tabloyu siler; hesap tahmini formüle döner.
    istemci.put(f"/api/katalog/{motor}/itki-tablosu", json={"satirlar": []})
    assert _ozet(istemci, drone)["ucus"]["toplam_itki_g"]["tahmini"] is True


def test_itki_tablosu_hatalari(ortam) -> None:
    istemci, _, motor, pil = ortam
    yanit = istemci.put(f"/api/katalog/{motor}/itki-tablosu", json={"satirlar": [{"gerilim_v": 22.2, "gaz_yuzde": 150, "itki_g": 1}]})
    assert yanit.status_code == 400 and "1. satır" in yanit.json()["hata"]
    yanit = istemci.put(f"/api/katalog/{motor}/itki-tablosu", json={"satirlar": [{"gerilim_v": 22.2}]})
    assert yanit.status_code == 400 and "zorunlu" in yanit.json()["hata"]
    yanit = istemci.put(f"/api/katalog/{pil}/itki-tablosu", json={"satirlar": []})
    assert yanit.status_code == 400 and "motor" in yanit.json()["hata"]
    assert istemci.put("/api/katalog/999/itki-tablosu", json={"satirlar": []}).status_code == 404


def test_oneri_istemine_hedefler_eklenir() -> None:
    from elektronik.oneri.istem import OneriIstemiOlusturucu
    from drone.modeller import BaslangicTuru, Drone, DroneTuru
    from elektronik.parcalar.turler import ParcaTuru

    drone = Drone(kimlik=1, ad="X", baslangic_turu=BaslangicTuru.SIFIRDAN, drone_turu=DroneTuru.QUADCOPTER,
                  amac="Yük taşıma", olusturma_zamani="", guncelleme_zamani="")
    istem = OneriIstemiOlusturucu().olustur(
        drone, [], None, ParcaTuru.MOTOR, None, hedefler=DroneHedefleri(ucus_suresi_dk=20, yuk_g=500, butce_tl=8000)
    )
    assert "en az 20 dakika" in istem and "500 g" in istem and "8000 TL" in istem
