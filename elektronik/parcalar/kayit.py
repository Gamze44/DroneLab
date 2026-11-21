"""
Parça türünden parça sınıfına eşleme.

Yeni bir parça türü eklendiğinde yalnızca bu tabloya eklenmesi yeterlidir;
katalog ve serileştirme sınıfı buradan bulur.
"""

from typing import Final

from elektronik.parcalar.cekirdek_parcalar import Alici, Esc, GucDagitim, Motor, Pervane, Pil, UcusKarti
from elektronik.parcalar.diger_parca import DigerParca
from elektronik.parcalar.parca import Parca
from elektronik.parcalar.turler import ParcaTuru

PARCA_SINIFLARI: Final[dict[ParcaTuru, type[Parca]]] = {
    sinif.TUR: sinif for sinif in (Motor, Pervane, Esc, Pil, UcusKarti, Alici, GucDagitim, DigerParca)
}


def parca_sinifi(tur: ParcaTuru | str) -> type[Parca]:
    """
    Türün parça sınıfını döndürür.

    Parametreler:
        tur: ParcaTuru veya değeri (ör. "motor").
    Hatalar:
        ValueError: Tür tanınmıyorsa.
    """
    return PARCA_SINIFLARI[ParcaTuru(tur)]
