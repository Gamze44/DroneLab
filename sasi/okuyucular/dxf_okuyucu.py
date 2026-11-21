"""
DXF okuyucusu: karbon veya alüminyum levhadan kesilen 2B şasiler için.

Çizimdeki kapalı konturlar bulunur, iç içe olanlar delik sayılır ve net alan
hesaplanır. Ağırlık daha sonra alan × kalınlık × yoğunluk olarak bulunacak;
kalınlık bu aşamada istenmez.
"""

import logging
import math
from pathlib import Path
from typing import Final, Iterable

import ezdxf
from ezdxf import path as dxf_yolu
from ezdxf.entities import DXFGraphic

from cekirdek.birimler import BIRIM_CM, BIRIM_INC, BIRIM_M, BIRIM_MM
from cekirdek.hatalar import DosyaOkumaHatasi
from sasi.konturlar import Kontur, KonturAlanHesaplayici, KonturBirlestirici
from sasi.modeller import GeometriTuru, SasiGeometrisi
from sasi.okuyucular.temel import SasiOkuyucu

# Şasi şeklini oluşturabilen DXF öğe türleri. Yazı, ölçü çizgisi gibi öğeler yok sayılır.
GEOMETRIK_TURLER: Final[frozenset[str]] = frozenset(
    {"LINE", "ARC", "CIRCLE", "ELLIPSE", "LWPOLYLINE", "POLYLINE", "SPLINE"}
)

# Bloklar (INSERT) iç içe olabilir; sonsuz döngüye karşı derinlik sınırı.
EN_FAZLA_BLOK_DERINLIGI: Final[int] = 10

# DXF $INSUNITS kodu -> programın birim adı. 0 "birimsiz" demektir, kullanıcıya sorulur.
DXF_BIRIM_KODLARI: Final[dict[int, str]] = {1: BIRIM_INC, 4: BIRIM_MM, 5: BIRIM_CM, 6: BIRIM_M}

# DEĞİŞTİRİLEBİLİR: Eğrileri düz parçalara bölerken izin verilen sapma ve iki ucun
# "değiyor" sayılacağı mesafe. Çizim birimi bilinmediği için sabit bir değer yerine
# çizimin köşegen uzunluğunun bu oranı kullanılır.
EGRI_SAPMA_ORANI: Final[float] = 1e-4
UC_ESLESME_ORANI: Final[float] = 1e-4

# DEĞİŞTİRİLEBİLİR: Bir çizimden alınacak en çok geometrik öğe (bloklar açıldıktan sonra).
# Bloklar iç içe çoğaltılabildiği için 50 KB'lık bir DXF milyarlarca öğeye açılabilir;
# gerçek bir şasi çizimi birkaç bin öğeyi geçmez.
EN_FAZLA_DXF_OGESI: Final[int] = 10_000
# DEĞİŞTİRİLEBİLİR: Birleştirilecek en çok açık çizgi parçası. Birleştirme parça sayısının
# karesiyle yavaşladığı için sınır, programın dakikalarca donmasını önler.
EN_FAZLA_ACIK_PARCA: Final[int] = 5_000

COK_OGELI_CIZIM_MESAJI: Final[str] = (
    "'{ad}' çizimi çok fazla öğe içeriyor (sınır {sinir}). Şasi dışındaki çizimleri (montaj, "
    "ölçü, tekrarlanan bloklar) silip yalnızca şasi levhasını dışa aktarın."
)
BOZUK_CIZIM_MESAJI: Final[str] = (
    "'{ad}' çizimindeki şekiller işlenemedi; dosya bozuk veya beklenmeyen öğeler içeriyor olabilir. "
    "Çizimi yeniden dışa aktarıp tekrar deneyin."
)

gunluk = logging.getLogger(__name__)


class _CokOgeliCizim(Exception):
    """Öğe sayısı sınırı aşıldığında toplama işlemini erken durdurmak için."""


class DxfOkuyucu(SasiOkuyucu):
    """DXF dosyalarından levha şasi geometrisini okur."""

    UZANTILAR = (".dxf",)

    def __init__(self) -> None:
        self._alan_hesaplayici = KonturAlanHesaplayici()

    def oku(self, yol: Path) -> SasiGeometrisi:
        """
        DXF dosyasını okur; dış konturları, delikleri ve net alanı çıkarır.

        Parametreler:
            yol: .dxf dosyasının yolu.
        Dönüş:
            Tür LEVHA olan SasiGeometrisi (ölçüler dosya biriminde, z = 0).
        Hatalar:
            DosyaOkumaHatasi: Dosya bozuksa veya kapalı kontur bulunamazsa.
        """
        belge = self._belgeyi_ac(yol)
        try:
            return self._belgeyi_isle(yol, belge)
        except (ValueError, ArithmeticError, RecursionError, IndexError, ezdxf.DXFError) as hata:
            # Bozuk veya aşırı uç değerli geometri (ör. sonsuz koordinat) kütüphanede çok
            # farklı hatalara yol açabilir; kullanıcı tek, anlaşılır bir mesaj görür.
            gunluk.warning("DXF işlenemedi: %s", hata)
            raise DosyaOkumaHatasi(BOZUK_CIZIM_MESAJI.format(ad=yol.name)) from hata

    def _belgeyi_isle(self, yol: Path, belge: ezdxf.document.Drawing) -> SasiGeometrisi:
        """
        Açılmış DXF belgesinden konturları, delikleri ve net alanı çıkarır (bkz. oku).

        Hatalar:
            DosyaOkumaHatasi: Şekil yoksa, çok fazla öğe varsa veya çizim boyutsuzsa.
        """
        uyarilar: list[str] = []

        yok_sayilan_turler: set[str] = set()
        yollar: list[dxf_yolu.Path] = []
        try:
            self._yollari_topla(belge.modelspace(), yok_sayilan_turler, derinlik=0, yollar=yollar)
        except _CokOgeliCizim:
            raise DosyaOkumaHatasi(COK_OGELI_CIZIM_MESAJI.format(ad=yol.name, sinir=EN_FAZLA_DXF_OGESI)) from None
        yollar = [y for y in yollar if len(y) > 0 or y.start != y.end]
        if not yollar:
            raise DosyaOkumaHatasi(
                f"'{yol.name}' dosyasında şasi çizimi bulunamadı. "
                "Çizimin çizgi, yay, daire veya çoklu çizgi içerdiğinden emin olun."
            )
        if yok_sayilan_turler:
            uyarilar.append(
                "Şu DXF öğeleri hesaba katılmadı: " + ", ".join(sorted(yok_sayilan_turler)) + "."
            )

        kutu = dxf_yolu.bbox(yollar, fast=True)
        kosegen = float(kutu.size.magnitude)
        # Tolerans köşegenden türetildiği için boyutsuz (tek nokta) veya sonsuz büyüklükte
        # bir çizim eğri bölmeyi sonsuz döngüye sokabilir.
        if not math.isfinite(kosegen) or kosegen <= 0:
            raise DosyaOkumaHatasi(
                f"'{yol.name}' çiziminin boyutu sıfır veya geçersiz. Şasi çiziminin doğru dışa aktarıldığından emin olun."
            )
        konturlar, kapanmayan = self._konturlari_cikar(yollar, kosegen)
        if not konturlar:
            raise DosyaOkumaHatasi(
                f"'{yol.name}' dosyasında kapalı bir şekil bulunamadı. "
                "Şasinin dış çizgisinin kapalı olduğundan (uçların birleştiğinden) emin olun."
            )
        if kapanmayan:
            uyarilar.append(
                f"{kapanmayan} açık çizgi kapalı bir şekle bağlanamadı ve alana katılmadı. "
                "Çizimde boşluk olup olmadığını kontrol edin."
            )

        ozet = self._alan_hesaplayici.hesapla(konturlar)
        if ozet.dis_kontur_sayisi > 1:
            uyarilar.append(
                f"Çizimde {ozet.dis_kontur_sayisi} ayrı dış parça var. "
                "Hepsinin aynı kalınlıkta levhadan kesileceği varsayılıyor."
            )

        return SasiGeometrisi(
            dosya_adi=yol.name,
            tur=GeometriTuru.LEVHA,
            olculer=(float(kutu.size.x), float(kutu.size.y), 0.0),
            dosya_birimi=self._birimi_oku(belge),
            alan=ozet.net_alan,
            govde_sayisi=ozet.dis_kontur_sayisi,
            dis_kontur_sayisi=ozet.dis_kontur_sayisi,
            delik_sayisi=ozet.delik_sayisi,
            uyarilar=uyarilar,
        )

    @staticmethod
    def _belgeyi_ac(yol: Path) -> ezdxf.document.Drawing:
        """
        DXF belgesini açar.

        Hatalar:
            DosyaOkumaHatasi: Dosya okunamaz veya DXF yapısı bozuksa.
        """
        try:
            return ezdxf.readfile(yol)
        except IOError as hata:
            raise DosyaOkumaHatasi(f"'{yol.name}' dosyası açılamadı veya geçerli bir DXF dosyası değil.") from hata
        except ezdxf.DXFStructureError as hata:
            # Kütüphanenin ham mesajı kullanıcıya değil günlüğe yazılır.
            gunluk.warning("DXF yapısı bozuk: %s", hata)
            raise DosyaOkumaHatasi(f"'{yol.name}' DXF dosyası bozuk. Çizimi yeniden dışa aktarıp deneyin.") from hata

    def _yollari_topla(
        self,
        varliklar: Iterable[DXFGraphic],
        yok_sayilan_turler: set[str],
        derinlik: int,
        yollar: list[dxf_yolu.Path],
    ) -> None:
        """
        Geometrik öğeleri ezdxf yol (path) nesnelerine çevirip listeye ekler; blokları açar.

        Liste parametreyle verilir (her çağrı yeni liste döndürmez): böylece iç içe
        bloklarda toplam öğe sayısı tek yerde sayılır ve sınır aşılınca hemen durulur.

        Parametreler:
            varliklar: DXF öğeleri.
            yok_sayilan_turler: Desteklenmeyen öğe türlerinin ekleneceği küme.
            derinlik: Şu anki blok iç içelik derinliği.
            yollar: Yolların ekleneceği liste (yerinde değiştirilir).
        Hatalar:
            _CokOgeliCizim: Öğe sayısı EN_FAZLA_DXF_OGESI'ni aşarsa.
        """
        for varlik in varliklar:
            tur = varlik.dxftype()
            if tur == "INSERT" and derinlik < EN_FAZLA_BLOK_DERINLIGI:
                self._yollari_topla(varlik.virtual_entities(), yok_sayilan_turler, derinlik + 1, yollar)
            elif tur in GEOMETRIK_TURLER:
                try:
                    yollar.append(dxf_yolu.make_path(varlik))
                except (TypeError, ValueError):
                    # 3B ağ çoklu çizgileri gibi yola çevrilemeyen özel öğeler.
                    yok_sayilan_turler.add(tur)
                if len(yollar) > EN_FAZLA_DXF_OGESI:
                    raise _CokOgeliCizim()
            else:
                yok_sayilan_turler.add(tur)

    def _konturlari_cikar(self, yollar: list[dxf_yolu.Path], kosegen: float) -> tuple[list[Kontur], int]:
        """
        Yolları düz parçalara böler, kapalı olanları ayırır, açıkları birleştirir.

        Parametreler:
            yollar: ezdxf yolları.
            kosegen: Çizimin sınır kutusu köşegeni (tolerans hesabı için).
        Dönüş:
            (kapalı konturlar, kapatılamayan zincir sayısı).
        """
        sapma = kosegen * EGRI_SAPMA_ORANI
        tolerans = kosegen * UC_ESLESME_ORANI

        kapali: list[Kontur] = []
        acik: list[Kontur] = []
        for yol in yollar:
            noktalar = [(float(n.x), float(n.y)) for n in yol.flattening(sapma)]
            if len(noktalar) < 2:
                continue
            if yol.is_closed and len(noktalar) > 2:
                kapali.append(noktalar)
            else:
                acik.append(noktalar)

        if len(acik) > EN_FAZLA_ACIK_PARCA:
            raise DosyaOkumaHatasi(
                f"Çizimde birleştirilmesi gereken {len(acik)} açık çizgi parçası var (sınır {EN_FAZLA_ACIK_PARCA}). "
                "Şasi dış hattını CAD programında tek bir kapalı çoklu çizgi (polyline) olarak dışa aktarın."
            )
        birlesenler, kapanmayan = KonturBirlestirici(tolerans).birlestir(acik)
        return kapali + birlesenler, kapanmayan

    @staticmethod
    def _birimi_oku(belge: ezdxf.document.Drawing) -> str | None:
        """
        DXF başlığındaki $INSUNITS değerinden birimi okur.

        Dönüş:
            "mm", "cm", "m", "inch" veya birim belirtilmemişse None.
        """
        kod = belge.header.get("$INSUNITS", 0)
        return DXF_BIRIM_KODLARI.get(int(kod))
