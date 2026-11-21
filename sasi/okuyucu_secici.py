"""
Dosya uzantısına göre doğru şasi okuyucusunu seçer.

Desteklenmeyen formatlarda kullanıcıya neden okunamadığını ve dosyayı
hangi formatta dışa aktarması gerektiğini anlatan bir hata fırlatır.
"""

from pathlib import Path
from typing import Final

from cekirdek.hatalar import DesteklenmeyenDosyaHatasi
from sasi.disa_aktarma_rehberi import (
    DISA_AKTARMA_ADIMLARI,
    GENEL_TAVSIYE,
    STEP_BEKLEMEDE_MESAJI,
    YEREL_FORMATLAR,
)
from sasi.okuyucular.ag_okuyucu import AgOkuyucu
from sasi.okuyucular.dxf_okuyucu import DxfOkuyucu
from sasi.okuyucular.temel import SasiOkuyucu
from sasi.okuyucular.zip_okuyucu import ZipSasiOkuyucu

# DEĞİŞTİRİLEBİLİR: Yeni okuyucu (ör. STEP) yazıldığında buraya eklenir. Zip içindeki
# parçalar da bu okuyucularla okunur.
OKUYUCU_SINIFLARI: Final[tuple[type[SasiOkuyucu], ...]] = (AgOkuyucu, DxfOkuyucu)

STEP_UZANTILARI: Final[tuple[str, ...]] = (".step", ".stp")


class OkuyucuSecici:
    """Dosya uzantısından uygun SasiOkuyucu nesnesini bulur."""

    def __init__(self) -> None:
        self._okuyucular: dict[str, type[SasiOkuyucu]] = {
            uzanti: sinif for sinif in OKUYUCU_SINIFLARI for uzanti in sinif.UZANTILAR
        }

    @property
    def desteklenen_uzantilar(self) -> list[str]:
        """Okunabilen uzantıların sıralı listesi (ör. [".3mf", ".dxf", ...]); parçalı şasi zip'i dahil."""
        return sorted([*self._okuyucular, *ZipSasiOkuyucu.UZANTILAR])

    @staticmethod
    def parcali_mi(dosya_adi: str | Path) -> bool:
        """
        Dosyanın parçalı şasi arşivi (zip) olup olmadığını uzantıdan söyler.

        Parametreler:
            dosya_adi: Dosya adı veya yolu.
        Dönüş:
            Zip ise True.
        """
        return Path(dosya_adi).suffix.lower() in ZipSasiOkuyucu.UZANTILAR

    def parcali_okuyucu(self) -> ZipSasiOkuyucu:
        """Zip içindeki parçaları bu seçicinin okuyucularıyla okuyan okuyucuyu döndürür."""
        return ZipSasiOkuyucu(self._parca_okuyucusu)

    def _parca_okuyucusu(self, uzanti: str) -> SasiOkuyucu | None:
        """Zip içindeki bir parça uzantısı için okuyucu; desteklenmiyorsa None."""
        sinif = self._okuyucular.get(uzanti)
        return sinif() if sinif is not None else None

    def denetle(self, dosya_adi: str | Path) -> None:
        """
        Dosya türünün okunabildiğini denetler (tek dosya veya parçalı şasi zip'i).

        Hatalar:
            DesteklenmeyenDosyaHatasi: Tür desteklenmiyorsa.
        """
        if not self.parcali_mi(dosya_adi):
            self.sec(dosya_adi)

    def sec(self, dosya_adi: str | Path) -> SasiOkuyucu:
        """
        Dosya adının uzantısına göre okuyucu döndürür.

        Parametreler:
            dosya_adi: Dosya adı veya yolu.
        Dönüş:
            Uygun okuyucu nesnesi.
        Hatalar:
            DesteklenmeyenDosyaHatasi: Uzantı desteklenmiyorsa (rehber bilgisiyle).
        """
        uzanti = Path(dosya_adi).suffix.lower()
        if uzanti in self._okuyucular:
            return self._okuyucular[uzanti]()

        if uzanti in STEP_UZANTILARI:
            raise DesteklenmeyenDosyaHatasi(STEP_BEKLEMEDE_MESAJI)

        program = YEREL_FORMATLAR.get(uzanti)
        if program is not None:
            raise DesteklenmeyenDosyaHatasi(
                f"{program} dosyaları ({uzanti}) kapalı bir formattır ve okunamaz. {GENEL_TAVSIYE}",
                rehber=DISA_AKTARMA_ADIMLARI.get(program, []),
            )

        gorunen_uzanti = uzanti or "(uzantısız)"
        raise DesteklenmeyenDosyaHatasi(
            f"'{gorunen_uzanti}' dosya türü desteklenmiyor. "
            f"Desteklenen türler: {', '.join(self.desteklenen_uzantilar)}."
        )
