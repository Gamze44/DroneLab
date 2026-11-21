"""sasi/birim_dogrulayici.py için testler."""

import pytest

from cekirdek.hatalar import BirimHatasi
from sasi.birim_dogrulayici import BirimDogrulayici
from sasi.modeller import GeometriTuru, OneriKaynagi, SasiGeometrisi


def _kati(olculer: tuple[float, float, float], birim: str | None = None, hacim: float = 1.0) -> SasiGeometrisi:
    """Test için katı geometri oluşturur."""
    return SasiGeometrisi(dosya_adi="t.stl", tur=GeometriTuru.KATI, olculer=olculer, dosya_birimi=birim, hacim=hacim)


@pytest.mark.parametrize(
    ("olculer", "beklenen"),
    [
        ((250, 250, 40), "mm"),  # tipik 5 inç yarış şasisi mm ile çizilmiş
        ((25, 25, 4), "cm"),  # aynı şasi cm ile çizilmiş
        ((0.25, 0.25, 0.04), "m"),  # aynı şasi m ile çizilmiş
    ],
)
def test_birim_yoksa_olcuye_gore_tahmin_edilir(olculer: tuple[float, float, float], beklenen: str) -> None:
    """Birim bilgisi olmayan dosyada ölçüleri makul yapan birim önerilmeli."""
    oneri = BirimDogrulayici().birim_oner(_kati(olculer))
    assert oneri.birim == beklenen
    assert oneri.kaynak is OneriKaynagi.TAHMIN


def test_dosyadaki_makul_birim_kullanilir() -> None:
    """Dosyada yazan birim ölçülerle uyumluysa önerilmeli."""
    oneri = BirimDogrulayici().birim_oner(_kati((10, 10, 2), birim="inch"))
    assert oneri.birim == "inch"
    assert oneri.kaynak is OneriKaynagi.DOSYA


def test_dosyadaki_birim_makul_degilse_tahmin_onerilir() -> None:
    """ezdxf gibi araçlar varsayılan olarak 'm' yazar; 250 m şasi olamaz -> mm önerilmeli."""
    oneri = BirimDogrulayici().birim_oner(_kati((250, 250, 40), birim="m"))
    assert oneri.birim == "mm"
    assert oneri.kaynak is OneriKaynagi.TAHMIN
    assert "alışılmadık" in oneri.aciklama


def test_hicbir_birim_uymuyorsa_varsayilan_ve_uyari() -> None:
    """Çok küçük ölçülerde de bir öneri dönmeli ve dikkat istenmeli."""
    oneri = BirimDogrulayici().birim_oner(_kati((0.001, 0.001, 0.001)))
    assert oneri.birim == "mm"
    assert "dikkatle" in oneri.aciklama


def test_cm_onayi_hacmi_1000_kat_buyutur() -> None:
    """cm ile çizilmiş 25×25×4 kutu: ölçüler 10, hacim 1000 kat büyümeli."""
    sonuc = BirimDogrulayici().olculeri_mm_ye_cevir(_kati((25, 25, 4), hacim=2500), "cm")
    assert (sonuc.en_mm, sonuc.boy_mm, sonuc.yukseklik_mm) == pytest.approx((250, 250, 40))
    assert sonuc.hacim_mm3 == pytest.approx(2_500_000)
    assert sonuc.alan_mm2 is None
    assert sonuc.uyarilar == []


def test_levha_alani_kareyle_cevrilir() -> None:
    """Levhada alan birimin karesiyle çevrilmeli, hacim olmamalı."""
    g = SasiGeometrisi(dosya_adi="l.dxf", tur=GeometriTuru.LEVHA, olculer=(20, 10, 0), alan=150)
    sonuc = BirimDogrulayici().olculeri_mm_ye_cevir(g, "cm")
    assert sonuc.alan_mm2 == pytest.approx(15000)
    assert sonuc.hacim_mm3 is None


def test_makul_olmayan_onay_uyari_ekler() -> None:
    """Kullanıcı yanlış birim seçerse (250 mm'lik şasiye m) uyarı en başta görünmeli."""
    sonuc = BirimDogrulayici().olculeri_mm_ye_cevir(_kati((250, 250, 40)), "m")
    assert "alışılmadık" in sonuc.uyarilar[0]


def test_tanimsiz_birim_hata_verir() -> None:
    """Tanınmayan birim BirimHatasi vermeli."""
    with pytest.raises(BirimHatasi):
        BirimDogrulayici().olculeri_mm_ye_cevir(_kati((1, 1, 1)), "ayak")
