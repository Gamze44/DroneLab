"""
Bir drone tasarımının bütün hesap zinciri: ağırlık → zorunlu parçalar → uyum → uçuş.

Bu sınıf veritabanına dokunmaz; verilen (parça, adet) listesiyle hesaplar. Böylece hem
kayıtlı drone'un özeti hem de asistanın "şu parçayı değiştirirsem ne olur?" (senaryo)
hesabı AYNI hesap sınıflarıyla yapılır; iki yerde farklı sonuç çıkmaz.
"""

from dataclasses import dataclass

from drone.hedefler import DroneHedefleri
from drone.modeller import Drone
from elektronik.hesap.agirlik import AgirlikHesaplayici, AgirlikOzeti
from elektronik.hesap.ucus import UcusHesaplayici, UcusOzeti
from elektronik.hesap.uyum import UyumSonucu
from elektronik.hesap.uyumluluk import UyumlulukKontrolcusu
from elektronik.parcalar.parca import Parca
from elektronik.zorunlu_parcalar import Zorunluluk, ZorunluParcaDenetleyici
from sasi.modeller import SasiOlculeri


@dataclass
class TasarimSonucu:
    """
    Alanlar:
        zorunluluklar: Zorunlu parça sonuçları.
        agirlik: Ağırlık özeti (yük hedefi dahil).
        uyum: Uyum kontrolü sonuçları (K1–K13).
        ucus: Uçuş hesabı.
    """

    zorunluluklar: list[Zorunluluk]
    agirlik: AgirlikOzeti
    uyum: list[UyumSonucu]
    ucus: UcusOzeti


class TasarimHesaplayici:
    """Drone'un parça listesinden ağırlık, zorunlu parça, uyum ve uçuş sonuçlarını hesaplar."""

    def __init__(self) -> None:
        self._agirlik = AgirlikHesaplayici()
        self._zorunlu = ZorunluParcaDenetleyici()
        self._uyum = UyumlulukKontrolcusu()
        self._ucus = UcusHesaplayici()

    def hesapla(
        self,
        drone: Drone,
        parca_adetleri: list[tuple[Parca, int]],
        sasi_olculeri: SasiOlculeri | None,
        hedefler: DroneHedefleri,
    ) -> TasarimSonucu:
        """
        Parametreler:
            drone: Drone (tür, amaç ve elle girilen şasi ağırlığı buradan okunur).
            parca_adetleri: (parça, adet) listesi.
            sasi_olculeri: Birim onaylanmış şasi ölçüleri; yoksa None.
            hedefler: Drone hedefleri (yük ağırlığa, uçuş süresi hedefi uçuş hesabına girer).
        Dönüş:
            TasarimSonucu.
        """
        agirlik = self._agirlik.hesapla(drone.sasi_agirlik_g, parca_adetleri, yuk_g=hedefler.yuk_g or 0.0)
        return TasarimSonucu(
            zorunluluklar=self._zorunlu.denetle(parca_adetleri, drone.motor_sayisi, drone.amac),
            agirlik=agirlik,
            uyum=self._uyum.kontrol_et(parca_adetleri, drone.motor_sayisi, sasi_olculeri),
            ucus=self._ucus.hesapla(
                parca_adetleri, drone.motor_sayisi, drone.amac, agirlik, hedef_ucus_suresi_dk=hedefler.ucus_suresi_dk
            ),
        )
