"""
Toplam ağırlık hesabı.

Toplam = şasi + Σ(parça ağırlığı × adet) + yük + kablo/vida payı.
Kablo/vida payı kullanıcı tartıp girdiyse o değerdir; girmediyse şasi + parça ağırlığının
bir oranı olarak tahmin edilir.
Ağırlığı girilmemiş parçalar toplama katılmaz ve ayrıca listelenir; böylece
toplamın eksik olduğu kullanıcıdan gizlenmez.
"""

from dataclasses import dataclass, field
from typing import Final

from elektronik.parcalar.parca import Parca

# DEĞİŞTİRİLEBİLİR: Kablo, vida, lehim, bant gibi listelenmeyen küçük parçalar için
# parça + şasi ağırlığına eklenen pay. Gerçek değer yapıya göre değişir; bu yüzden
# pay sıfırdan büyükse toplam "tahmini" sayılır.
KABLO_PAYI_ORANI: Final[float] = 0.05


@dataclass
class AgirlikOzeti:
    """
    Ağırlık hesabının sonucu (gram).

    Alanlar:
        sasi_g: Şasi ağırlığı; girilmediyse None.
        parcalar_g: Ağırlığı bilinen parçaların toplamı (adetle çarpılmış).
        yuk_g: Taşınacak yük.
        kablo_payi_g: Kablo/vida payı (tartılmış ya da tahmini).
        toplam_g: Hepsinin toplamı (eksik ağırlıklar hariç).
        agirligi_eksik_parcalar: Ağırlığı girilmemiş parçaların görünen adları.
        tahmini: Tahmini kablo payı eklendiyse True.
        kablo_payi_elle_mi: Kablo/vida payı kullanıcının tarttığı değerse True.
    """

    sasi_g: float | None
    parcalar_g: float
    yuk_g: float
    kablo_payi_g: float
    toplam_g: float
    agirligi_eksik_parcalar: list[str] = field(default_factory=list)
    tahmini: bool = False
    kablo_payi_elle_mi: bool = False

    @property
    def eksiksiz_mi(self) -> bool:
        """Şasi ve tüm parçaların ağırlığı biliniyorsa True."""
        return self.sasi_g is not None and not self.agirligi_eksik_parcalar


class AgirlikHesaplayici:
    """
    Şasi, parça ve yük ağırlıklarından toplam ağırlığı hesaplar.

    Parametreler:
        kablo_payi_orani: Parça + şasi ağırlığına eklenecek pay oranı (0,05 = %5).
    """

    def __init__(self, kablo_payi_orani: float = KABLO_PAYI_ORANI) -> None:
        self.kablo_payi_orani: float = kablo_payi_orani

    def hesapla(
        self,
        sasi_g: float | None,
        kalemler: list[tuple[Parca, int]],
        yuk_g: float = 0.0,
        kablo_vida_g: float | None = None,
    ) -> AgirlikOzeti:
        """
        Toplam ağırlığı hesaplar.

        Parametreler:
            sasi_g: Şasi ağırlığı, gram; bilinmiyorsa None.
            kalemler: (parça, adet) listesi.
            yuk_g: Taşınacak yük, gram.
            kablo_vida_g: Tartılmış kablo/vida ağırlığı, gram; None ise oranla tahmin edilir.
        Dönüş:
            AgirlikOzeti.
        """
        parcalar_g = 0.0
        eksikler: list[str] = []
        for parca, adet in kalemler:
            if parca.agirlik_g is None:
                eksikler.append(parca.gorunen_ad)
            else:
                parcalar_g += parca.agirlik_g * adet
        # Yük bir paket olarak tartıldığı için kablo payına katılmaz.
        elle = kablo_vida_g is not None
        kablo_payi_g = kablo_vida_g if elle else (parcalar_g + (sasi_g or 0.0)) * self.kablo_payi_orani
        toplam = (sasi_g or 0.0) + parcalar_g + yuk_g + kablo_payi_g
        return AgirlikOzeti(
            sasi_g=sasi_g,
            parcalar_g=parcalar_g,
            yuk_g=yuk_g,
            kablo_payi_g=kablo_payi_g,
            toplam_g=toplam,
            agirligi_eksik_parcalar=eksikler,
            tahmini=not elle and kablo_payi_g > 0,
            kablo_payi_elle_mi=elle,
        )
