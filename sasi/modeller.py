"""
Şasi bölümünün veri modelleri.

Okuyucular dosyayı SasiGeometrisi nesnesine çevirir. Bu nesnedeki ölçüler
henüz DOSYANIN KENDİ BİRİMİNDEDİR; çünkü STL gibi formatlar birim taşımaz ve
birimi kullanıcı onaylamadan mm'ye çevirmek ağırlığı kat kat bozabilir.
Birim onaylandıktan sonra mm cinsinden değerler SasiOlculeri nesnesinde tutulur.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class GeometriTuru(str, Enum):
    """Şasinin geometri türü."""

    KATI = "kati"
    """3B katı model (STL, OBJ, 3MF); hacim doğrudan hesaplanır."""

    LEVHA = "levha"
    """2B levha çizimi (DXF); hacim = alan × kalınlık, kalınlık sonra girilir."""


class OneriKaynagi(str, Enum):
    """Önerilen birimin nereden geldiği."""

    DOSYA = "dosya"
    """Birim dosyanın içinde yazıyor ve ölçüler makul."""

    TAHMIN = "tahmin"
    """Birim dosyada yok veya güvenilmez; ölçülere bakılarak tahmin edildi."""


@dataclass
class SasiGeometrisi:
    """
    Bir şasi dosyasından okunan ham geometri bilgisi.

    Alanlar (uzunluk, alan ve hacim değerleri DOSYA BİRİMİNDEDİR):
        dosya_adi: Kullanıcının yüklediği dosyanın adı.
        tur: KATI (3B) veya LEVHA (2B).
        olculer: Sınır kutusunun x, y, z boyutları; levhada z = 0.
        dosya_birimi: Dosyada yazan birim ("mm", "cm", "m", "inch"); yoksa None.
        hacim: Katı modelin hacmi (birim^3); levhada None.
        alan: Levhanın net alanı, delikler çıkarılmış (birim^2); katıda None.
        ucgen_sayisi: 3B modeldeki üçgen sayısı.
        govde_sayisi: Birbirine bağlı olmayan parça sayısı.
        kapali_mi: 3B model su geçirmez mi (hacim hesabının güvenilirliği buna bağlı).
        dis_kontur_sayisi: Levhadaki dış kontur sayısı.
        delik_sayisi: Levhadaki delik sayısı.
        uyarilar: Kullanıcıya gösterilecek Türkçe uyarılar.
        ag: 3B önizleme aşamasında kullanılacak trimesh ağı; levhada None.
        ozdes_govde_sayisi: Dosyadaki özdeş büyük gövde sayısı (ör. baskı tablasına dizilmiş
            4 kol = 4); adet önerisinde kullanılır.
        tek_govde_olculeri: En büyük tek gövdenin x, y, z boyutları (ör. tek bir kolun boyu);
            dosya tek gövdeyse olculer ile aynıdır, bilinmiyorsa None.
    """

    dosya_adi: str
    tur: GeometriTuru
    olculer: tuple[float, float, float]
    dosya_birimi: str | None = None
    hacim: float | None = None
    alan: float | None = None
    ucgen_sayisi: int = 0
    govde_sayisi: int = 0
    kapali_mi: bool = True
    dis_kontur_sayisi: int = 0
    delik_sayisi: int = 0
    uyarilar: list[str] = field(default_factory=list)
    ag: Any = field(default=None, repr=False)
    ozdes_govde_sayisi: int = 1
    tek_govde_olculeri: tuple[float, float, float] | None = None


class ParcaRolu(str, Enum):
    """Parçalı şaside bir parçanın görevi. Değerler veritabanında saklanır; değiştirilmemeli."""

    GOVDE = "govde"
    KOL = "kol"
    AYAK = "ayak"
    DIGER = "diger"


PARCA_ROLU_ADLARI: dict[ParcaRolu, str] = {
    ParcaRolu.GOVDE: "Gövde",
    ParcaRolu.KOL: "Kol",
    ParcaRolu.AYAK: "Ayak",
    ParcaRolu.DIGER: "Diğer",
}


@dataclass
class SasiParcasi:
    """
    Parçalı şasinin (zip) bir parçası.

    Alanlar:
        sira: Zip içindeki sıra (parçanın kimliği gibi kullanılır).
        geometri: Parça dosyasından okunan geometri (dosya biriminde).
        rol: Gövde / kol / ayak / diğer (program önerir, kullanıcı değiştirebilir).
        adet: Şasideki adedi (ör. tek kol dosyası için 4).
    """

    sira: int
    geometri: SasiGeometrisi
    rol: ParcaRolu = ParcaRolu.DIGER
    adet: int = 1


class DingilKaynagi(str, Enum):
    """Dingil mesafesinin nereden geldiği. Değerler saklanır; değiştirilmemeli."""

    ELLE = "elle"
    """Kullanıcı yazdı."""

    HESAP = "hesap"
    """Gövde ve kol parçasından hesaplandı ve kullanıcı onayladı (tahmini)."""


@dataclass
class KayitliSasi:
    """
    Bir drone'a bağlı, veritabanında saklanan şasi.

    Alanlar:
        saklanan_dosya: Şasi dosyasının kopyasının veri klasörüne göre yolu.
        geometri: Dosyadan okunan geometri (ag alanı saklanmaz, None gelir). Parçalı
            şaside parçaların özeti (en büyük ölçüler, adetlerle toplam hacim).
        olculer: Birim onaylandıysa mm ölçüleri; onaylanmadıysa None.
        parcalar: Parçalı şasinin (zip) parçaları; tek dosyalı şaside boş.
    """

    saklanan_dosya: str
    geometri: SasiGeometrisi
    olculer: "SasiOlculeri | None" = None
    parcalar: list[SasiParcasi] = field(default_factory=list)

    @property
    def parcali_mi(self) -> bool:
        """Şasi birden çok parça dosyasından (zip) mı oluşuyor."""
        return bool(self.parcalar)


@dataclass(frozen=True)
class BirimOnerisi:
    """
    Kullanıcıya onay için sunulan birim önerisi.

    Alanlar:
        birim: Önerilen birim.
        kaynak: Önerinin dosyadan mı geldiği, tahmin mi edildiği.
        aciklama: Önerinin nedenini anlatan Türkçe metin.
    """

    birim: str
    kaynak: OneriKaynagi
    aciklama: str


@dataclass
class SasiOlculeri:
    """
    Birim onaylandıktan sonra mm cinsinden şasi ölçüleri.

    Alanlar:
        birim: Kullanıcının onayladığı dosya birimi.
        en_mm: x boyutu, mm.
        boy_mm: y boyutu, mm.
        yukseklik_mm: z boyutu, mm (levhada 0; kalınlık sonra girilir).
        hacim_mm3: Katı modelin hacmi, mm3; levhada None.
        alan_mm2: Levhanın net alanı, mm2; katıda None.
        uyarilar: Kullanıcıya gösterilecek Türkçe uyarılar.
        dingil_mm: Kullanıcının girdiği ya da onayladığı çapraz motor–motor mesafesi;
            None ise tek dosyalı şaside dış ölçüden tahmin edilir.
        dingil_kaynagi: Dingilin nereden geldiği (elle / hesap); dingil yoksa None.
        parca_sayisi: Parçalı şaside parça dosyası sayısı; tek dosyada 0.
        tahmini: En/boy dosyadan doğrudan ölçülmediyse (parçalı şasi) True.
    """

    birim: str
    en_mm: float
    boy_mm: float
    yukseklik_mm: float
    hacim_mm3: float | None = None
    alan_mm2: float | None = None
    uyarilar: list[str] = field(default_factory=list)
    dingil_mm: float | None = None
    dingil_kaynagi: DingilKaynagi | None = None
    parca_sayisi: int = 0
    tahmini: bool = False

    @property
    def parcali_mi(self) -> bool:
        """Ölçüler parçalı (zip) şasiye mi ait."""
        return self.parca_sayisi > 0

    @property
    def dingil_bilinmiyor(self) -> bool:
        """Parçalı şaside dingil girilmediyse True (dış ölçüden tahmin edilemez)."""
        return self.parcali_mi and self.dingil_mm is None
