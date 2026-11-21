"""
Para birimleri ve fiyat değeri.
"""

from dataclasses import dataclass
import math
from typing import Final

from cekirdek.hatalar import GecersizDegerHatasi


# Para birimleri ISO 4217 kodlarıyla (ör. "USD") tutulur.
TL: Final[str] = "TRY"

# DEĞİŞTİRİLEBİLİR: Seçilebilen para birimleri ve ekrandaki adları. TL dışındakiler TCMB
# günlük kur dosyasında bulunmalı (yeni birim eklemek için koduyla buraya yazmak yeterli).
PARA_BIRIMLERI: Final[dict[str, str]] = {
    TL: "TL",
    "USD": "ABD doları ($)",
    "EUR": "Euro (€)",
    "GBP": "İngiliz sterlini (£)",
    "CNY": "Çin yuanı (¥)",
}

# DEĞİŞTİRİLEBİLİR: Akla yatkın en büyük birim fiyat (yanlışlıkla fazladan sıfır yazmayı yakalar).
EN_BUYUK_TUTAR: Final[float] = 10_000_000.0


@dataclass(frozen=True)
class Fiyat:
    """
    Bir fiyat.

    Alanlar:
        tutar: Sıfır veya pozitif tutar (0 = bedava/hediye).
        para_birimi: PARA_BIRIMLERI içinden kod.
    """

    tutar: float
    para_birimi: str = TL

    def __post_init__(self) -> None:
        t = self.tutar
        if isinstance(t, bool) or not isinstance(t, (int, float)) or not math.isfinite(t) or t < 0:
            raise GecersizDegerHatasi(f"Fiyat sıfır veya pozitif bir sayı olmalı (girilen: {t!r}).")
        if t > EN_BUYUK_TUTAR:
            raise GecersizDegerHatasi(f"Fiyat çok büyük görünüyor ({t}). Fazladan sıfır yazılmış olabilir.")
        if self.para_birimi not in PARA_BIRIMLERI:
            raise GecersizDegerHatasi(
                f"Para birimi tanınmıyor: {self.para_birimi!r}. Seçenekler: {', '.join(PARA_BIRIMLERI)}."
            )
