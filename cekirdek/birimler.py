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

# Birim adları; kodda yazım hatası olmasın diye metin yerine bu sabitler kullanılır.
BIRIM_MM: Final[str] = "mm"
BIRIM_CM: Final[str] = "cm"
BIRIM_M: Final[str] = "m"
BIRIM_INC: Final[str] = "inch"
BIRIM_G: Final[str] = "g"
BIRIM_KG: Final[str] = "kg"

# DEĞİŞTİRİLEBİLİR: Yeni bir uzunluk birimi eklemek için 1 biriminin kaç mm olduğunu yaz.
UZUNLUK_CARPANLARI_MM: Final[dict[str, float]] = {
    BIRIM_MM: 1.0,
    BIRIM_CM: 10.0,
    BIRIM_M: 1000.0,
    BIRIM_INC: 25.4,
}

# DEĞİŞTİRİLEBİLİR: 1 biriminin kaç gram olduğu.
KUTLE_CARPANLARI_G: Final[dict[str, float]] = {
    BIRIM_G: 1.0,
    BIRIM_KG: 1000.0,
}

# Fiziksel sabitler ve zaman/elektrik dönüşümleri (hesap modüllerinde elle çarpılmasın diye).
YERCEKIMI_M_S2: Final[float] = 9.80665  # standart yerçekimi ivmesi
MAH_BIR_AH: Final[float] = 1000.0
DAKIKA_BIR_SAAT: Final[float] = 60.0
SANIYE_BIR_DAKIKA: Final[float] = 60.0
# Dosya boyutları: 1 MB = 1024 × 1024 bayt.
BAYT_BIR_MB: Final[int] = 1024 * 1024

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
    def birimi_normallestir(birim: str) -> str:
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
        anahtar = cls.birimi_normallestir(birim)
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

    @classmethod
    def mm2_yi_cm2_ye_cevir(cls, alan_mm2: float) -> float:
        """
        mm2 cinsinden alanı cm2'ye çevirir (ekranda gösterim için).

        Parametreler:
            alan_mm2: Alan, mm2.
        Dönüş:
            Alan, cm2.
        """
        cls._negatif_olmayani_denetle(alan_mm2, "alan")
        return alan_mm2 / cls.alan_carpani(BIRIM_CM)

    # ---------- Kuvvet (itki) ----------

    @classmethod
    def gram_kuvvetini_newtona_cevir(cls, itki_g: float) -> float:
        """
        Gram-kuvveti (itki tablolarındaki "g") newtona çevirir.

        Parametreler:
            itki_g: İtki, gram-kuvvet.
        Dönüş:
            Kuvvet, N.
        """
        return cls.grami_kutleye_cevir(itki_g, BIRIM_KG) * YERCEKIMI_M_S2

    @classmethod
    def newtonu_gram_kuvvetine_cevir(cls, kuvvet_n: float) -> float:
        """
        Newtonu gram-kuvvete çevirir.

        Parametreler:
            kuvvet_n: Kuvvet, N.
        Dönüş:
            İtki, gram-kuvvet.
        """
        return cls.kutleyi_grama_cevir(kuvvet_n / YERCEKIMI_M_S2, BIRIM_KG)

    # ---------- Elektrik ve zaman ----------

    @classmethod
    def mah_i_ah_a_cevir(cls, kapasite_mah: float) -> float:
        """
        Pil kapasitesini mAh'den Ah'ye çevirir.

        Parametreler:
            kapasite_mah: Kapasite, mAh.
        Dönüş:
            Kapasite, Ah.
        """
        cls._negatif_olmayani_denetle(kapasite_mah, "kapasite")
        return kapasite_mah / MAH_BIR_AH

    @classmethod
    def saati_dakikaya_cevir(cls, sure_saat: float) -> float:
        """
        Süreyi saatten dakikaya çevirir.

        Parametreler:
            sure_saat: Süre, saat.
        Dönüş:
            Süre, dakika.
        """
        cls._sonlu_mu_denetle(sure_saat, "süre")
        return sure_saat * DAKIKA_BIR_SAAT

    @classmethod
    def dakika_basinadan_saniye_basinaya_cevir(cls, deger_dakika_basina: float) -> float:
        """
        Dakikadaki miktarı saniyedekine çevirir (ör. devir/dk → devir/sn).

        Parametreler:
            deger_dakika_basina: Dakika başına değer.
        Dönüş:
            Saniye başına değer.
        """
        cls._sonlu_mu_denetle(deger_dakika_basina, "hız")
        return deger_dakika_basina / SANIYE_BIR_DAKIKA
