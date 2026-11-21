"""
Pil hücre sayısı ve kimyasından gerilim aralıklarının bulunması.

Kimya girilmemişse tahmin yapılmaz: olası bütün kimyaların en düşük ve en
yüksek değeri birlikte döndürülür. Kontrol iki uçta da aynı sonucu veriyorsa
kimyayı bilmeye gerek kalmaz; vermiyorsa sonuç "bilinmiyor" olur.
"""

from dataclasses import dataclass

from elektronik.hesap.katsayilar import DOLU_HUCRE_GERILIMI_V, NOMINAL_HUCRE_GERILIMI_V
from elektronik.parcalar.cekirdek_parcalar import Pil
from elektronik.parcalar.turler import PilKimyasi


@dataclass(frozen=True)
class GerilimAraligi:
    """
    Kimya bilinmediğinde olası gerilim aralığı (kimya biliniyorsa iki uç eşittir).

    Alanlar:
        en_dusuk_v / en_yuksek_v: Olası en düşük ve en yüksek değer, V.
    """

    en_dusuk_v: float
    en_yuksek_v: float

    @property
    def kesin_mi(self) -> bool:
        """İki uç aynıysa (kimya biliniyorsa) True."""
        return self.en_dusuk_v == self.en_yuksek_v


class PilGerilimiHesaplayici:
    """Pilin dolu ve nominal gerilimini (V) hücre sayısı ve kimyadan hesaplar."""

    @staticmethod
    def _aralik(pil: Pil, tablo: dict[PilKimyasi, float]) -> GerilimAraligi | None:
        """Tablodaki hücre gerilimini hücre sayısıyla çarpar; S girilmemişse None."""
        if pil.hucre_sayisi_s is None:
            return None
        degerler = [tablo[pil.kimya]] if pil.kimya is not None else list(tablo.values())
        return GerilimAraligi(min(degerler) * pil.hucre_sayisi_s, max(degerler) * pil.hucre_sayisi_s)

    def dolu(self, pil: Pil) -> GerilimAraligi | None:
        """
        Tam dolu pil gerilimi.

        Dönüş:
            GerilimAraligi (V) veya hücre sayısı girilmemişse None.
        """
        return self._aralik(pil, DOLU_HUCRE_GERILIMI_V)

    def nominal(self, pil: Pil) -> GerilimAraligi | None:
        """
        Nominal (ortalama) pil gerilimi.

        Dönüş:
            GerilimAraligi (V) veya hücre sayısı girilmemişse None.
        """
        return self._aralik(pil, NOMINAL_HUCRE_GERILIMI_V)
