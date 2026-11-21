"""
Drone'un tasarım hedefleri: istenen uçuş süresi, taşınacak yük ve bütçe.

Hepsi isteğe bağlıdır; girilmeyen hedef karşılaştırmaya girmez.
    - yük: toplam ağırlığa eklenir (uçuş hesabı ve öneriler bunu kullanır)
    - uçuş süresi: uçuş hesabının tahmini süresiyle karşılaştırılır
    - bütçe: maliyet sekmesinde alınacakların toplamıyla karşılaştırılır
"""

from dataclasses import dataclass
import math
from typing import Final

from cekirdek.hatalar import GecersizDegerHatasi

# DEĞİŞTİRİLEBİLİR: Akla yatkın üst sınırlar (yanlışlıkla fazladan sıfır yazmayı yakalar).
EN_BUYUK_UCUS_SURESI_DK: Final[float] = 600.0
EN_BUYUK_YUK_G: Final[float] = 100_000.0
EN_BUYUK_BUTCE_TL: Final[float] = 100_000_000.0


@dataclass
class DroneHedefleri:
    """
    Alanlar:
        ucus_suresi_dk: İstenen en az uçuş süresi, dakika; yoksa None.
        yuk_g: Taşınacak yük (kamera dışı ek yük vb.), gram; yoksa None.
        butce_tl: Alınacak parçalar için bütçe, TL; yoksa None.
    """

    ucus_suresi_dk: float | None = None
    yuk_g: float | None = None
    butce_tl: float | None = None

    def __post_init__(self) -> None:
        self._denetle("Uçuş süresi hedefi", self.ucus_suresi_dk, EN_BUYUK_UCUS_SURESI_DK, sifir_olur=False)
        self._denetle("Yük", self.yuk_g, EN_BUYUK_YUK_G, sifir_olur=True)
        self._denetle("Bütçe", self.butce_tl, EN_BUYUK_BUTCE_TL, sifir_olur=False)

    @staticmethod
    def _denetle(ad: str, deger: float | None, en_buyuk: float, sifir_olur: bool) -> None:
        if deger is None:
            return
        if isinstance(deger, bool) or not isinstance(deger, (int, float)) or not math.isfinite(deger):
            raise GecersizDegerHatasi(f"{ad} bir sayı olmalı (girilen: {deger!r}).")
        if deger < 0 or (deger == 0 and not sifir_olur):
            raise GecersizDegerHatasi(f"{ad} sıfırdan büyük olmalı (girilen: {deger}).")
        if deger > en_buyuk:
            raise GecersizDegerHatasi(f"{ad} çok büyük görünüyor ({deger}). Fazladan sıfır yazılmış olabilir.")
