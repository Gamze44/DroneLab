"""
DXF okuyucusu: karbon veya alüminyum levhadan kesilen 2B şasiler için.

Çizimdeki kapalı konturlar bulunur, iç içe olanlar delik sayılır ve net alan
hesaplanır. Ağırlık daha sonra alan × kalınlık × yoğunluk olarak bulunacak;
kalınlık bu aşamada istenmez.
"""

from pathlib import Path
from typing import Final, Iterable

import ezdxf
from ezdxf import path as dxf_yolu
from ezdxf.entities import DXFGraphic

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
DXF_BIRIM_KODLARI: Final[dict[int, str]] = {1: "inch", 4: "mm", 5: "cm", 6: "m"}

# DEĞİŞTİRİLEBİLİR: Eğrileri düz parçalara bölerken izin verilen sapma ve iki ucun
# "değiyor" sayılacağı mesafe. Çizim birimi bilinmediği için sabit bir değer yerine
# çizimin köşegen uzunluğunun bu oranı kullanılır.
EGRI_SAPMA_ORANI: Final[float] = 1e-4
UC_ESLESME_ORANI: Final[float] = 1e-4


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
        uyarilar: list[str] = []

        yok_sayilan_turler: set[str] = set()
        yollar = self._yollari_topla(belge.modelspace(), yok_sayilan_turler, derinlik=0)
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
            raise DosyaOkumaHatasi(f"'{yol.name}' DXF dosyası bozuk. (Ayrıntı: {hata})") from hata

    def _yollari_topla(
        self, varliklar: Iterable[DXFGraphic], yok_sayilan_turler: set[str], derinlik: int
    ) -> list[dxf_yolu.Path]:
        """
        Geometrik öğeleri ezdxf yol (path) nesnelerine çevirir; blokları açar.

        Parametreler:
            varliklar: DXF öğeleri.
            yok_sayilan_turler: Desteklenmeyen öğe türlerinin ekleneceği küme.
            derinlik: Şu anki blok iç içelik derinliği.
        Dönüş:
            ezdxf Path listesi.
        """
        yollar: list[dxf_yolu.Path] = []
        for varlik in varliklar:
            tur = varlik.dxftype()
            if tur == "INSERT" and derinlik < EN_FAZLA_BLOK_DERINLIGI:
                yollar.extend(
                    self._yollari_topla(varlik.virtual_entities(), yok_sayilan_turler, derinlik + 1)
                )
            elif tur in GEOMETRIK_TURLER:
                try:
                    yollar.append(dxf_yolu.make_path(varlik))
                except (TypeError, ValueError):
                    # 3B ağ çoklu çizgileri gibi yola çevrilemeyen özel öğeler.
                    yok_sayilan_turler.add(tur)
            else:
                yok_sayilan_turler.add(tur)
        return [y for y in yollar if len(y) > 0 or y.start != y.end]

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
