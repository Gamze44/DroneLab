"""
Tüm parçaların temel sınıfı.

Her parça türü (Motor, ESC…) bu sınıftan türer ve kendi teknik alanlarını ekler.
Kural: bilinmeyen teknik değer None olarak tutulur, asla tahmin edilip
doldurulmaz. Tahmini hesaplar ayrı yapılır ve "tahmini" diye gösterilir.
"""

from dataclasses import dataclass, fields
from typing import Any, ClassVar, Final

# metni_sadelestir buradan da dışa verilir (eski içe aktarmalar bozulmasın diye).
from cekirdek.metin import metni_sadelestir
from elektronik.parcalar.denetim import AlanCinsi, DegerDenetleyici
from elektronik.parcalar.turler import ParcaTuru

# Arama anahtarında harf ve rakam dışındaki her şey atılır (bkz. cekirdek/metin.py); böylece
# "T-Motor F60 Pro V" ile "tmotor f60pro v" aynı parça sayılır.
ANAHTAR_AYRACI: Final[str] = ":"

__all__ = ["ANAHTAR_AYRACI", "Parca", "metni_sadelestir"]


@dataclass(kw_only=True)
class Parca:
    """
    Katalogdaki bir parçanın ortak bilgileri. Doğrudan kullanılmaz; türlerden biri kullanılır.

    Alanlar:
        uretici: Marka (ör. "T-Motor"). Zorunlu.
        model: Model (ör. "F60 Pro V 1950KV"). Zorunlu.
        agirlik_g: Ağırlık, gram; bilinmiyorsa None.
        ad: Görünen ad; boşsa "üretici model" kullanılır.
        dogrulandi: Kullanıcı teknik değerleri kontrol edip onayladı mı.
        kaynak_url: Bilgilerin alındığı sayfa (http/https).
        notlar: Serbest not.
        kimlik: Katalogdaki numara; katalog dışındaki yeni parçada None.
    """

    TUR: ClassVar[ParcaTuru]
    ORTAK_ALANLAR: ClassVar[frozenset[str]] = frozenset(
        {"uretici", "model", "agirlik_g", "ad", "dogrulandi", "kaynak_url", "notlar", "kimlik"}
    )
    # Alt sınıflar, "en az – en çok" çiftlerini burada listeler; __post_init__ sırasını denetler.
    ARALIK_CIFTLERI: ClassVar[tuple[tuple[str, str], ...]] = ()

    uretici: str
    model: str
    agirlik_g: float | None = None
    ad: str | None = None
    dogrulandi: bool = False
    kaynak_url: str | None = None
    notlar: str | None = None
    kimlik: int | None = None

    def __post_init__(self) -> None:
        """Ortak ve teknik alanları denetler; geçersizse GecersizDegerHatasi fırlatır."""
        if type(self) is Parca:
            raise TypeError("Parca doğrudan kullanılamaz; Motor, ESC gibi bir tür kullanın.")
        d = DegerDenetleyici
        self.uretici = d.zorunlu_metin("uretici", self.uretici)
        self.model = d.zorunlu_metin("model", self.model)
        self.ad = d.secimli_metin(self.ad)
        self.notlar = d.secimli_metin(self.notlar)
        self.kaynak_url = d.baglanti("kaynak_url", d.secimli_metin(self.kaynak_url))
        d.pozitif_sayi("agirlik_g", self.agirlik_g)
        self.dogrulandi = bool(self.dogrulandi)
        self._teknik_alanlari_denetle()

    def _teknik_alanlari_denetle(self) -> None:
        """
        Teknik alanları TANIMLI TÜRLERİNE göre denetler, sonra türe özel denetimi çağırır.

        Sayı alanları pozitif sayı, "int" alanlar tam sayı, metin alanları metin olmalı;
        sayı listeleri pozitif sayılardan, metin listeleri metinlerden oluşmalı.
        Enum ve nesne listeleri (pil kimyası, alt tür, itki tablosu) türe özel denetime kalır.
        """
        d = DegerDenetleyici
        for alan in fields(self):
            if alan.name in self.ORTAK_ALANLAR:
                continue
            deger = getattr(self, alan.name)
            cins = d.alan_cinsi(alan.type)
            if cins == AlanCinsi.TAMSAYI:
                d.pozitif_sayi(alan.name, deger, tamsayi=True)
            elif cins == AlanCinsi.SAYI:
                d.pozitif_sayi(alan.name, deger)
            elif cins == AlanCinsi.METIN:
                setattr(self, alan.name, d.metin(alan.name, deger))
            elif cins == AlanCinsi.MANTIKSAL:
                d.mantiksal(alan.name, deger)
            elif cins == AlanCinsi.METIN_LISTESI:
                setattr(self, alan.name, d.metin_listesi(alan.name, deger))
            elif cins == AlanCinsi.SAYI_LISTESI:
                d.pozitif_sayi_listesi(alan.name, deger)
                if deger is not None and not deger:
                    setattr(self, alan.name, None)  # boş liste "bilinmiyor" ile aynı
        for alt, ust in self.ARALIK_CIFTLERI:
            d.aralik_sirasi(alt, getattr(self, alt), ust, getattr(self, ust))
        self._ture_ozel_denetim()

    def _ture_ozel_denetim(self) -> None:
        """Alt sınıfların ek kuralları için; varsayılan olarak bir şey yapmaz."""

    @property
    def tur(self) -> ParcaTuru:
        """Parçanın türü."""
        return self.TUR

    @property
    def gorunen_ad(self) -> str:
        """Ekranda gösterilecek ad: girilmişse ad, yoksa "üretici model"."""
        return self.ad or f"{self.uretici} {self.model}"

    @property
    def tur_anahtari(self) -> str:
        """Arama anahtarındaki tür kısmı; DigerParca alt türü de ekler."""
        return self.TUR.value

    @property
    def arama_anahtari(self) -> str:
        """
        Katalogda aynı parçayı tanımak için kullanılan benzersiz anahtar.

        Dönüş:
            ör. "motor:tmotor:f60prov1950kv"
        """
        return ANAHTAR_AYRACI.join(
            (self.tur_anahtari, metni_sadelestir(self.uretici), metni_sadelestir(self.model))
        )

    @property
    def arama_metni(self) -> str:
        """Serbest aramada eşleştirilecek sadeleştirilmiş metin (üretici + model + ad)."""
        return " ".join(metni_sadelestir(m) for m in (self.uretici, self.model, self.ad or "") if m)

    @classmethod
    def teknik_alan_adlari(cls) -> list[str]:
        """Bu türün teknik alanlarının adları (ortak alanlar hariç), tanım sırasıyla."""
        return [a.name for a in fields(cls) if a.name not in cls.ORTAK_ALANLAR]

    def eksik_teknik_alanlar(self) -> list[str]:
        """Değeri girilmemiş (None) teknik alanların adları; arayüz ve araştırma için."""
        return [ad for ad in self.teknik_alan_adlari() if getattr(self, ad) is None]

    def teknik_degerler(self) -> dict[str, Any]:
        """Teknik alanların ad -> değer sözlüğü (dönüştürmeden, olduğu gibi)."""
        return {ad: getattr(self, ad) for ad in self.teknik_alan_adlari()}
