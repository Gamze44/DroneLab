"""
Kullanıcıdan ve yapay zekadan gelen sayıların ortak denetimi.

Neden: JSON 1e308 gibi çok büyük sayılara izin verir. Böyle bir ağırlık birkaç parçayla
toplandığında sonuç "sonsuz" olur; hesaplar anlamsızlaşır ve yanıt JSON'a yazılamaz.
Fiziksel olarak anlamlı hiçbir girdi EN_BUYUK_GIRDI_DEGERI'ni aşmaz.
"""

from typing import Any, Final

# DEĞİŞTİRİLEBİLİR: Bir sayı alanına girilebilecek en büyük değer (birimden bağımsız;
# ör. 1 milyar gram = 1000 ton). Fiyatlar için ayrıca maliyet/para.py'deki sınır geçerlidir.
EN_BUYUK_GIRDI_DEGERI: Final[float] = 1e9


def gecerli_sayi_mi(deger: Any) -> bool:
    """
    Değerin hesapta kullanılabilecek bir sayı olup olmadığını söyler.

    Mantıksal değerler (True/False) sayı sayılmaz. NaN ve sonsuz, karşılaştırmada
    kendiliğinden elenir (NaN hiçbir sayıdan küçük değildir).

    Parametreler:
        deger: Denetlenecek değer.
    Dönüş:
        int/float ise ve mutlak değeri EN_BUYUK_GIRDI_DEGERI'ni aşmıyorsa True.
    """
    if isinstance(deger, bool) or not isinstance(deger, (int, float)):
        return False
    return -EN_BUYUK_GIRDI_DEGERI <= deger <= EN_BUYUK_GIRDI_DEGERI
