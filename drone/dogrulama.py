"""
Kullanıcının drone için girdiği bilgilerin doğrulanması.

Hatalı girişler veritabanına yazılmadan önce burada yakalanır ve kullanıcıya
Türkçe, ne yapması gerektiğini anlatan bir mesaj döner.
"""

import math
from typing import Final

from cekirdek.hatalar import GecersizDegerHatasi
from drone.modeller import KULLANIM_AMACLARI

# DEĞİŞTİRİLEBİLİR: Drone adının en fazla karakter sayısı.
AD_EN_FAZLA_UZUNLUK: Final[int] = 80


class DroneGirdisiDogrulayici:
    """Drone adı, amacı ve şasi ağırlığı girdilerini denetler."""

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
        if not math.isfinite(agirlik_g) or agirlik_g <= 0:
            raise GecersizDegerHatasi("Şasi ağırlığı sıfırdan büyük bir sayı olmalı (gram).")
        return float(agirlik_g)
