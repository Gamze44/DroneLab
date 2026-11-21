"""sasi/konturlar.py için testler."""

import pytest

from sasi.konturlar import KonturAlanHesaplayici, KonturBirlestirici

KARE_10 = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]


def _kare(x: float, y: float, kenar: float) -> list[tuple[float, float]]:
    """Sol alt köşesi (x, y) olan kare konturu."""
    return [(x, y), (x + kenar, y), (x + kenar, y + kenar), (x, y + kenar)]


def test_isaretli_alan_yone_gore_isaret_degistirir() -> None:
    """Saat yönünün tersi pozitif, saat yönü negatif alan vermeli."""
    assert KonturAlanHesaplayici.isaretli_alan(KARE_10) == pytest.approx(100)
    assert KonturAlanHesaplayici.isaretli_alan(list(reversed(KARE_10))) == pytest.approx(-100)


def test_nokta_icinde_mi() -> None:
    """Merkez içeride, dışarıdaki nokta dışarıda olmalı."""
    assert KonturAlanHesaplayici.nokta_icinde_mi((5, 5), KARE_10)
    assert not KonturAlanHesaplayici.nokta_icinde_mi((15, 5), KARE_10)


def test_delik_ve_ada() -> None:
    """Dış kare - delik + deliğin içindeki ada: 10000 - 3600 + 400."""
    konturlar = [_kare(0, 0, 100), _kare(20, 20, 60), _kare(40, 40, 20)]
    ozet = KonturAlanHesaplayici().hesapla(konturlar)
    assert ozet.net_alan == pytest.approx(10000 - 3600 + 400)
    assert ozet.dis_kontur_sayisi == 1
    assert ozet.delik_sayisi == 1


def test_yan_yana_iki_dis_parca() -> None:
    """Birbirinin içinde olmayan iki kare iki dış parça sayılmalı."""
    ozet = KonturAlanHesaplayici().hesapla([_kare(0, 0, 10), _kare(50, 0, 10)])
    assert ozet.net_alan == pytest.approx(200)
    assert ozet.dis_kontur_sayisi == 2
    assert ozet.delik_sayisi == 0


def test_birlestirici_ters_yonlu_parcalari_baglar() -> None:
    """Farklı yönlerde çizilmiş dört kenar tek kapalı konturda birleşmeli."""
    parcalar = [
        [(0.0, 0.0), (10.0, 0.0)],
        [(10.0, 10.0), (10.0, 0.0)],  # ters
        [(10.0, 10.0), (0.0, 10.0)],
        [(0.0, 0.0), (0.0, 10.0)],  # ters
    ]
    konturlar, kapanmayan = KonturBirlestirici(tolerans=1e-6).birlestir(parcalar)
    assert kapanmayan == 0
    assert len(konturlar) == 1
    assert abs(KonturAlanHesaplayici.isaretli_alan(konturlar[0])) == pytest.approx(100)


def test_birlestirici_tolerans_icindeki_boslugu_kapatir() -> None:
    """Uçlar arasında tolerans altında boşluk varsa yine birleşmeli."""
    parcalar = [[(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)], [(10.0, 10.0001), (0.0, 10.0), (0.0, 0.0001)]]
    konturlar, kapanmayan = KonturBirlestirici(tolerans=0.001).birlestir(parcalar)
    assert (len(konturlar), kapanmayan) == (1, 0)


def test_birlestirici_kapanmayan_zinciri_sayar() -> None:
    """Kapanmayan bir zincir sayılmalı, kontur üretmemeli."""
    konturlar, kapanmayan = KonturBirlestirici(tolerans=1e-6).birlestir([[(0.0, 0.0), (10.0, 0.0)]])
    assert konturlar == []
    assert kapanmayan == 1
