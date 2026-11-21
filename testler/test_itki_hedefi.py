"""
Drone başına itki/ağırlık hedefi: doğrulama, kayıt, uçuş hesabına etkisi ve asistan değişikliği.
Gerçek veritabanına dokunulmaz (geçici klasör).
"""

from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from arayuz.sunucu import sunucu_olustur
from asistan.senaryo import Degisiklik
from cekirdek.hatalar import GecersizDegerHatasi
from drone.hedefler import DroneHedefleri
from elektronik.hesap.katsayilar import HEDEF_ITKI_AGIRLIK

FREESTYLE = "Serbest uçuş (freestyle)"
YENI_DRONE = {"ad": "Freestyle", "baslangic_turu": "sifirdan", "drone_turu": "quadcopter", "amac": FREESTYLE}


@pytest.mark.parametrize("deger", [0.5, 1.0, 31.0, float("nan")])
def test_gecersiz_itki_hedefi_reddedilir(deger: float) -> None:
    with pytest.raises(GecersizDegerHatasi, match="İtki/ağırlık"):
        DroneHedefleri(itki_agirlik=deger)


def test_gecerli_itki_hedefi_kabul_edilir() -> None:
    assert DroneHedefleri(itki_agirlik=2).itki_agirlik == 2


def _ucus(istemci: TestClient, kimlik: int) -> dict:
    return istemci.get(f"/api/dronelar/{kimlik}/elektronik").json()["ucus"]


def test_drone_hedefi_amac_varsayilaninin_yerine_gecer(tmp_path: Path) -> None:
    veri = tmp_path / "veri"
    istemci = TestClient(sunucu_olustur(veri, kur_getirici=lambda: b""))
    kimlik = istemci.post("/api/dronelar", json=YENI_DRONE).json()["kimlik"]

    u = _ucus(istemci, kimlik)
    assert u["hedef_itki_agirlik"] == HEDEF_ITKI_AGIRLIK[FREESTYLE]
    assert not u["hedef_itki_agirlik_elle_mi"] and u["amac_hedef_itki_agirlik"] == HEDEF_ITKI_AGIRLIK[FREESTYLE]

    yanit = istemci.put(f"/api/dronelar/{kimlik}/hedefler", json={"itki_agirlik": 2})
    assert yanit.status_code == 200 and yanit.json()["itki_agirlik"] == 2
    u = _ucus(istemci, kimlik)
    assert u["hedef_itki_agirlik"] == 2 and u["hedef_itki_agirlik_elle_mi"]

    # Program yeniden açılınca da korunur.
    yeni = TestClient(sunucu_olustur(veri, kur_getirici=lambda: b""))
    assert _ucus(yeni, kimlik)["hedef_itki_agirlik"] == 2
    assert yeni.get(f"/api/dronelar/{kimlik}/elektronik").json()["hedefler"]["itki_agirlik"] == 2

    # Boş bırakınca amaca göre varsayılana döner; geçersiz değer Türkçe reddedilir.
    istemci.put(f"/api/dronelar/{kimlik}/hedefler", json={"itki_agirlik": None})
    assert _ucus(istemci, kimlik)["hedef_itki_agirlik"] == HEDEF_ITKI_AGIRLIK[FREESTYLE]
    yanit = istemci.put(f"/api/dronelar/{kimlik}/hedefler", json={"itki_agirlik": 1})
    assert yanit.status_code == 400 and "kalkamaz" in yanit.json()["hata"] and "girilen: 1)" in yanit.json()["hata"]


def test_asistan_itki_hedefi_degisikligi_onerebilir() -> None:
    d = Degisiklik.sozlukten({"islem": "hedef_degistir", "itki_agirlik": 3})
    assert d.itki_agirlik == 3 and d.sozluk() == {"islem": "hedef_degistir", "itki_agirlik": 3}
