"""
Maliyet hesabı: her kalemin TL tutarı, toplamlar ve eksikler.

Toplamlar üç gruptur:
    - toplam: dronun bütün parçaları + şasi
    - alinacak: "planlanan" ve "önerilen" parçalar + (elde değilse) şasi
    - elimde: "elimde" parçalar + (eldeyse) şasi
Fiyatı girilmemiş veya kuru bulunamayan kalem toplama katılmaz ve listelenir;
böylece toplamın eksik olduğu gizlenmez. Yabancı para içeren toplam "tahmini"dir.
"""

from dataclasses import dataclass, field
from typing import Final

from elektronik.parcalar.turler import ParcaDurumu
from maliyet.kur import Kur
from maliyet.para import TL, Fiyat

GRUP_TOPLAM: Final[str] = "toplam"
GRUP_ALINACAK: Final[str] = "alinacak"
GRUP_ELIMDE: Final[str] = "elimde"

# Kalemin neden hesaplanamadığının kodu; arayüz ekran metnine değil bu koda bakar.
EKSIK_FIYAT_YOK: Final[str] = "fiyat_yok"
EKSIK_KUR_YOK: Final[str] = "kur_yok"
FIYAT_YOK_MESAJI: Final[str] = "fiyat girilmemiş"


@dataclass(frozen=True)
class KalemKaynagi:
    """
    Kalemin dronedaki karşılığı (arayüz fiyatı doğru parçaya kaydedebilsin diye).

    Alanlar:
        parca_kimlik: Katalogdaki parça.
        bag_kimlik: Drone–parça bağı.
        durum: Parçanın bu dronedaki durumu.
    """

    parca_kimlik: int
    bag_kimlik: int
    durum: ParcaDurumu


@dataclass(frozen=True)
class MaliyetGirdisi:
    """
    Hesaba giren bir kalem.

    Alanlar:
        ad: Görünen ad.
        adet: Adet.
        elimde: Kalem zaten elde mi.
        fiyat: Birim fiyat; girilmediyse None.
        kaynak: Parçanın dronedaki karşılığı; şasi için None.
    """

    ad: str
    adet: int
    elimde: bool
    fiyat: Fiyat | None
    kaynak: KalemKaynagi | None = None


@dataclass(frozen=True)
class MaliyetKalemi:
    """
    Hesaplanmış kalem.

    Alanlar:
        ad, adet, elimde, fiyat, kaynak: Girdiyle aynı.
        tl_tutar: adet × birim fiyat × kur; hesaplanamadıysa None.
        tahmini: Kurla çevrildiyse True.
        eksik: Hesaplanamadıysa nedeni (ekranda gösterilir).
        eksik_kodu: Hesaplanamadıysa EKSIK_FIYAT_YOK veya EKSIK_KUR_YOK.
    """

    ad: str
    adet: int
    elimde: bool
    fiyat: Fiyat | None
    tl_tutar: float | None
    tahmini: bool = False
    eksik: str | None = None
    eksik_kodu: str | None = None
    kaynak: KalemKaynagi | None = None


@dataclass
class Toplam:
    """
    Alanlar:
        tl: Hesaplanabilen kalemlerin toplamı, TL.
        tahmini: İçinde kurla çevrilmiş tutar varsa True.
        eksik_kalem_sayisi: Fiyatı/kuru olmadığı için katılmayan kalem sayısı.
    """

    tl: float = 0.0
    tahmini: bool = False
    eksik_kalem_sayisi: int = 0


@dataclass
class MaliyetOzeti:
    """
    Alanlar:
        kalemler: Hesaplanmış kalemler (şasi ilk sırada).
        toplamlar: Grup adı → Toplam.
        kullanilan_kurlar: Hesapta kullanılan kurlar.
    """

    kalemler: list[MaliyetKalemi]
    toplamlar: dict[str, Toplam] = field(default_factory=dict)
    kullanilan_kurlar: list[Kur] = field(default_factory=list)


def parca_elimde_mi(durum: ParcaDurumu) -> bool:
    """Drone'daki parça durumu "elimde" ise True."""
    return durum is ParcaDurumu.ELIMDE


class MaliyetHesaplayici:
    """Kalemleri kurlarla TL'ye çevirip toplar."""

    def hesapla(self, girdiler: list[MaliyetGirdisi], kurlar: dict[str, Kur]) -> MaliyetOzeti:
        """
        Parametreler:
            girdiler: Hesaba girecek kalemler.
            kurlar: Kod → Kur.
        Dönüş:
            MaliyetOzeti.
        """
        ozet = MaliyetOzeti(kalemler=[], toplamlar={g: Toplam() for g in (GRUP_TOPLAM, GRUP_ALINACAK, GRUP_ELIMDE)})
        kullanilan: dict[str, Kur] = {}
        for g in girdiler:
            kalem = self._kalem(g, kurlar)
            ozet.kalemler.append(kalem)
            if g.fiyat is not None and g.fiyat.para_birimi in kurlar:
                kullanilan[g.fiyat.para_birimi] = kurlar[g.fiyat.para_birimi]
            for grup in (GRUP_TOPLAM, GRUP_ELIMDE if g.elimde else GRUP_ALINACAK):
                toplam = ozet.toplamlar[grup]
                if kalem.tl_tutar is None:
                    toplam.eksik_kalem_sayisi += 1
                else:
                    toplam.tl += kalem.tl_tutar
                    toplam.tahmini = toplam.tahmini or kalem.tahmini
        ozet.kullanilan_kurlar = list(kullanilan.values())
        return ozet

    @staticmethod
    def _kalem(g: MaliyetGirdisi, kurlar: dict[str, Kur]) -> MaliyetKalemi:
        """Tek kalemin TL tutarı."""
        if g.fiyat is None:
            return MaliyetKalemi(
                g.ad, g.adet, g.elimde, None, None, eksik=FIYAT_YOK_MESAJI, eksik_kodu=EKSIK_FIYAT_YOK, kaynak=g.kaynak
            )
        if g.fiyat.para_birimi == TL:
            return MaliyetKalemi(g.ad, g.adet, g.elimde, g.fiyat, g.fiyat.tutar * g.adet, kaynak=g.kaynak)
        kur = kurlar.get(g.fiyat.para_birimi)
        if kur is None:
            return MaliyetKalemi(
                g.ad, g.adet, g.elimde, g.fiyat, None,
                eksik=f"{g.fiyat.para_birimi} kuru alınamadı", eksik_kodu=EKSIK_KUR_YOK, kaynak=g.kaynak,
            )
        return MaliyetKalemi(
            g.ad, g.adet, g.elimde, g.fiyat, g.fiyat.tutar * g.adet * kur.tl_karsiligi, tahmini=True, kaynak=g.kaynak
        )
