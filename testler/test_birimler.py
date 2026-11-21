"""cekirdek/birimler.py için testler."""

import math

import pytest

from cekirdek.birimler import BirimDonusturucu
from cekirdek.hatalar import BirimHatasi, GecersizDegerHatasi


def test_uzunluk_mm_ye_cevrilir() -> None:
    """cm, m ve inch değerleri doğru mm karşılığına çevrilmeli."""
    assert BirimDonusturucu.uzunlugu_mm_ye_cevir(25, "cm") == 250
    assert BirimDonusturucu.uzunlugu_mm_ye_cevir(0.25, "m") == 250
    assert BirimDonusturucu.uzunlugu_mm_ye_cevir(1, "inch") == 25.4


def test_uzunluk_geri_donusumu() -> None:
    """mm'ye çevrilip geri çevrilen değer aynı kalmalı."""
    mm = BirimDonusturucu.uzunlugu_mm_ye_cevir(3.5, "cm")
    assert math.isclose(BirimDonusturucu.mm_yi_uzunluga_cevir(mm, "cm"), 3.5)


def test_birim_buyuk_harf_ve_bosluk_kabul_edilir() -> None:
    """Kullanıcı ' CM ' yazsa da birim tanınmalı."""
    assert BirimDonusturucu.uzunlugu_mm_ye_cevir(1, " CM ") == 10


def test_negatif_uzunluk_kabul_edilir() -> None:
    """Koordinatlar negatif olabileceği için negatif uzunluk hata vermemeli."""
    assert BirimDonusturucu.uzunlugu_mm_ye_cevir(-2, "cm") == -20


def test_hacim_carpani_kup_alir() -> None:
    """cm ile çizilmiş bir parçada hacim 1000 kat büyümeli."""
    assert BirimDonusturucu.hacim_carpani("cm") == 1000
    assert BirimDonusturucu.hacmi_mm3_e_cevir(2, "cm") == 2000


def test_alan_carpani_kare_alir() -> None:
    """cm ile çizilmiş levhada alan 100 kat büyümeli."""
    assert BirimDonusturucu.alani_mm2_ye_cevir(3, "cm") == 300


def test_mm3_cm3_donusumu() -> None:
    """1000 mm3 = 1 cm3."""
    assert BirimDonusturucu.mm3_u_cm3_e_cevir(1000) == 1


def test_kutle_donusumleri() -> None:
    """kg ile gram arasında doğru dönüşüm yapılmalı."""
    assert BirimDonusturucu.kutleyi_grama_cevir(1.5, "kg") == 1500
    assert BirimDonusturucu.grami_kutleye_cevir(2150, "kg") == 2.15


def test_yogunluk_donusumu() -> None:
    """1240 kg/m3 (PLA) = 1.24 g/cm3."""
    assert math.isclose(BirimDonusturucu.yogunlugu_g_cm3_e_cevir(1240, "kg/m3"), 1.24)


def test_tanimsiz_birim_hata_verir() -> None:
    """Tanınmayan birim Türkçe mesajlı BirimHatasi vermeli."""
    with pytest.raises(BirimHatasi) as bilgi:
        BirimDonusturucu.uzunlugu_mm_ye_cevir(1, "ayak")
    assert "tanınmıyor" in bilgi.value.mesaj


@pytest.mark.parametrize("deger", [-1, float("nan"), float("inf")])
def test_gecersiz_kutle_hata_verir(deger: float) -> None:
    """Negatif, NaN veya sonsuz kütle reddedilmeli."""
    with pytest.raises(GecersizDegerHatasi):
        BirimDonusturucu.kutleyi_grama_cevir(deger, "g")


def test_sayi_olmayan_deger_hata_verir() -> None:
    """Metin gibi sayı olmayan değer reddedilmeli."""
    with pytest.raises(GecersizDegerHatasi):
        BirimDonusturucu.uzunlugu_mm_ye_cevir("10", "mm")  # type: ignore[arg-type]
