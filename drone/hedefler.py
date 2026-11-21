"""
Drone'un tasarım hedefleri: istenen uçuş süresi, taşınacak yük, bütçe ve itki/ağırlık oranı.

Hepsi isteğe bağlıdır; girilmeyen hedef karşılaştırmaya girmez.
    - yük: toplam ağırlığa eklenir (uçuş hesabı ve öneriler bunu kullanır)
    - uçuş süresi: uçuş hesabının tahmini süresiyle karşılaştırılır
    - bütçe: maliyet sekmesinde alınacakların toplamıyla karşılaştırılır
    - itki/ağırlık: girilirse kullanım amacına göre varsayılan hedefin yerine geçer
"""

from dataclasses import dataclass
import math
from typing import Final

from cekirdek.hatalar import GecersizDegerHatasi

# DEĞİŞTİRİLEBİLİR: Akla yatkın üst sınırlar (yanlışlıkla fazladan sıfır yazmayı yakalar).
EN_BUYUK_UCUS_SURESI_DK: Final[float] = 600.0
EN_BUYUK_YUK_G: Final[float] = 100_000.0
EN_BUYUK_BUTCE_TL: Final[float] = 100_000_000.0
# DEĞİŞTİRİLEBİLİR: İtki/ağırlık hedefi aralığı. 1'in altında drone kalkamaz; yarış dronları ~15'e çıkar.
EN_KUCUK_ITKI_AGIRLIK: Final[float] = 1.0
EN_BUYUK_ITKI_AGIRLIK: Final[float] = 30.0


@dataclass
class DroneHedefleri:
    """
    Alanlar:
        ucus_suresi_dk: İstenen en az uçuş süresi, dakika; yoksa None.
        yuk_g: Taşınacak yük (kamera dışı ek yük vb.), gram; yoksa None.
        butce_tl: Alınacak parçalar için bütçe, TL; yoksa None.
        itki_agirlik: İstenen en az itki/ağırlık oranı (birimsiz); yoksa None ve kullanım
            amacına göre varsayılan hedef kullanılır.
    """

    ucus_suresi_dk: float | None = None
    yuk_g: float | None = None
    butce_tl: float | None = None
    itki_agirlik: float | None = None

    def __post_init__(self) -> None:
        self._denetle("Uçuş süresi hedefi", self.ucus_suresi_dk, EN_BUYUK_UCUS_SURESI_DK, sifir_olur=False)
        self._denetle("Yük", self.yuk_g, EN_BUYUK_YUK_G, sifir_olur=True)
        self._denetle("Bütçe", self.butce_tl, EN_BUYUK_BUTCE_TL, sifir_olur=False)
        self._denetle("İtki/ağırlık hedefi", self.itki_agirlik, EN_BUYUK_ITKI_AGIRLIK, sifir_olur=False)
        if self.itki_agirlik is not None and self.itki_agirlik <= EN_KUCUK_ITKI_AGIRLIK:
            raise GecersizDegerHatasi(
                f"İtki/ağırlık hedefi {EN_KUCUK_ITKI_AGIRLIK:g}'den büyük olmalı; daha düşük oranla drone kalkamaz "
                f"(girilen: {self.itki_agirlik:g})."
            )

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
