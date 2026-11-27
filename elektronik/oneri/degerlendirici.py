"""
Önerilen adayın drone'a takılmış gibi uyum kontrolü ve uçuş hesabıyla değerlendirilmesi.

Aday, drone'daki aynı türden parçaların YERİNE konur (ör. önerilen motor mevcut
motorun alternatifi); "Diğer" türünde ise mevcutlara eklenir. Sonuçları
modelin söylediği değil, programın kendi kontrolleri belirler.
"""

from dataclasses import dataclass, field

from drone.hedefler import DroneHedefleri
from drone.modeller import Drone
from elektronik.hesap.agirlik import AgirlikHesaplayici
from elektronik.hesap.ucus import HesapDegeri, UcusHesaplayici
from elektronik.hesap.uyum import UyumDurumu, UyumSonucu
from elektronik.hesap.uyumluluk import UyumlulukKontrolcusu
from elektronik.parcalar.cekirdek_parcalar import Esc
from elektronik.parcalar.diger_parca import DigerParca
from elektronik.parcalar.parca import Parca
from elektronik.parcalar.turler import ParcaTuru
from sartname.kontrol import MaddeDurumu, MaddeSonucu, SartnameBaglami, SartnameKontrolcusu
from sartname.modeller import Madde
from sasi.modeller import SasiOlculeri

# Bu türlerden drone'da motor sayısı kadar bulunur.
MOTOR_BASINA_TURLER: frozenset[ParcaTuru] = frozenset({ParcaTuru.MOTOR, ParcaTuru.PERVANE})


@dataclass
class Degerlendirme:
    """
    Alanlar:
        adet: Adayın drone'a kaç adet takılacağı.
        ilgili_sonuclar: Adayın ilgili olduğu uyum sonuçları.
        sayilar: Bütün kontrollerde durum → adet (ör. {"uygunsuz": 1, ...}).
        itki_agirlik: Aday takılınca itki/ağırlık oranı.
        ucus_suresi_dk: Aday takılınca tahmini uçuş süresi.
        sartname_ihlalleri: Aday takılınca uyulmayan şartname maddeleri.
    """

    adet: int
    ilgili_sonuclar: list[UyumSonucu]
    sayilar: dict[str, int] = field(default_factory=dict)
    itki_agirlik: HesapDegeri | None = None
    ucus_suresi_dk: HesapDegeri | None = None
    sartname_ihlalleri: list[MaddeSonucu] = field(default_factory=list)

    @property
    def siralama_anahtari(self) -> tuple[int, int]:
        """Uyumsuzluğu veya şartname ihlali olan sona; sonra dikkat/bilinmiyor sayısı az olan öne."""
        kotu = sum(1 for s in self.ilgili_sonuclar if s.durum is UyumDurumu.UYGUNSUZ) + len(self.sartname_ihlalleri)
        belirsiz = sum(1 for s in self.ilgili_sonuclar if s.durum in (UyumDurumu.UYARI, UyumDurumu.BILINMIYOR))
        return kotu, belirsiz


class AdayDegerlendirici:
    """Adayı drone'un diğer parçalarıyla birlikte kontrol eder ve hesaplar."""

    def __init__(self) -> None:
        self._uyum = UyumlulukKontrolcusu()
        self._agirlik = AgirlikHesaplayici()
        self._ucus = UcusHesaplayici()
        self._sartname = SartnameKontrolcusu()

    @staticmethod
    def adet_belirle(aday: Parca, motor_sayisi: int) -> int:
        """Motor ve pervane motor sayısı kadar; tekli ESC motor sayısı kadar; diğerleri 1."""
        if aday.tur in MOTOR_BASINA_TURLER:
            return motor_sayisi
        if isinstance(aday, Esc) and aday.kanal_sayisi == 1:
            return motor_sayisi
        return 1

    def degerlendir(
        self,
        aday: Parca,
        drone: Drone,
        kalemler: list[tuple[Parca, int]],
        sasi_olculeri: SasiOlculeri | None,
        hedefler: DroneHedefleri | None = None,
        sartname_maddeleri: list[Madde] | None = None,
    ) -> Degerlendirme:
        """
        Parametreler:
            aday: Önerilen parça.
            drone: Drone kaydı (motor sayısı, amaç, şasi ağırlığı).
            kalemler: Drone'daki mevcut (parça, adet) listesi.
            sasi_olculeri: Şasi ölçüleri veya None.
            hedefler: Drone hedefleri (yük ağırlığa eklenir); yoksa None.
            sartname_maddeleri: Uyulacak şartname maddeleri (onaylı kesin kurallar); maliyet
                maddeleri burada değerlendirilmez (adayın fiyatı bilinmez).
        Dönüş:
            Degerlendirme.
        """
        adet = self.adet_belirle(aday, drone.motor_sayisi)
        if isinstance(aday, DigerParca):
            yeni = [*kalemler, (aday, adet)]
        else:
            yeni = [k for k in kalemler if k[0].tur is not aday.tur] + [(aday, adet)]
        sonuclar = self._uyum.kontrol_et(yeni, drone.motor_sayisi, sasi_olculeri)
        ilgili = [s for s in sonuclar if aday.gorunen_ad in s.ilgili_parcalar]
        sayilar: dict[str, int] = {}
        for s in sonuclar:
            sayilar[s.durum.value] = sayilar.get(s.durum.value, 0) + 1
        hedefler = hedefler or DroneHedefleri()
        agirlik = self._agirlik.hesapla(
            drone.sasi_agirlik_g, yeni, yuk_g=hedefler.yuk_g or 0.0, kablo_vida_g=hedefler.kablo_vida_g
        )
        ucus = self._ucus.hesapla(
            yeni, drone.motor_sayisi, drone.amac, agirlik, hedefler.ucus_suresi_dk, hedefler.itki_agirlik
        )
        ihlaller: list[MaddeSonucu] = []
        if sartname_maddeleri:
            baglam = SartnameBaglami(yeni, drone.motor_sayisi, sasi_olculeri, agirlik, ucus, hedefler)
            ihlaller = [
                s for s in self._sartname.kontrol_et(sartname_maddeleri, baglam) if s.durum is MaddeDurumu.UYGUNSUZ
            ]
        return Degerlendirme(
            adet=adet,
            ilgili_sonuclar=ilgili,
            sayilar=sayilar,
            itki_agirlik=ucus.itki_agirlik_orani,
            ucus_suresi_dk=ucus.ucus_suresi_dk,
            sartname_ihlalleri=ihlaller,
        )
