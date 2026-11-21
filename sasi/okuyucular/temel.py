"""
Tüm şasi okuyucularının ortak arayüzü.

Yeni bir dosya türü eklemek (ör. STEP) için bu sınıftan türeyen bir okuyucu
yazıp okuyucu_secici.py içindeki listeye eklemek yeterlidir.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from sasi.modeller import SasiGeometrisi


class SasiOkuyucu(ABC):
    """
    Bir şasi dosyasını okuyup SasiGeometrisi döndüren okuyucuların temel sınıfı.

    Sınıf değişkenleri:
        UZANTILAR: Okuyucunun desteklediği küçük harfli uzantılar (ör. (".stl",)).
    """

    UZANTILAR: ClassVar[tuple[str, ...]] = ()

    @abstractmethod
    def oku(self, yol: Path) -> SasiGeometrisi:
        """
        Dosyayı okur.

        Parametreler:
            yol: Okunacak dosyanın yolu.
        Dönüş:
            Dosya biriminde ölçüler içeren SasiGeometrisi.
        Hatalar:
            DosyaOkumaHatasi: Dosya açılamaz veya geometri bulunamazsa.
        """
