"""
Parça formunun alan tanımları.

Arayüz, her parça türünün formunu bu tanımlardan kendisi kurar; böylece bir
parça sınıfına yeni alan eklendiğinde arayüz kodunu değiştirmek gerekmez.
"""

from dataclasses import fields
from enum import Enum
import typing
from typing import Any, Final

from elektronik.parcalar.denetim import AlanCinsi, DegerDenetleyici
from elektronik.parcalar.parca import Parca
from elektronik.parcalar.turler import PIL_KIMYASI_ADLARI, PilKimyasi, alan_etiketi

# Formda gösterilmeyen teknik alanlar: alt tür formun üst kısmında ayrıca seçilir;
# itki tablosu çok satırlı olduğu için ayrı bir ekranda girilecek (sonraki aşama).
FORMDA_GOSTERILMEYEN: Final[frozenset[str]] = frozenset({"alt_tur", "itki_tablosu"})

SECIM: Final[str] = "secim"

# Enum alanlarının seçenek adları (değer -> ekranda görünen ad).
SECIM_ADLARI: Final[dict[type[Enum], dict[Any, str]]] = {PilKimyasi: PIL_KIMYASI_ADLARI}


def _enum_turu(tur_ipucu: Any) -> type[Enum] | None:
    """Tür ipucu (ör. "PilKimyasi | None") bir Enum içeriyorsa onu döndürür."""
    for aday in typing.get_args(tur_ipucu) or (tur_ipucu,):
        if isinstance(aday, type) and issubclass(aday, Enum):
            return aday
    return None


def alan_tanimlari(sinif: type[Parca]) -> list[dict[str, Any]]:
    """
    Bir parça türünün formda gösterilecek teknik alanlarını tanımlar.

    Parametreler:
        sinif: Parça sınıfı (ör. Motor).
    Dönüş:
        [{"ad", "etiket", "cins", "secenekler"?}, ...]; cins: tamsayi, sayi, metin,
        mantiksal, metin_listesi, sayi_listesi veya secim.
    """
    tanimlar: list[dict[str, Any]] = []
    for alan in fields(sinif):
        if alan.name in Parca.ORTAK_ALANLAR or alan.name in FORMDA_GOSTERILMEYEN:
            continue
        tanim: dict[str, Any] = {"ad": alan.name, "etiket": alan_etiketi(alan.name)}
        enum_turu = _enum_turu(alan.type)
        if enum_turu is not None:
            adlar = SECIM_ADLARI.get(enum_turu, {})
            tanim["cins"] = SECIM
            tanim["secenekler"] = [{"deger": e.value, "ad": adlar.get(e, e.value)} for e in enum_turu]
        else:
            cins = DegerDenetleyici.alan_cinsi(alan.type)
            if cins == AlanCinsi.DIGER:
                continue
            tanim["cins"] = cins
        tanimlar.append(tanim)
    return tanimlar
