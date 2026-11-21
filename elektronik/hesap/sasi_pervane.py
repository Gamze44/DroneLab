"""
Şasi ölçüsünden takılabilecek en büyük pervanenin tahmini (plan bölüm 5.4).

Şasi dosyasından yalnızca sınır kutusu (en × boy) bilinir, motorların tam yeri
bilinmez. Bu yüzden sonuç kabadır ve her zaman "tahmini" gösterilir.

Yöntem:
    1. Dingil mesafesi (çapraz motor–motor) W: kullanıcı girdiyse (veya parçalardan hesaplanıp
       onaylandıysa) o değer; yoksa W ≈ √(en² + boy²) × k. Parçalı şaside dış ölçü dingili
       vermez, bu yüzden dingil girilmeden tahmin yapılmaz.
    2. Komşu motorlar arası d = W × sin(π / motor sayısı)  (quad: W/√2, hexa: W/2)
    3. En büyük pervane ≈ d − pervane uçları arası boşluk, inçe çevrilip aşağı yuvarlanır.
"""

from dataclasses import dataclass
import math
from typing import Final

from cekirdek.birimler import BIRIM_INC, BirimDonusturucu
from elektronik.hesap.katsayilar import DINGIL_KATSAYISI, PERVANE_UC_BOSLUGU_MM, PERVANE_YUVARLAMA_ADIMI_INC
from sasi.modeller import SasiOlculeri

# Kayan nokta hatası (ör. 4.9999) yuvarlamada bir adım aşağı düşürmesin diye eklenen pay.
YUVARLAMA_PAYI: Final[float] = 1e-9
# Sonuç inç cinsinden bu kadar ondalığa yuvarlanır (0,1 inç adımlarında gürültüyü atar).
SONUC_BASAMAGI: Final[int] = 3


@dataclass(frozen=True)
class SasiGorunumu:
    """
    Şasinin üstten görünüş çizimi için ölçüler. Motor yerleri ve pervane sınırı tahminidir.

    Alanlar:
        en_mm, boy_mm: Şasinin dış ölçüsü, mm.
        dingil_mm: Tahmini çapraz motor–motor mesafesi, mm.
        en_buyuk_pervane_inc / _mm: Sığabilecek en büyük pervane; sığmıyorsa None.
        pervane_cap_inc / _mm: Takılı (ilk) pervanenin çapı; pervane yoksa veya çapı girilmediyse None.
    """

    en_mm: float
    boy_mm: float
    dingil_mm: float
    en_buyuk_pervane_inc: float | None
    en_buyuk_pervane_mm: float | None
    pervane_cap_inc: float | None
    pervane_cap_mm: float | None


def _inc_mm(deger_inc: float | None) -> float | None:
    """İnçi mm'ye çevirir; None ise None."""
    return None if deger_inc is None else BirimDonusturucu.uzunlugu_mm_ye_cevir(deger_inc, BIRIM_INC)


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

    def dingil_mesafesi_mm(self, olculer: SasiOlculeri) -> float | None:
        """
        Çapraz motor–motor mesafesi, mm.

        Dönüş:
            Girilen dingil; yoksa dış ölçüden tahmin. Parçalı şaside dingil girilmediyse None.
        """
        if olculer.dingil_mm is not None:
            return olculer.dingil_mm
        if olculer.dingil_bilinmiyor:
            return None
        return math.hypot(olculer.en_mm, olculer.boy_mm) * self.dingil_katsayisi

    def tahmin_et(self, olculer: SasiOlculeri, motor_sayisi: int) -> float | None:
        """
        En büyük pervane çapını tahmin eder.

        Parametreler:
            olculer: Birim onaylanmış şasi ölçüleri, mm.
            motor_sayisi: Motor sayısı (motorların bir çember üzerinde eşit aralıklı olduğu kabul edilir).
        Dönüş:
            Tahmini en büyük pervane çapı, inç; şasi pervane sığmayacak kadar küçükse veya
            dingil bilinmiyorsa (parçalı şasi) None. İkisini ayırmak için önce
            olculer.dingil_bilinmiyor denetlenmeli.
        """
        dingil = self.dingil_mesafesi_mm(olculer)
        if dingil is None:
            return None
        komsu_mm = dingil * math.sin(math.pi / motor_sayisi)
        cap_mm = komsu_mm - self.uc_boslugu_mm
        if cap_mm <= 0:
            return None
        cap_inc = BirimDonusturucu.mm_yi_uzunluga_cevir(cap_mm, BIRIM_INC)
        adim_sayisi = math.floor(cap_inc / self.yuvarlama_adimi_inc + YUVARLAMA_PAYI)
        return round(adim_sayisi * self.yuvarlama_adimi_inc, SONUC_BASAMAGI)

    def gorunum(
        self, olculer: SasiOlculeri, motor_sayisi: int, pervane_cap_inc: float | None
    ) -> SasiGorunumu | None:
        """
        Üstten görünüş çizimi için gereken ölçüleri hesaplar (arayüz birim çevirmesin diye mm de verilir).

        Parametreler:
            olculer: Birim onaylanmış şasi ölçüleri, mm.
            motor_sayisi: Motor sayısı.
            pervane_cap_inc: Takılı pervanenin çapı, inç; yoksa None.
        Dönüş:
            SasiGorunumu; dingil bilinmiyorsa (parçalı şasi) None, çünkü motor yerleri çizilemez.
        """
        dingil = self.dingil_mesafesi_mm(olculer)
        if dingil is None:
            return None
        en_buyuk = self.tahmin_et(olculer, motor_sayisi)
        return SasiGorunumu(
            en_mm=olculer.en_mm,
            boy_mm=olculer.boy_mm,
            dingil_mm=dingil,
            en_buyuk_pervane_inc=en_buyuk,
            en_buyuk_pervane_mm=_inc_mm(en_buyuk),
            pervane_cap_inc=pervane_cap_inc,
            pervane_cap_mm=_inc_mm(pervane_cap_inc),
        )
