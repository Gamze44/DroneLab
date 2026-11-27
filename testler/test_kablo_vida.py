"""
Drone başına tartılmış kablo/vida ağırlığı: hesap, doğrulama, kayıt, uçuş hesabına etkisi,
eski veritabanının yükseltilmesi ve asistan değişikliği. Gerçek veritabanına dokunulmaz (geçici klasör).
"""

from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient
import pytest

from arayuz.sunucu import sunucu_olustur
from asistan.senaryo import Degisiklik
from cekirdek.hatalar import GecersizDegerHatasi
from depolama.veritabani import SEMA_SURUMU, Veritabani
from drone.hedefler import DroneHedefleri
from elektronik.hesap.agirlik import AgirlikHesaplayici
from elektronik.parcalar.cekirdek_parcalar import Motor

YENI_DRONE = {"ad": "Vidalı", "baslangic_turu": "sifirdan", "drone_turu": "quadcopter", "amac": "FPV yarış"}
MOTOR = {"tur": "motor", "uretici": "M", "model": "2207", "agirlik_g": 30}


def _kalemler() -> list:
    return [(Motor(uretici="M", model="1", agirlik_g=50), 4)]


def test_tartilmis_deger_tahmini_payin_yerine_gecer() -> None:
    o = AgirlikHesaplayici(kablo_payi_orani=0.05).hesapla(sasi_g=100, kalemler=_kalemler(), yuk_g=20, kablo_vida_g=42)
    assert o.kablo_payi_g == 42 and o.kablo_payi_elle_mi
    assert o.toplam_g == pytest.approx(100 + 200 + 20 + 42)
    assert not o.tahmini  # tartılmış değer tahmin değildir


def test_bos_birakilinca_oranla_tahmin_edilir() -> None:
    o = AgirlikHesaplayici(kablo_payi_orani=0.05).hesapla(sasi_g=100, kalemler=_kalemler())
    assert o.kablo_payi_g == pytest.approx(15) and not o.kablo_payi_elle_mi and o.tahmini


def test_sifir_girilebilir() -> None:
    o = AgirlikHesaplayici(kablo_payi_orani=0.05).hesapla(sasi_g=100, kalemler=_kalemler(), kablo_vida_g=0)
    assert o.kablo_payi_g == 0 and o.kablo_payi_elle_mi and o.toplam_g == pytest.approx(300)


@pytest.mark.parametrize("deger", [-1, 20_000, float("nan")])
def test_gecersiz_kablo_vida_reddedilir(deger: float) -> None:
    with pytest.raises(GecersizDegerHatasi, match="Kablo ve vida"):
        DroneHedefleri(kablo_vida_g=deger)


def test_api_kaydeder_hesaba_yansitir_ve_korur(tmp_path: Path) -> None:
    veri = tmp_path / "veri"
    istemci = TestClient(sunucu_olustur(veri, kur_getirici=lambda: b""))
    kimlik = istemci.post("/api/dronelar", json=YENI_DRONE).json()["kimlik"]
    istemci.put(f"/api/dronelar/{kimlik}/sasi/agirlik", json={"agirlik_g": 100})
    istemci.post(f"/api/dronelar/{kimlik}/parcalar", json={"parca": MOTOR, "adet": 4})

    adres = f"/api/dronelar/{kimlik}/elektronik"
    a = istemci.get(adres).json()["agirlik"]
    assert not a["kablo_payi_elle_mi"] and a["kablo_payi_g"] > 0 and a["tahmini"]
    tahmini_toplam = a["toplam_g"]

    yanit = istemci.put(f"/api/dronelar/{kimlik}/hedefler", json={"kablo_vida_g": 35})
    assert yanit.status_code == 200 and yanit.json()["kablo_vida_g"] == 35
    o = istemci.get(adres).json()
    assert o["agirlik"]["kablo_payi_g"] == 35 and o["agirlik"]["kablo_payi_elle_mi"]
    assert o["agirlik"]["toplam_g"] == pytest.approx(100 + 120 + 35)
    assert o["ucus"]["toplam_agirlik_g"]["deger"] == pytest.approx(o["agirlik"]["toplam_g"])
    assert o["agirlik"]["toplam_g"] != tahmini_toplam

    # Program yeniden açılınca da korunur; boş bırakılınca tahmine döner.
    yeni = TestClient(sunucu_olustur(veri, kur_getirici=lambda: b""))
    assert yeni.get(adres).json()["hedefler"]["kablo_vida_g"] == 35
    yeni.put(f"/api/dronelar/{kimlik}/hedefler", json={"kablo_vida_g": None})
    assert yeni.get(adres).json()["agirlik"]["toplam_g"] == pytest.approx(tahmini_toplam)

    yanit = istemci.put(f"/api/dronelar/{kimlik}/hedefler", json={"kablo_vida_g": -5})
    assert yanit.status_code == 400 and "Kablo ve vida ağırlığı eksi olamaz" in yanit.json()["hata"]


def test_eski_veritabani_yukseltilir_ve_hedefler_korunur(tmp_path: Path) -> None:
    yol = tmp_path / "eski.sqlite3"
    Veritabani(yol)
    with sqlite3.connect(yol) as bag:
        # Sürüm 9'daki duruma geri dön: yeni sütun yok, eski hedef kaydı var.
        bag.execute("PRAGMA foreign_keys = OFF")
        bag.execute("ALTER TABLE drone_hedefleri DROP COLUMN kablo_vida_g")
        bag.execute("INSERT INTO drone_hedefleri (drone_kimlik, yuk_g) VALUES (1, 80)")
        bag.execute("PRAGMA user_version = 9")
    Veritabani(yol)
    with sqlite3.connect(yol) as bag:
        assert bag.execute("PRAGMA user_version").fetchone()[0] == SEMA_SURUMU == 10
        assert bag.execute("SELECT yuk_g, kablo_vida_g FROM drone_hedefleri").fetchone() == (80, None)


def test_asistan_kablo_vida_degisikligi_onerebilir() -> None:
    d = Degisiklik.sozlukten({"islem": "hedef_degistir", "kablo_vida_g": 40})
    assert d.kablo_vida_g == 40 and d.sozluk() == {"islem": "hedef_degistir", "kablo_vida_g": 40}
