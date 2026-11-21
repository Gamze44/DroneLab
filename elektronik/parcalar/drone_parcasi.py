"""
Drone ile katalogdaki parça arasındaki bağ.

Katalog tüm dronelar arasında ortaktır; bir parçanın bir drone'daki adedi ve
durumu (elimde / önerilen / planlanan) bu bağda tutulur. Bu bağı yöneten
depo ve iş mantığı E1'in sonraki adımında yazılacak.
"""

from dataclasses import dataclass
from typing import Final

from cekirdek.hatalar import GecersizDegerHatasi
from elektronik.parcalar.turler import ParcaDurumu

# DEĞİŞTİRİLEBİLİR: Bir drone'a aynı parçadan eklenebilecek en çok adet. Yanlışlıkla
# fazladan sıfır yazmayı yakalar ve veritabanının tam sayı sınırını aşan değerleri engeller.
EN_FAZLA_ADET: Final[int] = 1000


@dataclass(kw_only=True)
class DroneParcasi:
    """
    Bir drone'a eklenmiş parça.

    Alanlar:
        drone_kimlik: Drone numarası.
        parca_kimlik: Katalogdaki parça numarası.
        adet: Kaç tane (ör. 4 motor). En az 1.
        durum: Elimde / önerilen / planlanan.
        kimlik: Bağın numarası; kaydedilmemişse None.
        eklenme_zamani: ISO zaman; kaydedilmemişse None.
    """

    drone_kimlik: int
    parca_kimlik: int
    adet: int = 1
    durum: ParcaDurumu = ParcaDurumu.PLANLANAN
    kimlik: int | None = None
    eklenme_zamani: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.adet, bool) or not isinstance(self.adet, int) or not 1 <= self.adet <= EN_FAZLA_ADET:
            raise GecersizDegerHatasi(
                f"Adet 1 ile {EN_FAZLA_ADET} arasında bir tam sayı olmalı (girilen: {self.adet!r})."
            )
        if not isinstance(self.durum, ParcaDurumu):
            try:
                self.durum = ParcaDurumu(self.durum)
            except ValueError:
                gecerli = ", ".join(d.value for d in ParcaDurumu)
                raise GecersizDegerHatasi(f"Parça durumu tanınmıyor: {self.durum!r}. Seçenekler: {gecerli}.") from None
