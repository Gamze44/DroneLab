"""drone/dogrulama.py için testler."""

import pytest

from cekirdek.hatalar import GecersizDegerHatasi
from drone.dogrulama import AD_EN_FAZLA_UZUNLUK, DroneGirdisiDogrulayici
from drone.modeller import KULLANIM_AMACLARI

D = DroneGirdisiDogrulayici


def test_ad_bosluklari_temizlenir() -> None:
    assert D.ad_dogrula("  Yarış 5 inç  ") == "Yarış 5 inç"


@pytest.mark.parametrize("ad", ["", "   ", "x" * (AD_EN_FAZLA_UZUNLUK + 1)])
def test_gecersiz_ad(ad: str) -> None:
    with pytest.raises(GecersizDegerHatasi):
        D.ad_dogrula(ad)


def test_amac_listede_olmali() -> None:
    assert D.amac_dogrula(KULLANIM_AMACLARI[0]) == KULLANIM_AMACLARI[0]
    with pytest.raises(GecersizDegerHatasi):
        D.amac_dogrula("Uzaya gitmek")


def test_agirlik() -> None:
    assert D.agirlik_dogrula(None) is None
    assert D.agirlik_dogrula(85) == 85.0
    for gecersiz in (0, -5, float("nan"), float("inf")):
        with pytest.raises(GecersizDegerHatasi):
            D.agirlik_dogrula(gecersiz)
