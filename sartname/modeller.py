"""
Şartname ve madde veri modelleri.

Her şartname aynı madde biçimine çevrilir: büyüklük (programın ölçtüğü değer),
sınır türü, değer, kaynak madde numarası ve sayfa. Değerler programın iç
birimlerindedir (g, mm, dakika, inç, mAh, TL); birim büyüklükten gelir.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Final

from cekirdek.hatalar import GecersizDegerHatasi
from cekirdek.sayilar import gecerli_sayi_mi


class Buyukluk(str, Enum):
    """Maddenin sınırladığı büyüklük. Değerler veritabanında saklanır; değiştirilmemeli."""

    KALKIS_AGIRLIGI = "kalkis_agirligi"
    BOYUT = "boyut"
    PERVANE_CAPI = "pervane_capi"
    MOTOR_SAYISI = "motor_sayisi"
    PIL_HUCRE = "pil_hucre"
    PIL_KAPASITE = "pil_kapasite"
    UCUS_SURESI = "ucus_suresi"
    ITKI_AGIRLIK = "itki_agirlik"
    YUK = "yuk"
    MALIYET = "maliyet"
    GPS = "gps"
    KAMERA = "kamera"
    VTX = "vtx"
    TELEMETRI = "telemetri"
    DIGER = "diger"  # program ölçemez (failsafe, acil durdurma, irtifa, hız…)


class SinirTuru(str, Enum):
    """Maddenin sınır türü."""

    EN_AZ = "en_az"
    EN_COK = "en_cok"
    ESIT = "esit"
    ZORUNLU = "zorunlu"  # parça bulunmalı (ör. GPS zorunlu)


class MaddeSinifi(str, Enum):
    """Kesin kural uyulmazsa diskalifiye eder; puanlanan kriter yalnızca bilgi olarak gösterilir."""

    KESIN = "kesin"
    PUANLANAN = "puanlanan"


@dataclass(frozen=True)
class BuyuklukTanimi:
    """
    Alanlar:
        ad: Ekranda görünen ad.
        birim: Programın iç birimi (boşsa birimsiz).
        parca_mi: Değer değil parçanın varlığına bakılır (GPS, kamera…).
    """

    ad: str
    birim: str
    parca_mi: bool = False


# DEĞİŞTİRİLEBİLİR: Ekranda görünen adlar ve birimler.
BUYUKLUK_TANIMLARI: Final[dict[Buyukluk, BuyuklukTanimi]] = {
    Buyukluk.KALKIS_AGIRLIGI: BuyuklukTanimi("Kalkış ağırlığı", "g"),
    Buyukluk.BOYUT: BuyuklukTanimi("Şasi boyutu (en/boy)", "mm"),
    Buyukluk.PERVANE_CAPI: BuyuklukTanimi("Pervane çapı", "inç"),
    Buyukluk.MOTOR_SAYISI: BuyuklukTanimi("Motor sayısı", ""),
    Buyukluk.PIL_HUCRE: BuyuklukTanimi("Pil hücre sayısı", "S"),
    Buyukluk.PIL_KAPASITE: BuyuklukTanimi("Pil kapasitesi", "mAh"),
    Buyukluk.UCUS_SURESI: BuyuklukTanimi("Uçuş süresi", "dk"),
    Buyukluk.ITKI_AGIRLIK: BuyuklukTanimi("İtki/ağırlık oranı", ""),
    Buyukluk.YUK: BuyuklukTanimi("Taşınacak yük", "g"),
    Buyukluk.MALIYET: BuyuklukTanimi("Toplam maliyet", "TL"),
    Buyukluk.GPS: BuyuklukTanimi("GPS", "", parca_mi=True),
    Buyukluk.KAMERA: BuyuklukTanimi("Kamera", "", parca_mi=True),
    Buyukluk.VTX: BuyuklukTanimi("Video verici (VTX)", "", parca_mi=True),
    Buyukluk.TELEMETRI: BuyuklukTanimi("Telemetri", "", parca_mi=True),
    Buyukluk.DIGER: BuyuklukTanimi("Diğer (program ölçemez)", ""),
}

SINIR_TURU_ADLARI: Final[dict[SinirTuru, str]] = {
    SinirTuru.EN_AZ: "en az",
    SinirTuru.EN_COK: "en çok",
    SinirTuru.ESIT: "eşit",
    SinirTuru.ZORUNLU: "zorunlu",
}

MADDE_SINIFI_ADLARI: Final[dict[MaddeSinifi, str]] = {
    MaddeSinifi.KESIN: "Kesin kural",
    MaddeSinifi.PUANLANAN: "Puanlanan kriter",
}

# DEĞİŞTİRİLEBİLİR: Metin alanlarının en çok uzunluğu.
EN_UZUN_ACIKLAMA: Final[int] = 600
EN_UZUN_MADDE_NO: Final[int] = 30


def _enum_yap(tur: type[Enum], deger: object, ad: str) -> Enum:
    if isinstance(deger, tur):
        return deger
    try:
        return tur(deger)
    except ValueError:
        raise GecersizDegerHatasi(f"{ad} tanınmıyor: {deger!r}.") from None


@dataclass
class Madde:
    """
    Şartnamenin ölçülebilir bir maddesi.

    Alanlar:
        aciklama: Maddenin kısa metni (şartnamedeki ifade).
        buyukluk: Sınırlanan büyüklük.
        sinir_turu: en az / en çok / eşit / zorunlu.
        deger: Sınır değeri (iç birimde); zorunlu parça ve "diğer" maddelerde None olabilir.
        sinif: Kesin kural veya puanlanan kriter.
        madde_no: Şartnamedeki madde numarası (ör. "4.2"); bilinmiyorsa None.
        sayfa: Belgedeki sayfa; bilinmiyorsa None.
        onaylandi: Kullanıcı maddeyi kontrol edip onayladı mı. Onaysız madde rapora "onay bekliyor" diye girer.
        kimlik: Veritabanı kimliği; kaydedilmemişse None.
    """

    aciklama: str
    buyukluk: Buyukluk
    sinir_turu: SinirTuru
    deger: float | None = None
    sinif: MaddeSinifi = MaddeSinifi.KESIN
    madde_no: str | None = None
    sayfa: int | None = None
    onaylandi: bool = False
    kimlik: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.aciklama, str) or not self.aciklama.strip():
            raise GecersizDegerHatasi("Madde açıklaması boş olamaz.")
        self.aciklama = self.aciklama.strip()[:EN_UZUN_ACIKLAMA]
        self.buyukluk = _enum_yap(Buyukluk, self.buyukluk, "Büyüklük")
        self.sinir_turu = _enum_yap(SinirTuru, self.sinir_turu, "Sınır türü")
        self.sinif = _enum_yap(MaddeSinifi, self.sinif, "Madde sınıfı")
        if self.madde_no is not None:
            self.madde_no = str(self.madde_no).strip()[:EN_UZUN_MADDE_NO] or None
        if self.sayfa is not None and (isinstance(self.sayfa, bool) or not isinstance(self.sayfa, int) or self.sayfa < 1):
            raise GecersizDegerHatasi(f"Sayfa numarası pozitif bir tam sayı olmalı (girilen: {self.sayfa!r}).")

        tanim = BUYUKLUK_TANIMLARI[self.buyukluk]
        if tanim.parca_mi:
            # Parça maddelerinde yalnızca "zorunlu" anlamlıdır; değer kullanılmaz.
            if self.sinir_turu is not SinirTuru.ZORUNLU:
                raise GecersizDegerHatasi(f"{tanim.ad} maddesinin sınır türü 'zorunlu' olmalı.")
            self.deger = None
            return
        if self.sinir_turu is SinirTuru.ZORUNLU and self.buyukluk is not Buyukluk.DIGER:
            raise GecersizDegerHatasi(f"'{tanim.ad}' için 'zorunlu' yerine en az / en çok / eşit seçilmeli.")
        if self.deger is not None:
            d = self.deger
            if not gecerli_sayi_mi(d) or d < 0:
                raise GecersizDegerHatasi(f"{tanim.ad} değeri sıfır veya pozitif bir sayı olmalı (girilen: {d!r}).")
        elif self.buyukluk is not Buyukluk.DIGER:
            raise GecersizDegerHatasi(f"'{tanim.ad}' maddesi için sınır değeri girilmeli.")


@dataclass
class Sartname:
    """
    Kütüphanedeki bir şartname.

    Alanlar:
        kimlik: Veritabanı kimliği.
        ad: Kullanıcının verdiği ad (ör. "Teknofest 2026 Uluslararası İHA").
        dosya_adi: Yüklenen belgenin özgün adı.
        saklanan_dosya: Belge kopyasının veri klasörüne göre yolu.
        yuklenme_zamani: ISO zaman.
        metin_uzunlugu: Belgeden çıkarılan metnin karakter sayısı (0 ise taranmış belge olabilir).
        madde_sayisi / onayli_madde_sayisi / kullanan_drone_sayisi: Listeleme bilgisi.
    """

    kimlik: int
    ad: str
    dosya_adi: str
    saklanan_dosya: str
    yuklenme_zamani: str
    metin_uzunlugu: int = 0
    madde_sayisi: int = 0
    onayli_madde_sayisi: int = 0
    kullanan_drone_sayisi: int = 0
