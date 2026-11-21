"""sasi/okuyucu_secici.py için testler."""

import pytest

from cekirdek.hatalar import DesteklenmeyenDosyaHatasi
from sasi.okuyucu_secici import OkuyucuSecici
from sasi.okuyucular.ag_okuyucu import AgOkuyucu
from sasi.okuyucular.dxf_okuyucu import DxfOkuyucu


@pytest.mark.parametrize(
    ("ad", "sinif"),
    [("a.stl", AgOkuyucu), ("A.STL", AgOkuyucu), ("b.obj", AgOkuyucu), ("c.3mf", AgOkuyucu), ("d.dxf", DxfOkuyucu)],
)
def test_uzantiya_gore_okuyucu_secilir(ad: str, sinif: type) -> None:
    """Uzantı büyük/küçük harf fark etmeksizin doğru okuyucuya gitmeli."""
    assert isinstance(OkuyucuSecici().sec(ad), sinif)


def test_yerel_format_rehberle_reddedilir() -> None:
    """SolidWorks dosyası okunamaz; mesaj programı anmalı ve rehber dönmeli."""
    with pytest.raises(DesteklenmeyenDosyaHatasi) as bilgi:
        OkuyucuSecici().sec("govde.SLDPRT")
    assert "SolidWorks" in bilgi.value.mesaj
    assert len(bilgi.value.rehber) > 0


def test_step_sonraki_surume_yonlendirilir() -> None:
    """STEP henüz desteklenmiyor; kullanıcı STL/3MF'ye yönlendirilmeli."""
    with pytest.raises(DesteklenmeyenDosyaHatasi, match="STEP"):
        OkuyucuSecici().sec("sasi.step")


def test_bilinmeyen_uzanti_desteklenenleri_listeler() -> None:
    """Bilinmeyen uzantıda desteklenen türler mesajda yazmalı."""
    with pytest.raises(DesteklenmeyenDosyaHatasi, match=r"\.stl"):
        OkuyucuSecici().sec("resim.png")
