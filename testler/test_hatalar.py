"""cekirdek/hatalar.py için testler."""

from cekirdek.hatalar import BirimHatasi, DroneProgramHatasi, GecersizDegerHatasi


def test_tum_hatalar_temel_siniftan_turer() -> None:
    """Arayüz tek bir temel sınıfı yakalayabilsin diye tüm hatalar ondan türemeli."""
    assert issubclass(GecersizDegerHatasi, DroneProgramHatasi)
    assert issubclass(BirimHatasi, DroneProgramHatasi)


def test_birim_hatasi_mesaji_birimleri_listeler() -> None:
    """Mesaj, hatalı birimi ve kullanılabilecek birimleri içermeli."""
    hata = BirimHatasi("ayak", ["mm", "cm"])
    assert "ayak" in hata.mesaj
    assert "mm, cm" in hata.mesaj
    assert str(hata) == hata.mesaj
