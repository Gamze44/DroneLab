"""
Uyum kontrollerinin ortak yapı taşları.

Her kontrol (K1…K13) UyumKontrolu sınıfından türeyen ayrı bir sınıftır ve
bir KontrolBaglami alıp tek bir UyumSonucu döndürür. Kural: gereken bir değer
girilmemişse sonuç "bilinmiyor" olur; eksik veri hiçbir zaman "uygun" sayılmaz
ve değer tahmin edilmez.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Final, TypeVar

from elektronik.parcalar.parca import Parca
from elektronik.parcalar.turler import alan_etiketi
from sasi.modeller import SasiOlculeri

P = TypeVar("P", bound=Parca)


class UyumDurumu(str, Enum):
    """Bir uyum kontrolünün sonucu."""

    UYGUN = "uygun"
    UYARI = "uyari"  # çalışabilir ama dikkat gerekir (ör. farklı konnektör, sınıra yakın pervane)
    UYGUNSUZ = "uygunsuz"
    BILINMIYOR = "bilinmiyor"  # gereken değer girilmemiş veya parça eklenmemiş


# Birden çok parça çifti kontrol edildiğinde sonuç en kötüsü olur; sıra kötüden iyiye.
DURUM_ONCELIGI: Final[tuple[UyumDurumu, ...]] = (
    UyumDurumu.UYGUNSUZ,
    UyumDurumu.UYARI,
    UyumDurumu.BILINMIYOR,
    UyumDurumu.UYGUN,
)


@dataclass(frozen=True)
class AraSonuc:
    """
    Bir kontrolün tek bir parça çifti için vardığı sonuç.

    Alanlar:
        durum: UyumDurumu.
        aciklama: Kısa Türkçe açıklama.
        ilgili_parcalar: Bu sonuca konu olan parçaların görünen adları.
    """

    durum: UyumDurumu
    aciklama: str
    ilgili_parcalar: tuple[str, ...] = ()


@dataclass(frozen=True)
class UyumSonucu:
    """
    Bir uyum kontrolünün sonucu.

    Alanlar:
        kod: Kontrol kodu (ör. "K1"), plandaki tabloyla aynı.
        baslik: Kontrolün adı (ör. "Pil ↔ motor hücre sayısı").
        durum: UyumDurumu.
        aciklama: Kullanıcıya gösterilecek Türkçe açıklama (birden çok satır olabilir).
        ilgili_parcalar: Sonuca konu olan parçaların görünen adları.
        tahmini: Sonuç kaba bir tahmine dayanıyorsa True (ör. şasiden pervane sınırı).
    """

    kod: str
    baslik: str
    durum: UyumDurumu
    aciklama: str
    ilgili_parcalar: tuple[str, ...] = ()
    tahmini: bool = False


@dataclass
class KontrolBaglami:
    """
    Kontrollerin ihtiyaç duyduğu bilgiler.

    Alanlar:
        kalemler: Drone'daki (parça, adet) listesi.
        motor_sayisi: Drone türüne göre motor sayısı.
        sasi_olculeri: Birim onaylanmış şasi ölçüleri (mm); yoksa None.
    """

    kalemler: list[tuple[Parca, int]]
    motor_sayisi: int
    sasi_olculeri: SasiOlculeri | None = None

    def parcalar(self, sinif: type[P]) -> list[P]:
        """Verilen sınıftaki parçaları (her model bir kez) döndürür."""
        return [p for p, _ in self.kalemler if isinstance(p, sinif)]

    def adet(self, sinif: type[Parca]) -> int:
        """Verilen sınıftaki parçaların toplam adedi."""
        return sum(adet for p, adet in self.kalemler if isinstance(p, sinif))


def eksik_mesaji(parca: Parca, *alanlar: str) -> str | None:
    """
    Parçada girilmemiş alanlar varsa "X: Y girilmemiş" mesajı döndürür.

    Parametreler:
        parca: Bakılacak parça.
        alanlar: Gereken alan adları.
    Dönüş:
        Eksik alan yoksa None, varsa Türkçe mesaj.
    """
    eksikler = [alan_etiketi(a) for a in alanlar if getattr(parca, a) is None]
    if not eksikler:
        return None
    return f"{parca.gorunen_ad}: {', '.join(eksikler)} girilmemiş"


def birlestir(kod: str, baslik: str, ara_sonuclar: list[AraSonuc], tahmini: bool = False) -> UyumSonucu:
    """
    Parça çiftlerinin sonuçlarını tek sonuca indirger: durum en kötüsü olur.

    Açıklamada yalnızca en kötü durumdaki çiftlerin mesajları yer alır; hepsi
    uygunsa tüm mesajlar gösterilir.
    """
    if not ara_sonuclar:
        raise ValueError("Birleştirilecek sonuç yok.")  # programlama hatası, kullanıcıya gitmez
    en_kotu = min((a.durum for a in ara_sonuclar), key=DURUM_ONCELIGI.index)
    secilenler = [a for a in ara_sonuclar if a.durum is en_kotu]
    ilgili: list[str] = []
    for a in secilenler:
        ilgili += [ad for ad in a.ilgili_parcalar if ad not in ilgili]
    return UyumSonucu(
        kod=kod,
        baslik=baslik,
        durum=en_kotu,
        aciklama="\n".join(dict.fromkeys(a.aciklama for a in secilenler)),
        ilgili_parcalar=tuple(ilgili),
        tahmini=tahmini,
    )


def sayi_yaz(deger: float | None) -> str:
    """Sayıyı Türkçe biçimde kısa yazar (30.5 → "30,5", 4.0 → "4"); None → "?"."""
    if deger is None:
        return "?"
    return f"{deger:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def aralik_durumu(deger: float | None, alt: float | None, ust: float | None) -> UyumDurumu:
    """
    Değerin [alt, ust] aralığında olup olmadığı.

    Sınırlardan biri bilinmese bile bilinen sınırın dışındaysa sonuç kesin
    "uygunsuz"dur; içindeyse ve bir sınır bilinmiyorsa "bilinmiyor"dur.
    """
    if deger is None:
        return UyumDurumu.BILINMIYOR
    if (alt is not None and deger < alt) or (ust is not None and deger > ust):
        return UyumDurumu.UYGUNSUZ
    if alt is None or ust is None:
        return UyumDurumu.BILINMIYOR
    return UyumDurumu.UYGUN


def metni_karsilastirmaya_hazirla(metin: str) -> str:
    """Protokol/konnektör adlarını karşılaştırma için sadeleştirir ("DShot-600" → "dshot600")."""
    return "".join(ch for ch in metin.lower() if ch.isalnum())


class UyumKontrolu(ABC):
    """
    Tek bir uyum kontrolü (ör. K1). Alt sınıflar KOD, BASLIK ve _kontrol_et'i tanımlar.

    Ortak kural: kontrol için gereken parça türlerinden biri hiç eklenmemişse sonuç
    "bilinmiyor" olur ve hangi parçanın eksik olduğu yazılır.
    """

    KOD: str = ""
    BASLIK: str = ""
    TAHMINI: bool = False

    def kontrol_et(self, baglam: KontrolBaglami) -> UyumSonucu:
        """
        Kontrolü çalıştırır.

        Parametreler:
            baglam: Drone'un parçaları ve ilgili bilgiler.
        Dönüş:
            UyumSonucu.
        """
        return birlestir(self.KOD, self.BASLIK, self._kontrol_et(baglam), tahmini=self.TAHMINI)

    @abstractmethod
    def _kontrol_et(self, baglam: KontrolBaglami) -> list[AraSonuc]:
        """Parça çiftlerini kontrol eder; en az bir AraSonuc döndürmelidir."""

    @staticmethod
    def _eklenmedi(*etiketler: str) -> list[AraSonuc]:
        """Gereken parça türü yoksa döndürülen sonuç."""
        return [AraSonuc(UyumDurumu.BILINMIYOR, f"{' ve '.join(etiketler)} eklenince kontrol edilir.")]
