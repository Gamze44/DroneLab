"""
Birim dönüşümleri.

Programın iç birimleri: uzunluk mm, kütle gram, yoğunluk g/cm3, hacim mm3.
Dışarıdan gelen her değer önce bu modülle iç birime çevrilir; böylece hesap
kodunda birim karışıklığı (ör. cm yerine mm) oluşmaz. Yanlış birim ağırlığı
kat kat bozabildiği için tüm dönüşümler tek yerde toplanmıştır.
"""

import math
from typing import Final

from cekirdek.hatalar import BirimHatasi, GecersizDegerHatasi

# DEĞİŞTİRİLEBİLİR: Yeni bir uzunluk birimi eklemek için 1 biriminin kaç mm olduğunu yaz.
UZUNLUK_CARPANLARI_MM: Final[dict[str, float]] = {
    "mm": 1.0,
    "cm": 10.0,
    "m": 1000.0,
    "inch": 25.4,
}

# DEĞİŞTİRİLEBİLİR: 1 biriminin kaç gram olduğu.
KUTLE_CARPANLARI_G: Final[dict[str, float]] = {
    "g": 1.0,
    "kg": 1000.0,
}

# DEĞİŞTİRİLEBİLİR: 1 biriminin kaç g/cm3 olduğu.
YOGUNLUK_CARPANLARI_G_CM3: Final[dict[str, float]] = {
    "g/cm3": 1.0,
    "kg/m3": 0.001,
}

# 1 cm = 10 mm olduğundan 1 cm3 = 10^3 mm3.
MM3_BIR_CM3: Final[float] = 1000.0


class BirimDonusturucu:
    """
    Uzunluk, hacim, kütle ve yoğunluk değerlerini programın iç birimlerine
    (mm, mm3, g, g/cm3) çevirir ve geri çevirir.

    Durum tutmaz; tüm metotlar sınıf üzerinden doğrudan çağrılabilir.
    """

    @staticmethod
    def _birimi_normallestir(birim: str) -> str:
        """
        Birim adını karşılaştırma için sadeleştirir (boşluk ve büyük harf farkı yok sayılır).

        Parametreler:
            birim: Kullanıcının yazdığı birim adı.
        Dönüş:
            Küçük harfli, baştaki ve sondaki boşlukları silinmiş birim adı.
        """
        return birim.strip().lower()

    @classmethod
    def _carpani_bul(cls, birim: str, carpanlar: dict[str, float]) -> float:
        """
        Verilen birimin çarpanını tablodan bulur.

        Parametreler:
            birim: Birim adı.
            carpanlar: Birim adından çarpana eşleme tablosu.
        Dönüş:
            Birimin iç birime çarpanı.
        Hatalar:
            BirimHatasi: Birim tabloda yoksa.
        """
        anahtar = cls._birimi_normallestir(birim)
        if anahtar not in carpanlar:
            raise BirimHatasi(birim, carpanlar.keys())
        return carpanlar[anahtar]

    @staticmethod
    def _sonlu_mu_denetle(deger: float, ad: str) -> None:
        """
        Değerin gerçek bir sayı olduğunu denetler (NaN veya sonsuz olamaz).

        Parametreler:
            deger: Denetlenecek sayı.
            ad: Hata mesajında gösterilecek büyüklük adı (ör. "kütle").
        Hatalar:
            GecersizDegerHatasi: Değer sayı değilse veya sonsuzsa.
        """
        if not isinstance(deger, (int, float)) or isinstance(deger, bool) or not math.isfinite(deger):
            raise GecersizDegerHatasi(f"Girilen {ad} değeri geçerli bir sayı değil: {deger!r}.")

    @classmethod
    def _negatif_olmayani_denetle(cls, deger: float, ad: str) -> None:
        """
        Değerin sonlu ve sıfırdan küçük olmadığını denetler.

        Hacim, kütle ve yoğunluk fiziksel olarak negatif olamaz; koordinatlar
        olabileceği için uzunlukta bu denetim yapılmaz.

        Parametreler:
            deger: Denetlenecek sayı.
            ad: Hata mesajında gösterilecek büyüklük adı.
        Hatalar:
            GecersizDegerHatasi: Değer geçersiz veya negatifse.
        """
        cls._sonlu_mu_denetle(deger, ad)
        if deger < 0:
            raise GecersizDegerHatasi(f"{ad.capitalize()} negatif olamaz (girilen: {deger}).")

    # ---------- Uzunluk ----------

    @classmethod
    def uzunluk_carpani(cls, birim: str) -> float:
        """
        Verilen uzunluk biriminin mm karşılığını döndürür.

        Parametreler:
            birim: "mm", "cm", "m" veya "inch".
        Dönüş:
            1 birimin kaç mm olduğu.
        """
        return cls._carpani_bul(birim, UZUNLUK_CARPANLARI_MM)

    @classmethod
    def uzunlugu_mm_ye_cevir(cls, deger: float, birim: str) -> float:
        """
        Uzunluğu mm'ye çevirir.

        Parametreler:
            deger: Uzunluk değeri (koordinat olabileceği için negatif kabul edilir).
            birim: Değerin birimi.
        Dönüş:
            Uzunluk, mm.
        """
        cls._sonlu_mu_denetle(deger, "uzunluk")
        return deger * cls.uzunluk_carpani(birim)

    @classmethod
    def mm_yi_uzunluga_cevir(cls, deger_mm: float, birim: str) -> float:
        """
        mm cinsinden uzunluğu istenen birime çevirir.

        Parametreler:
            deger_mm: Uzunluk, mm.
            birim: Hedef birim.
        Dönüş:
            Uzunluk, hedef birimde.
        """
        cls._sonlu_mu_denetle(deger_mm, "uzunluk")
        return deger_mm / cls.uzunluk_carpani(birim)

    # ---------- Alan ----------

    @classmethod
    def alan_carpani(cls, birim: str) -> float:
        """
        Verilen uzunluk biriminin karesindeki alanın mm2 karşılığını döndürür.

        Parametreler:
            birim: Çizimin uzunluk birimi ("mm", "cm", "m", "inch").
        Dönüş:
            1 birim^2'nin kaç mm2 olduğu.
        """
        return cls.uzunluk_carpani(birim) ** 2

    @classmethod
    def alani_mm2_ye_cevir(cls, deger: float, birim: str) -> float:
        """
        Birim^2 cinsinden alanı mm2'ye çevirir (2D levha şasiler için).

        Parametreler:
            deger: Alan değeri, birim^2.
            birim: Uzunluk birimi.
        Dönüş:
            Alan, mm2.
        """
        cls._negatif_olmayani_denetle(deger, "alan")
        return deger * cls.alan_carpani(birim)

    # ---------- Hacim ----------

    @classmethod
    def hacim_carpani(cls, birim: str) -> float:
        """
        Verilen uzunluk biriminin küpündeki hacmin mm3 karşılığını döndürür.

        Bir çizim cm ile çizilmişse uzunluklar 10 kat, hacim 1000 kat büyür;
        bu yüzden hacim çarpanı uzunluk çarpanının küpüdür.

        Parametreler:
            birim: Çizimin uzunluk birimi ("mm", "cm", "m", "inch").
        Dönüş:
            1 birim^3'ün kaç mm3 olduğu.
        """
        return cls.uzunluk_carpani(birim) ** 3

    @classmethod
    def hacmi_mm3_e_cevir(cls, deger: float, birim: str) -> float:
        """
        Birim^3 cinsinden hacmi mm3'e çevirir.

        Parametreler:
            deger: Hacim değeri, birim^3.
            birim: Uzunluk birimi (ör. "cm" verilirse değer cm3 kabul edilir).
        Dönüş:
            Hacim, mm3.
        """
        cls._negatif_olmayani_denetle(deger, "hacim")
        return deger * cls.hacim_carpani(birim)

    @classmethod
    def mm3_u_cm3_e_cevir(cls, hacim_mm3: float) -> float:
        """
        mm3 cinsinden hacmi cm3'e çevirir (yoğunluk g/cm3 olduğu için gerekir).

        Parametreler:
            hacim_mm3: Hacim, mm3.
        Dönüş:
            Hacim, cm3.
        """
        cls._negatif_olmayani_denetle(hacim_mm3, "hacim")
        return hacim_mm3 / MM3_BIR_CM3

    # ---------- Kütle ----------

    @classmethod
    def kutleyi_grama_cevir(cls, deger: float, birim: str) -> float:
        """
        Kütleyi grama çevirir.

        Parametreler:
            deger: Kütle değeri.
            birim: "g" veya "kg".
        Dönüş:
            Kütle, gram.
        """
        cls._negatif_olmayani_denetle(deger, "kütle")
        return deger * cls._carpani_bul(birim, KUTLE_CARPANLARI_G)

    @classmethod
    def grami_kutleye_cevir(cls, deger_g: float, birim: str) -> float:
        """
        Gram cinsinden kütleyi istenen birime çevirir.

        Parametreler:
            deger_g: Kütle, gram.
            birim: Hedef birim ("g" veya "kg").
        Dönüş:
            Kütle, hedef birimde.
        """
        cls._negatif_olmayani_denetle(deger_g, "kütle")
        return deger_g / cls._carpani_bul(birim, KUTLE_CARPANLARI_G)

    # ---------- Yoğunluk ----------

    @classmethod
    def yogunlugu_g_cm3_e_cevir(cls, deger: float, birim: str) -> float:
        """
        Yoğunluğu g/cm3'e çevirir.

        Parametreler:
            deger: Yoğunluk değeri.
            birim: "g/cm3" veya "kg/m3".
        Dönüş:
            Yoğunluk, g/cm3.
        """
        cls._negatif_olmayani_denetle(deger, "yoğunluk")
        return deger * cls._carpani_bul(birim, YOGUNLUK_CARPANLARI_G_CM3)
