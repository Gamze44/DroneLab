"""
2B kontur işlemleri: açık çizgileri kapalı şekillere birleştirme ve
iç içe konturlardan net alan (dış kontur eksi delikler) hesabı.

DXF'te bir şasi çoğu zaman tek bir kapalı çoklu çizgi değil, uç uca eklenmiş
LINE ve ARC parçaları olarak gelir (ör. Fusion 360 dışa aktarımı). Bu yüzden
alan hesabından önce parçaları zincirlemek gerekir.
"""

from dataclasses import dataclass
import math

import numpy as np

Nokta = tuple[float, float]
Kontur = list[Nokta]


@dataclass(frozen=True)
class KonturOzeti:
    """
    Konturlardan çıkarılan alan özeti.

    Alanlar:
        net_alan: Dış konturların alanı eksi deliklerin alanı (çizim birimi^2).
        dis_kontur_sayisi: Hiçbir konturun içinde olmayan kontur sayısı.
        delik_sayisi: Bir dış konturun içinde kalan (alanı çıkarılan) kontur sayısı.
    """

    net_alan: float
    dis_kontur_sayisi: int
    delik_sayisi: int


class KonturBirlestirici:
    """
    Uçları birbirine değen açık çizgi parçalarını kapalı konturlara birleştirir.

    Parametreler:
        tolerans: İki ucun "değiyor" sayılacağı en büyük mesafe (çizim birimi).
    """

    def __init__(self, tolerans: float) -> None:
        self.tolerans: float = tolerans

    def _ayni_nokta_mi(self, a: Nokta, b: Nokta) -> bool:
        """İki noktanın tolerans içinde çakışıp çakışmadığını döndürür."""
        return math.dist(a, b) <= self.tolerans

    def birlestir(self, parcalar: list[Kontur]) -> tuple[list[Kontur], int]:
        """
        Açık parçaları uç uca ekleyerek kapalı konturlar oluşturur.

        Parametreler:
            parcalar: Her biri en az iki noktalı açık çizgi listesi.
        Dönüş:
            (kapalı konturlar, kapatılamayan zincir sayısı).
        """
        kalanlar = [list(p) for p in parcalar if len(p) >= 2]
        kapali_konturlar: list[Kontur] = []
        kapanmayan_sayisi = 0

        while kalanlar:
            zincir = kalanlar.pop()
            uzadi = True
            while uzadi and not self._ayni_nokta_mi(zincir[0], zincir[-1]):
                uzadi = self._zinciri_uzat(zincir, kalanlar)

            if len(zincir) > 2 and self._ayni_nokta_mi(zincir[0], zincir[-1]):
                kapali_konturlar.append(zincir)
            else:
                kapanmayan_sayisi += 1

        return kapali_konturlar, kapanmayan_sayisi

    def _zinciri_uzat(self, zincir: Kontur, kalanlar: list[Kontur]) -> bool:
        """
        Zincirin sonuna veya başına değen bir parça bulup ekler.

        Parçalar her iki yönde de çizilmiş olabileceği için gerekirse ters çevrilir.

        Parametreler:
            zincir: Uzatılacak nokta listesi (yerinde değiştirilir).
            kalanlar: Henüz kullanılmamış parçalar (kullanılan çıkarılır).
        Dönüş:
            Bir parça eklendiyse True.
        """
        son, bas = zincir[-1], zincir[0]
        for sira, parca in enumerate(kalanlar):
            if self._ayni_nokta_mi(son, parca[0]):
                zincir.extend(parca[1:])
            elif self._ayni_nokta_mi(son, parca[-1]):
                zincir.extend(reversed(parca[:-1]))
            elif self._ayni_nokta_mi(bas, parca[-1]):
                zincir[:0] = parca[:-1]
            elif self._ayni_nokta_mi(bas, parca[0]):
                zincir[:0] = list(reversed(parca[1:]))
            else:
                continue
            kalanlar.pop(sira)
            return True
        return False


class KonturAlanHesaplayici:
    """
    Kapalı konturların iç içe geçme durumuna bakarak net alanı hesaplar.

    Bir kontur kaç konturun içindeyse o kadar "derindir": derinlik 0 dış kontur,
    1 delik, 2 deliğin içindeki ada... Çift derinlikler alana eklenir, tekler çıkarılır.
    """

    @staticmethod
    def isaretli_alan(kontur: Kontur) -> float:
        """
        Konturun işaretli alanını Gauss (ayakkabı bağı) formülüyle hesaplar.

        Parametreler:
            kontur: Kapalı nokta listesi.
        Dönüş:
            Alan (çizim birimi^2); saat yönünün tersindeyse pozitif.
        """
        dizi = np.asarray(kontur, dtype=float)
        x, y = dizi[:, 0], dizi[:, 1]
        return float(0.5 * (np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))

    @staticmethod
    def nokta_icinde_mi(nokta: Nokta, kontur: Kontur) -> bool:
        """
        Noktanın kapalı konturun içinde olup olmadığını ışın atma yöntemiyle bulur.

        Parametreler:
            nokta: (x, y).
            kontur: Kapalı nokta listesi.
        Dönüş:
            İçerideyse True.
        """
        dizi = np.asarray(kontur, dtype=float)
        x1, y1 = dizi[:, 0], dizi[:, 1]
        x2, y2 = np.roll(x1, -1), np.roll(y1, -1)
        px, py = nokta
        kesiyor = (y1 > py) != (y2 > py)
        # Bölmede sıfıra bölme olmasın diye yalnızca ışını kesen kenarlar hesaplanır.
        with np.errstate(divide="ignore", invalid="ignore"):
            kesisim_x = x1 + (py - y1) * (x2 - x1) / (y2 - y1)
        return bool(np.count_nonzero(kesiyor & (px < kesisim_x)) % 2 == 1)

    def hesapla(self, konturlar: list[Kontur]) -> KonturOzeti:
        """
        Konturların net alanını ve dış kontur / delik sayılarını hesaplar.

        Parametreler:
            konturlar: Kapalı konturlar.
        Dönüş:
            KonturOzeti.
        """
        alanlar = [abs(self.isaretli_alan(k)) for k in konturlar]
        kutular = [self._sinir_kutusu(k) for k in konturlar]

        net_alan = 0.0
        dis_sayisi = 0
        delik_sayisi = 0
        for i, kontur in enumerate(konturlar):
            derinlik = sum(
                1
                for j, dis in enumerate(konturlar)
                if j != i
                and alanlar[j] > alanlar[i]
                and self._kutu_icinde_mi(kutular[i], kutular[j])
                and self.nokta_icinde_mi(kontur[0], dis)
            )
            if derinlik % 2 == 0:
                net_alan += alanlar[i]
                if derinlik == 0:
                    dis_sayisi += 1
            else:
                net_alan -= alanlar[i]
                delik_sayisi += 1

        return KonturOzeti(net_alan=net_alan, dis_kontur_sayisi=dis_sayisi, delik_sayisi=delik_sayisi)

    @staticmethod
    def _sinir_kutusu(kontur: Kontur) -> tuple[float, float, float, float]:
        """Konturun (en küçük x, en küçük y, en büyük x, en büyük y) kutusunu döndürür."""
        dizi = np.asarray(kontur, dtype=float)
        return (*dizi.min(axis=0), *dizi.max(axis=0))

    @staticmethod
    def _kutu_icinde_mi(ic: tuple[float, ...], dis: tuple[float, ...]) -> bool:
        """
        İç kutunun dış kutunun içinde olup olmadığını döndürür.

        Pahalı nokta-içinde testinden önce hızlı bir eleme yapmak için kullanılır;
        çok delikli şasilerde hesabı belirgin şekilde hızlandırır.
        """
        return ic[0] >= dis[0] and ic[1] >= dis[1] and ic[2] <= dis[2] and ic[3] <= dis[3]
