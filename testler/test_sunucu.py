"""arayuz/sunucu.py için testler."""

from pathlib import Path

from fastapi.testclient import TestClient

from arayuz.sunucu import ANA_SAYFA_DOSYASI, DRONE_SAYFASI_DOSYASI, sunucu_olustur
from cekirdek.ayarlar import STATIK_KLASORU


def test_sayfa_dosyalari_var() -> None:
    """Ana sayfa ve drone sayfası statik klasörde bulunmalı."""
    assert (STATIK_KLASORU / ANA_SAYFA_DOSYASI).is_file()
    assert (STATIK_KLASORU / DRONE_SAYFASI_DOSYASI).is_file()


def test_sayfalar_ve_betikler_sunulur(tmp_path: Path) -> None:
    """Ana sayfa, drone sayfası ve tüm betikler 200 dönmeli."""
    istemci = TestClient(sunucu_olustur(tmp_path))
    for adres in ("/", "/drone/1", "/statik/ortak.js", "/statik/ana_sayfa.js",
                  "/statik/drone.js", "/statik/sasi.js", "/statik/stil.css"):
        assert istemci.get(adres).status_code == 200, adres


def test_veritabani_veri_klasorunde_olusur(tmp_path: Path) -> None:
    """Sunucu açılınca veritabanı dosyası verilen klasörde oluşmalı (gerçek veri/ klasörüne değil)."""
    sunucu_olustur(tmp_path)
    assert (tmp_path / "dronelar.sqlite3").is_file()
