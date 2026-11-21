"""
Kullanıcının drone için girdiği bilgilerin doğrulanması.

Hatalı girişler veritabanına yazılmadan önce burada yakalanır ve kullanıcıya
Türkçe, ne yapması gerektiğini anlatan bir mesaj döner.
"""

from typing import Final

from cekirdek.hatalar import GecersizDegerHatasi
from cekirdek.sayilar import EN_BUYUK_GIRDI_DEGERI, gecerli_sayi_mi
from drone.modeller import KULLANIM_AMACLARI
from sasi.modeller import PARCA_ROLU_ADLARI, ParcaRolu

# DEĞİŞTİRİLEBİLİR: Drone adının en fazla karakter sayısı.
AD_EN_FAZLA_UZUNLUK: Final[int] = 80
# DEĞİŞTİRİLEBİLİR: Dingil mesafesi (çapraz motor–motor) için kabul edilen aralık, mm.
# En küçük tiny whoop ~65 mm, büyük taşıyıcılar ~1500 mm; yazım hatalarını (ör. 2950) yakalamak için.
DINGIL_EN_KUCUK_MM: Final[float] = 20.0
DINGIL_EN_BUYUK_MM: Final[float] = 3000.0
# DEĞİŞTİRİLEBİLİR: Parçalı şaside bir parçanın en çok adedi (ör. 8 kollu bir oktokopterde
# 16 vida tutucu); daha büyük değer büyük olasılıkla yazım hatasıdır.
EN_FAZLA_PARCA_ADEDI: Final[int] = 64


class DroneGirdisiDogrulayici:
    """Drone adı, amacı, şasi ağırlığı, dingil ve şasi parçası girdilerini denetler."""

    @staticmethod
    def ad_dogrula(ad: str) -> str:
        """
        Drone adını denetler ve baştaki/sondaki boşlukları temizler.

        Parametreler:
            ad: Kullanıcının yazdığı ad.
        Dönüş:
            Temizlenmiş ad.
        Hatalar:
            GecersizDegerHatasi: Ad boşsa veya çok uzunsa.
        """
        temiz = ad.strip()
        if not temiz:
            raise GecersizDegerHatasi("Drone adı boş olamaz.")
        if len(temiz) > AD_EN_FAZLA_UZUNLUK:
            raise GecersizDegerHatasi(f"Drone adı en fazla {AD_EN_FAZLA_UZUNLUK} karakter olabilir.")
        return temiz

    @staticmethod
    def amac_dogrula(amac: str) -> str:
        """
        Kullanım amacının listede olduğunu denetler.

        Parametreler:
            amac: Seçilen amaç.
        Dönüş:
            Amaç (değişmeden).
        Hatalar:
            GecersizDegerHatasi: Amaç listede yoksa.
        """
        if amac not in KULLANIM_AMACLARI:
            raise GecersizDegerHatasi(
                f"'{amac}' geçerli bir kullanım amacı değil. Seçenekler: {', '.join(KULLANIM_AMACLARI)}."
            )
        return amac

    @staticmethod
    def agirlik_dogrula(agirlik_g: float | None) -> float | None:
        """
        Elle girilen şasi ağırlığını denetler.

        Parametreler:
            agirlik_g: Ağırlık, gram; None ağırlığın silinmesi demektir.
        Dönüş:
            Ağırlık, gram veya None.
        Hatalar:
            GecersizDegerHatasi: Değer sayı değilse veya sıfır/negatifse.
        """
        if agirlik_g is None:
            return None
        if not gecerli_sayi_mi(agirlik_g) or agirlik_g <= 0:
            raise GecersizDegerHatasi(
                f"Şasi ağırlığı sıfırdan büyük ve en çok {EN_BUYUK_GIRDI_DEGERI:g} olan bir sayı olmalı (gram)."
            )
        return float(agirlik_g)

    @staticmethod
    def dingil_dogrula(dingil_mm: float | None) -> float | None:
        """
        Girilen veya onaylanan dingil mesafesini denetler.

        Parametreler:
            dingil_mm: Çapraz motor–motor mesafesi, mm; None dingilin silinmesi demektir.
        Dönüş:
            Dingil, mm veya None.
        Hatalar:
            GecersizDegerHatasi: Sayı değilse veya aralık dışındaysa.
        """
        if dingil_mm is None:
            return None
        if not gecerli_sayi_mi(dingil_mm) or not DINGIL_EN_KUCUK_MM <= dingil_mm <= DINGIL_EN_BUYUK_MM:
            raise GecersizDegerHatasi(
                f"Dingil mesafesi {DINGIL_EN_KUCUK_MM:g} ile {DINGIL_EN_BUYUK_MM:g} mm arasında bir sayı olmalı."
            )
        return float(dingil_mm)

    @staticmethod
    def parca_adedi_dogrula(adet: int, dosya_adi: str) -> int:
        """
        Parçalı şasideki bir parçanın adedini denetler.

        Parametreler:
            adet: Girilen adet.
            dosya_adi: Hata mesajında gösterilecek parça adı.
        Dönüş:
            Adet.
        Hatalar:
            GecersizDegerHatasi: 1 ile EN_FAZLA_PARCA_ADEDI arasında bir tam sayı değilse.
        """
        if isinstance(adet, bool) or not isinstance(adet, int) or not 1 <= adet <= EN_FAZLA_PARCA_ADEDI:
            raise GecersizDegerHatasi(
                f"'{dosya_adi}' için adet 1 ile {EN_FAZLA_PARCA_ADEDI} arasında bir tam sayı olmalı."
            )
        return adet

    @staticmethod
    def parca_rolu_dogrula(rol: str, dosya_adi: str) -> ParcaRolu:
        """
        Parçalı şasideki bir parçanın rolünü denetler.

        Parametreler:
            rol: Rol değeri ("govde", "kol", "ayak", "diger").
            dosya_adi: Hata mesajında gösterilecek parça adı.
        Dönüş:
            ParcaRolu.
        Hatalar:
            GecersizDegerHatasi: Rol tanınmıyorsa.
        """
        try:
            return ParcaRolu(rol)
        except ValueError as hata:
            secenekler = ", ".join(PARCA_ROLU_ADLARI.values())
            raise GecersizDegerHatasi(f"'{dosya_adi}' için rol geçersiz. Seçenekler: {secenekler}.") from hata
