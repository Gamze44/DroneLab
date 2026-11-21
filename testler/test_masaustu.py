"""Masaüstü başlatıcısı ve simge üretimi için testler (pencere açılmaz)."""

from pathlib import Path
import struct
import urllib.request

from araclar.simge_olustur import BOYUTLAR, ico_yaz, png_yaz, simge_ciz
from arayuz.sunucu import sunucu_olustur
from cekirdek.ayarlar import PROGRAM_ADI, SIMGE_YOLU
from fastapi.testclient import TestClient
from masaustu import YerelSunucu, bos_port_bul, renk_kodu


def test_sayfalarda_program_adi_ayardan_gelir(tmp_path: Path) -> None:
    """Sayfalarda ad elle yazılmaz; yer tutucular ayardaki değerle doldurulur."""
    istemci = TestClient(sunucu_olustur(tmp_path / "veri", kur_getirici=lambda: b""))
    for adres in ("/", "/ayarlar", "/drone/1"):
        html = istemci.get(adres).text
        assert "{{" not in html, f"{adres}: doldurulmamış yer tutucu var"
        assert f"<title>{PROGRAM_ADI}" in html or f"– {PROGRAM_ADI}</title>" in html
        assert SIMGE_YOLU.name in html
    assert PROGRAM_ADI.upper() in istemci.get("/").text  # üst etiket
    assert istemci.get(f"/statik/{SIMGE_YOLU.name}").status_code == 200


def test_renk_kodu_windows_bicimi() -> None:
    """Windows renkleri 0x00BBGGRR biçimindedir (kırmızı en düşük baytta)."""
    assert renk_kodu("#ff0000") == 0x0000FF
    assert renk_kodu("#0b111c") == 0x1C110B
    assert renk_kodu("22d3ee") == 0xEED322

PNG_IMZASI = b"\x89PNG\r\n\x1a\n"


def test_simge_cizimi_ve_png() -> None:
    resim = simge_ciz(32)
    assert resim.shape == (32, 32, 4)
    assert resim[0, 0, 3] == 0  # yuvarlatılmış köşe saydam
    assert resim[16, 16, 3] == 255  # orta dolu
    png = png_yaz(resim)
    assert png.startswith(PNG_IMZASI)
    assert struct.unpack(">II", png[16:24]) == (32, 32)


def test_ico_basligi_ve_girdileri() -> None:
    ico = ico_yaz()
    ayrilmis, tur, adet = struct.unpack("<HHH", ico[:6])
    assert (ayrilmis, tur, adet) == (0, 1, len(BOYUTLAR))
    for sira, boyut in enumerate(BOYUTLAR):
        g, y, _, _, _, bit, uzunluk, konum = struct.unpack("<BBBBHHII", ico[6 + 16 * sira: 22 + 16 * sira])
        assert g == boyut % 256 and bit == 32
        assert ico[konum: konum + 8] == PNG_IMZASI and konum + uzunluk <= len(ico)


def test_proje_simgesi_mevcut() -> None:
    assert SIMGE_YOLU.read_bytes()[:4] == b"\x00\x00\x01\x00"


def test_yerel_sunucu_baslar_ve_durur(tmp_path: Path) -> None:
    port = bos_port_bul()
    sunucu = YerelSunucu(port, sunucu_olustur(tmp_path / "veri", kur_getirici=lambda: b""))
    sunucu.baslat()
    try:
        with urllib.request.urlopen(sunucu.adres + "/", timeout=5) as yanit:
            assert yanit.status == 200 and PROGRAM_ADI.encode() in yanit.read()
    finally:
        sunucu.durdur()
    assert not sunucu._is_parcacigi.is_alive()
