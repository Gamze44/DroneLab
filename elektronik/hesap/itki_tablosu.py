"""
Ölçülmüş itki tablosundan (motor üreticisinin test verisi) değer okuma.

Tablolarda genellikle birkaç gerilim ve pervane için satırlar bulunur. Pilin
nominal gerilimine en yakın gerilimdeki satırlar seçilir; o gerilimde birden
çok pervane varsa drone'daki pervanenin çapıyla eşleşenler tercih edilir.
Ara değerler doğrusal bulunur; (0 gaz, 0 itki, 0 akım) başlangıç noktası eklenir.
"""

import re

from elektronik.parcalar.cekirdek_parcalar import ItkiNoktasi

# Pervane yazımındaki ilk sayı çaptır: "5x4.3x3", "5143", "T5143S" gibi biçimlerden yalnızca "AxB" desteklenir.
PERVANE_CAP_DESENI = re.compile(r"(\d+(?:[.,]\d+)?)\s*[xX×]")
CAP_ESLESME_TOLERANSI_INC: float = 0.05


def _cap(pervane: str | None) -> float | None:
    """Pervane yazısından çapı (inç) okur; okunamazsa None."""
    if not pervane:
        return None
    eslesme = PERVANE_CAP_DESENI.search(pervane)
    return float(eslesme.group(1).replace(",", ".")) if eslesme else None


def _ara_deger(x: float, xler: list[float], yler: list[float]) -> float:
    """Sıralı (x, y) noktaları arasında doğrusal ara değer; x aralık içinde olmalı."""
    for x0, x1, y0, y1 in zip(xler, xler[1:], yler, yler[1:]):
        if x <= x1:
            return y0 if x1 == x0 else y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return yler[-1]


class ItkiTablosuOkuyucu:
    """
    Bir gerilim + pervane için seçilmiş itki satırları üzerinde hesap yapar.

    Parametreler:
        tablo: Motorun itki tablosu.
        gerilim_v: Pilin nominal gerilimi, V.
        cap_inc: Drone'daki pervanenin çapı, inç; bilinmiyorsa None.
    """

    def __init__(self, tablo: list[ItkiNoktasi], gerilim_v: float, cap_inc: float | None) -> None:
        self.secilen_gerilim_v = min({n.gerilim_v for n in tablo}, key=lambda g: abs(g - gerilim_v))
        satirlar = [n for n in tablo if n.gerilim_v == self.secilen_gerilim_v]
        if cap_inc is not None:
            eslesen = [n for n in satirlar if (c := _cap(n.pervane)) is not None and abs(c - cap_inc) <= CAP_ESLESME_TOLERANSI_INC]
            satirlar = eslesen or satirlar
        self.noktalar: list[ItkiNoktasi] = sorted(satirlar, key=lambda n: (n.gaz_yuzde, n.itki_g))

    @property
    def en_buyuk_itki_g(self) -> float:
        """Seçilen satırlardaki en büyük itki, gram."""
        return max(n.itki_g for n in self.noktalar)

    def gaz_yuzde(self, itki_g: float) -> float | None:
        """
        Verilen itki için gereken gaz yüzdesi.

        Dönüş:
            Gaz, %; itki tablodaki en büyük itkiyi aşıyorsa None.
        """
        if itki_g > self.en_buyuk_itki_g:
            return None
        itkiler = [0.0] + [n.itki_g for n in self.noktalar]
        gazlar = [0.0] + [n.gaz_yuzde for n in self.noktalar]
        return _ara_deger(itki_g, itkiler, gazlar)

    def akim_a(self, gaz_yuzde: float) -> float | None:
        """
        Verilen gazda tek motorun akımı.

        Dönüş:
            Akım, A; tablodaki satırların akımı girilmemişse None.
        """
        if any(n.akim_a is None for n in self.noktalar):
            return None
        gazlar = [0.0] + [n.gaz_yuzde for n in self.noktalar]
        akimlar = [0.0] + [n.akim_a for n in self.noktalar]
        return _ara_deger(gaz_yuzde, gazlar, akimlar)
