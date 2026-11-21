"""
Parçalı şaside dingil mesafesinin (çapraz motor–motor) gövde ve kol parçasından tahmini.

Parçalar dosyalarda montajdaki yerlerinde değil, baskı tablasına dizilmiş olarak durur;
motorların yeri bilinmez. Bu yüzden tek bir kolun boyu ve kolların gövdeye nasıl
bağlandığından kaba bir dingil hesaplanır. Sonuç her zaman "tahmini"dir ve kullanıcı
onaylamadan kaydedilmez; motor deliklerinin arası ölçülerek doğrulanmalıdır.

Yöntem (L = tek kolun boyu, w = kolun genişliği, R = merkezden motora uzaklık):
    Merkez bağlantı (kollar gövdenin ortasında üst üste biner, ör. Mark4 tipi):
        R = L − w × KOL_UCU_PAYI_ORANI
    Kenar bağlantı (kollar gövdenin köşesinden dışarı uzanır):
        R = gövdenin yarım köşegeni + L − w × KOL_UCU_PAYI_ORANI − w × KENAR_BINDIRME_ORANI
    Dingil = 2 × R
"""

from dataclasses import dataclass
from enum import Enum
import math
from typing import Final

from cekirdek.bicim import sayi_yaz
from cekirdek.birimler import BirimDonusturucu
from cekirdek.hatalar import GecersizDegerHatasi
from sasi.modeller import SasiParcasi

# DEĞİŞTİRİLEBİLİR: Motor merkezinin kol ucundan içeride olduğu mesafe, kol genişliğinin
# katı olarak. Motor yatağı kabaca kol genişliğinde bir daire olduğu için yarısı (0,5).
KOL_UCU_PAYI_ORANI: Final[float] = 0.5
# DEĞİŞTİRİLEBİLİR: Kenar bağlantıda kolun gövdenin altına giren (vidalanan) kısmı,
# kol genişliğinin katı olarak.
KENAR_BINDIRME_ORANI: Final[float] = 1.0
# Açıklamadaki mm değerlerinin ondalık basamağı.
ACIKLAMA_BASAMAGI: Final[int] = 0


class KolBaglantisi(str, Enum):
    """Kolların gövdeye bağlanma biçimi. Değerler arayüzden gelir; değiştirilmemeli."""

    MERKEZ = "merkez"
    KENAR = "kenar"


KOL_BAGLANTISI_ADLARI: Final[dict[KolBaglantisi, str]] = {
    KolBaglantisi.MERKEZ: "Kollar gövdenin ortasında birleşiyor",
    KolBaglantisi.KENAR: "Kollar gövdenin köşesinden dışarı uzanıyor",
}


@dataclass(frozen=True)
class DingilTahmini:
    """
    Alanlar:
        dingil_mm: Tahmini çapraz motor–motor mesafesi, mm.
        kol_boyu_mm: Hesapta kullanılan tek kolun boyu, mm.
        kol_genisligi_mm: Hesapta kullanılan kol genişliği, mm.
        aciklama: Hesabın Türkçe açıklaması.
    """

    dingil_mm: float
    kol_boyu_mm: float
    kol_genisligi_mm: float
    aciklama: str


def _yatay_olculer(parca: SasiParcasi, birim: str) -> tuple[float, float]:
    """
    Parçanın (tek gövdesinin) en uzun iki ölçüsü, mm.

    Neden en uzun iki ölçü: parça baskı için yatırılmış da olabilir, dik de; boy ve
    genişlik her durumda en uzun iki boyuttur, kalınlık en kısasıdır.
    """
    olculer = parca.geometri.tek_govde_olculeri or parca.geometri.olculer
    uzun, orta, _ = sorted((BirimDonusturucu.uzunlugu_mm_ye_cevir(d, birim) for d in olculer), reverse=True)
    return uzun, orta


class DingilHesaplayici:
    """
    Gövde ve kol parçasından dingil mesafesini tahmin eder.

    Parametreler:
        kol_ucu_payi_orani: Motor merkezinin kol ucundan içeride olduğu mesafe / kol genişliği.
        kenar_bindirme_orani: Kenar bağlantıda kolun gövdeye giren kısmı / kol genişliği.
    """

    def __init__(
        self, kol_ucu_payi_orani: float = KOL_UCU_PAYI_ORANI, kenar_bindirme_orani: float = KENAR_BINDIRME_ORANI
    ) -> None:
        self.kol_ucu_payi_orani = kol_ucu_payi_orani
        self.kenar_bindirme_orani = kenar_bindirme_orani

    def hesapla(
        self, kol: SasiParcasi, birim: str, baglanti: KolBaglantisi, govde: SasiParcasi | None = None
    ) -> DingilTahmini:
        """
        Dingil mesafesini tahmin eder.

        Parametreler:
            kol: Kol parçası (dosyada birden çok özdeş kol varsa tek birinin ölçüsü kullanılır).
            birim: Onaylanmış dosya birimi.
            baglanti: Kolların gövdeye bağlanma biçimi.
            govde: Gövde parçası; kenar bağlantıda gerekir.
        Dönüş:
            DingilTahmini (tahmini).
        Hatalar:
            GecersizDegerHatasi: Kenar bağlantıda gövde yoksa veya ölçüler hesaba elvermiyorsa.
        """
        boy, genislik = _yatay_olculer(kol, birim)
        uc_payi = genislik * self.kol_ucu_payi_orani
        yaricap = boy - uc_payi
        aciklama = [
            f"Tek kolun boyu {self._mm(boy)} mm, genişliği {self._mm(genislik)} mm.",
            f"Motor merkezi kol ucundan {self._mm(uc_payi)} mm içeride kabul edildi.",
        ]
        if baglanti is KolBaglantisi.KENAR:
            if govde is None:
                raise GecersizDegerHatasi("Kollar gövdenin köşesine bağlanıyorsa gövde parçasını da seçin.")
            govde_en, govde_boy = _yatay_olculer(govde, birim)
            yari_kosegen = math.hypot(govde_en, govde_boy) / 2
            bindirme = genislik * self.kenar_bindirme_orani
            yaricap += yari_kosegen - bindirme
            aciklama.append(
                f"Kollar gövdenin köşesinden çıkıyor: gövdenin yarım köşegeni {self._mm(yari_kosegen)} mm eklendi, "
                f"kolun gövdeye giren kısmı {self._mm(bindirme)} mm çıkarıldı."
            )
        else:
            aciklama.append("Kolların iç uçları gövdenin ortasında buluşuyor kabul edildi.")
        if yaricap <= 0:
            raise GecersizDegerHatasi(
                "Seçilen kol parçasının ölçüsünden dingil hesaplanamadı. Doğru parçayı seçtiğinizden emin olun "
                "veya dingil mesafesini elle girin."
            )
        dingil = 2 * yaricap
        aciklama.append(
            f"Dingil ≈ 2 × {self._mm(yaricap)} = {self._mm(dingil)} mm (tahmini). "
            "Çapraz iki motorun mil merkezleri arası ölçülerek doğrulanmalı."
        )
        return DingilTahmini(dingil, boy, genislik, " ".join(aciklama))

    @staticmethod
    def _mm(deger: float) -> str:
        """mm değerini açıklama için yazar."""
        return sayi_yaz(round(deger, ACIKLAMA_BASAMAGI))
