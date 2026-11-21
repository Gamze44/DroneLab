"""
Şasi ölçüsünden takılabilecek en büyük pervanenin tahmini (plan bölüm 5.4).

Şasi dosyasından yalnızca sınır kutusu (en × boy) bilinir, motorların tam yeri
bilinmez. Bu yüzden sonuç kabadır ve her zaman "tahmini" gösterilir.

Yöntem:
    1. Dingil mesafesi (çapraz motor–motor) W ≈ √(en² + boy²) × k
    2. Komşu motorlar arası d = W × sin(π / motor sayısı)  (quad: W/√2, hexa: W/2)
    3. En büyük pervane ≈ d − pervane uçları arası boşluk, inçe çevrilip aşağı yuvarlanır.
"""

import math

from cekirdek.birimler import BirimDonusturucu
from elektronik.hesap.katsayilar import DINGIL_KATSAYISI, PERVANE_UC_BOSLUGU_MM, PERVANE_YUVARLAMA_ADIMI_INC
from sasi.modeller import SasiOlculeri

INC: str = "inch"


class EnBuyukPervaneTahmincisi:
    """
    Şasi ölçüsünden en büyük pervane çapını tahmin eder.

    Parametreler:
        dingil_katsayisi: Köşegenin motor merkezleri arasına düşen oranı.
        uc_boslugu_mm: Komşu pervane uçları arasındaki boşluk, mm.
        yuvarlama_adimi_inc: Sonucun aşağı yuvarlandığı adım, inç.
    """

    def __init__(
        self,
        dingil_katsayisi: float = DINGIL_KATSAYISI,
        uc_boslugu_mm: float = PERVANE_UC_BOSLUGU_MM,
        yuvarlama_adimi_inc: float = PERVANE_YUVARLAMA_ADIMI_INC,
    ) -> None:
        self.dingil_katsayisi = dingil_katsayisi
        self.uc_boslugu_mm = uc_boslugu_mm
        self.yuvarlama_adimi_inc = yuvarlama_adimi_inc

    def dingil_mesafesi_mm(self, olculer: SasiOlculeri) -> float:
        """Tahmini çapraz motor–motor mesafesi, mm."""
        return math.hypot(olculer.en_mm, olculer.boy_mm) * self.dingil_katsayisi

    def tahmin_et(self, olculer: SasiOlculeri, motor_sayisi: int) -> float | None:
        """
        En büyük pervane çapını tahmin eder.

        Parametreler:
            olculer: Birim onaylanmış şasi ölçüleri, mm.
            motor_sayisi: Motor sayısı (motorların bir çember üzerinde eşit aralıklı olduğu kabul edilir).
        Dönüş:
            Tahmini en büyük pervane çapı, inç; şasi pervane sığmayacak kadar küçükse None.
        """
        komsu_mm = self.dingil_mesafesi_mm(olculer) * math.sin(math.pi / motor_sayisi)
        cap_mm = komsu_mm - self.uc_boslugu_mm
        if cap_mm <= 0:
            return None
        cap_inc = BirimDonusturucu.mm_yi_uzunluga_cevir(cap_mm, INC)
        # Kayan nokta hatası (ör. 4.9999) bir adım aşağı düşürmesin diye küçük pay eklenir.
        adim_sayisi = math.floor(cap_inc / self.yuvarlama_adimi_inc + 1e-9)
        return round(adim_sayisi * self.yuvarlama_adimi_inc, 3)
