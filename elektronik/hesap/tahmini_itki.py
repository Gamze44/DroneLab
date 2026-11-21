"""
İtki tablosu yokken itki ve asılı kalma gücünün fizik formülleriyle tahmini
(plan bölüm 5.3). Sonuçlar her zaman "tahmini"dir.

Kabuller (neden bu formüller):
    - En büyük devir n ≈ KV × gerilim × yük altındaki düşüş oranı. KV boştaki
      devri verir; pervane yükü altında devir yaklaşık %20 düşer.
    - İtki T = C_T · ρ · n² · D⁴ (n: devir/saniye, D: çap, metre). Bu, pervane
      teorisinin standart boyutsuz itki bağıntısıdır; C_T pervane biçimine bağlıdır
      ve burada yalnızca hatve/çap oranından bir tablodan alınır.
    - Asılı kalma gücü momentum teorisinden: P_ideal = T^1,5 / √(2ρA). Gerçek
      pervane ideal değildir (verim katsayısı FoM) ve motor+ESC kayıpları vardır (η).
"""

import math

from cekirdek.birimler import BirimDonusturucu
from elektronik.hesap.katsayilar import (
    HAVA_YOGUNLUGU_KG_M3,
    ITKI_KATSAYISI_TABLOSU,
    MOTOR_ESC_VERIMI,
    PERVANE_VERIM_KATSAYISI,
    SANIYE_DAKIKA,
    YERCEKIMI_M_S2,
    YUK_ALTINDA_DEVIR_ORANI,
)

INC: str = "inch"
METRE: str = "m"
KILOGRAM: str = "kg"


def _cap_metre(cap_inc: float) -> float:
    """Pervane çapını inçten metreye çevirir (birimler modülü üzerinden)."""
    return BirimDonusturucu.mm_yi_uzunluga_cevir(BirimDonusturucu.uzunlugu_mm_ye_cevir(cap_inc, INC), METRE)


def _gram_newton(itki_g: float) -> float:
    """Gram-kuvveti Newton'a çevirir."""
    return BirimDonusturucu.grami_kutleye_cevir(itki_g, KILOGRAM) * YERCEKIMI_M_S2


def _newton_gram(itki_n: float) -> float:
    """Newton'u gram-kuvvete çevirir."""
    return BirimDonusturucu.kutleyi_grama_cevir(itki_n / YERCEKIMI_M_S2, KILOGRAM)


class TahminiItkiHesaplayici:
    """
    Motor ve pervane değerlerinden itki ve güç tahmini yapar.

    Parametreler:
        hava_yogunlugu: kg/m3.
        devir_orani: Yük altındaki devrin boştaki devre oranı.
        verim_katsayisi: Pervane verim katsayısı (FoM).
        motor_esc_verimi: Motor + ESC verimi.
    """

    def __init__(
        self,
        hava_yogunlugu: float = HAVA_YOGUNLUGU_KG_M3,
        devir_orani: float = YUK_ALTINDA_DEVIR_ORANI,
        verim_katsayisi: float = PERVANE_VERIM_KATSAYISI,
        motor_esc_verimi: float = MOTOR_ESC_VERIMI,
    ) -> None:
        self.hava_yogunlugu = hava_yogunlugu
        self.devir_orani = devir_orani
        self.verim_katsayisi = verim_katsayisi
        self.motor_esc_verimi = motor_esc_verimi

    @staticmethod
    def itki_katsayisi(cap_inc: float, hatve_inc: float) -> float:
        """
        Hatve/çap oranından C_T (tablodan doğrusal ara değer; tablo dışı en yakın uca sabitlenir).

        Parametreler:
            cap_inc, hatve_inc: Pervane çapı ve hatvesi, inç.
        Dönüş:
            Boyutsuz itki katsayısı.
        """
        oran = hatve_inc / cap_inc
        tablo = ITKI_KATSAYISI_TABLOSU
        if oran <= tablo[0][0]:
            return tablo[0][1]
        for (x0, y0), (x1, y1) in zip(tablo, tablo[1:]):
            if oran <= x1:
                return y0 + (y1 - y0) * (oran - x0) / (x1 - x0)
        return tablo[-1][1]

    def en_buyuk_itki_g(self, kv: float, gerilim_v: float, cap_inc: float, hatve_inc: float) -> float:
        """
        Tam gazda tek motorun tahmini itkisi.

        Parametreler:
            kv: Motor KV, dev/dk/V.
            gerilim_v: Pil nominal gerilimi, V.
            cap_inc, hatve_inc: Pervane çapı ve hatvesi, inç.
        Dönüş:
            İtki, gram.
        """
        devir_saniye = kv * gerilim_v * self.devir_orani / SANIYE_DAKIKA
        itki_n = self.itki_katsayisi(cap_inc, hatve_inc) * self.hava_yogunlugu * devir_saniye**2 * _cap_metre(cap_inc) ** 4
        return _newton_gram(itki_n)

    def asili_guc_w(self, itki_g: float, cap_inc: float) -> float:
        """
        Tek motorun verilen itkiyi üretmek için pilden çektiği tahmini güç.

        Parametreler:
            itki_g: Motor başına gereken itki, gram.
            cap_inc: Pervane çapı, inç.
        Dönüş:
            Elektrik gücü, W.
        """
        disk_alani = math.pi * (_cap_metre(cap_inc) / 2) ** 2
        ideal = _gram_newton(itki_g) ** 1.5 / math.sqrt(2 * self.hava_yogunlugu * disk_alani)
        return ideal / (self.verim_katsayisi * self.motor_esc_verimi)
