"""
Şasi biriminin önerilmesi ve doğrulanması.

Yanlış birim ağırlığı 1000 kata kadar bozabilir (cm ile çizilmiş bir parça mm
sanılırsa hacim 1000 kat küçük çıkar). Bu yüzden program bir birim önerir ama
son kararı her zaman kullanıcıya bırakır. Öneri, ölçülerin bir drone şasisi
için makul aralıkta olup olmadığına bakılarak yapılır.
"""

from typing import Final

from cekirdek.birimler import BirimDonusturucu
from sasi.modeller import BirimOnerisi, GeometriTuru, OneriKaynagi, SasiGeometrisi, SasiOlculeri

# DEĞİŞTİRİLEBİLİR: Bir drone şasisinin en büyük ölçüsü için makul aralık (mm).
# Küçük "tiny whoop" şasiler ~65 mm, büyük taşıyıcı droneler ~1500 mm civarındadır.
MAKUL_EN_KUCUK_MM: Final[float] = 50.0
MAKUL_EN_BUYUK_MM: Final[float] = 2000.0

# DEĞİŞTİRİLEBİLİR: Birim tahmin edilirken denenecek birimler, tercih sırasıyla.
# inch yalnızca dosyada yazıyorsa önerilir; cm ile karışması kolay olduğu için tahmin edilmez.
TAHMIN_SIRASI: Final[tuple[str, ...]] = ("mm", "cm", "m")

VARSAYILAN_BIRIM: Final[str] = "mm"


class BirimDogrulayici:
    """Dosya birimini önerir ve onaylanan birimle ölçüleri mm'ye çevirir."""

    @staticmethod
    def makul_mu(en_buyuk_olcu_mm: float) -> bool:
        """
        Şasinin en büyük ölçüsünün bir drone için makul olup olmadığını döndürür.

        Parametreler:
            en_buyuk_olcu_mm: En büyük ölçü, mm.
        Dönüş:
            Makul aralıktaysa True.
        """
        return MAKUL_EN_KUCUK_MM <= en_buyuk_olcu_mm <= MAKUL_EN_BUYUK_MM

    def birim_oner(self, geometri: SasiGeometrisi) -> BirimOnerisi:
        """
        Kullanıcıya onay için bir birim önerir.

        Önce dosyada yazan birime bakılır; ölçüler o birimle makulse o önerilir.
        Değilse (veya birim yoksa) ölçüleri makul yapan ilk birim tahmin edilir.

        Parametreler:
            geometri: Okunan şasi geometrisi.
        Dönüş:
            BirimOnerisi.
        """
        en_buyuk = max(geometri.olculer)
        dosya_birimi = geometri.dosya_birimi

        if dosya_birimi is not None:
            mm = en_buyuk * BirimDonusturucu.uzunluk_carpani(dosya_birimi)
            if self.makul_mu(mm):
                return BirimOnerisi(
                    birim=dosya_birimi,
                    kaynak=OneriKaynagi.DOSYA,
                    aciklama=f"Birim dosyada '{dosya_birimi}' olarak belirtilmiş.",
                )

        for aday in TAHMIN_SIRASI:
            mm = en_buyuk * BirimDonusturucu.uzunluk_carpani(aday)
            if self.makul_mu(mm):
                return BirimOnerisi(
                    birim=aday,
                    kaynak=OneriKaynagi.TAHMIN,
                    aciklama=self._tahmin_aciklamasi(dosya_birimi, aday, mm),
                )

        return BirimOnerisi(
            birim=dosya_birimi or VARSAYILAN_BIRIM,
            kaynak=OneriKaynagi.TAHMIN,
            aciklama="Ölçüler hiçbir birimle tipik bir drone boyutuna uymuyor; lütfen birimi dikkatle seçin.",
        )

    @staticmethod
    def _tahmin_aciklamasi(dosya_birimi: str | None, aday: str, mm: float) -> str:
        """Tahmin edilen birim için kullanıcıya gösterilecek açıklamayı oluşturur."""
        boyut = f"en büyük ölçü {mm:.0f} mm olur"
        if dosya_birimi is None:
            return f"Dosyada birim bilgisi yok. '{aday}' seçilirse {boyut}; bu bir drone için makul."
        return (
            f"Dosyada birim '{dosya_birimi}' yazıyor, ancak bu birimle ölçüler bir drone için alışılmadık. "
            f"'{aday}' seçilirse {boyut}. Hangisinin doğru olduğunu kontrol edin."
        )

    def olculeri_mm_ye_cevir(self, geometri: SasiGeometrisi, birim: str) -> SasiOlculeri:
        """
        Kullanıcının onayladığı birimle ölçüleri, hacmi ve alanı mm cinsine çevirir.

        Parametreler:
            geometri: Okunan şasi geometrisi (dosya biriminde).
            birim: Kullanıcının onayladığı birim.
        Dönüş:
            SasiOlculeri (mm, mm2, mm3).
        Hatalar:
            BirimHatasi: Birim tanınmıyorsa.
        """
        en, boy, yukseklik = (BirimDonusturucu.uzunlugu_mm_ye_cevir(d, birim) for d in geometri.olculer)
        uyarilar = list(geometri.uyarilar)

        en_buyuk = max(en, boy, yukseklik)
        if not self.makul_mu(en_buyuk):
            uyarilar.insert(
                0,
                f"Seçilen '{birim}' birimiyle şasinin en büyük ölçüsü {en_buyuk:.1f} mm çıkıyor. "
                "Bu bir drone şasisi için alışılmadık; birimi kontrol edin.",
            )

        hacim_mm3 = None
        alan_mm2 = None
        if geometri.tur is GeometriTuru.KATI and geometri.hacim is not None:
            hacim_mm3 = BirimDonusturucu.hacmi_mm3_e_cevir(geometri.hacim, birim)
        if geometri.tur is GeometriTuru.LEVHA and geometri.alan is not None:
            alan_mm2 = BirimDonusturucu.alani_mm2_ye_cevir(geometri.alan, birim)

        return SasiOlculeri(
            birim=birim,
            en_mm=en,
            boy_mm=boy,
            yukseklik_mm=yukseklik,
            hacim_mm3=hacim_mm3,
            alan_mm2=alan_mm2,
            uyarilar=uyarilar,
        )
