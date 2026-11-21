"""
İkinci grup parçalar: kamera, VTX, GPS, telemetri, yük.

Hepsi tek sınıfla tutulur; ilk sürümde yalnızca ağırlık ve besleme gerilimi
kontrol edilir. Ayrıntılı alanlar gerektiğinde bu sınıftan türetilebilir.
"""

from dataclasses import dataclass
from typing import ClassVar

from cekirdek.hatalar import GecersizDegerHatasi
from elektronik.parcalar.parca import Parca
from elektronik.parcalar.turler import DigerAltTur, ParcaTuru


@dataclass(kw_only=True)
class DigerParca(Parca):
    """
    İkinci grup parça.

    Alanlar:
        alt_tur: Kamera, VTX, GPS, telemetri veya yük. Zorunlu.
        besleme_gerilimi_v: Nominal besleme gerilimi, V (K13); yükte genelde None.
        guc_w: Çektiği güç, W.
    """

    TUR: ClassVar[ParcaTuru] = ParcaTuru.DIGER

    alt_tur: DigerAltTur
    besleme_gerilimi_v: float | None = None
    guc_w: float | None = None

    def _ture_ozel_denetim(self) -> None:
        if not isinstance(self.alt_tur, DigerAltTur):
            try:
                self.alt_tur = DigerAltTur(self.alt_tur)
            except ValueError:
                gecerli = ", ".join(t.value for t in DigerAltTur)
                raise GecersizDegerHatasi(f"Alt tür tanınmıyor: {self.alt_tur!r}. Seçenekler: {gecerli}.") from None

    @property
    def tur_anahtari(self) -> str:
        """Aynı marka ve modelde bir kamera ile bir GPS karışmasın diye alt tür de anahtara girer."""
        return f"{self.TUR.value}/{self.alt_tur.value}"
