"""
Maliyet sekmesinin işlemlerini yöneten servis.

Kur yalnızca yabancı para birimli bir fiyat varsa istenir; böylece bütün fiyatlar
TL ise program hiç internete çıkmaz.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from cekirdek.ayarlar import VERITABANI_DOSYA_ADI
from depolama.veritabani import Veritabani
from elektronik.servis import ElektronikServisi
from maliyet.fiyat_deposu import ParcaFiyatDeposu, SasiFiyatDeposu, SasiMaliyeti
from maliyet.hesap import (
    GRUP_ALINACAK,
    KalemKaynagi,
    MaliyetGirdisi,
    MaliyetHesaplayici,
    MaliyetOzeti,
    parca_elimde_mi,
)
from maliyet.kur import KurDeposu, KurServisi, tcmb_xml_getir
from maliyet.para import TL, Fiyat

SASI_ADI: str = "Şasi"


@dataclass
class MaliyetSonucu:
    """
    Alanlar:
        ozet: Hesaplanmış kalemler ve toplamlar (ilk kalem şasi; parça kalemleri kaynağını taşır).
        sasi_elimde: Şasi elde mi.
        kur_notu: Kur alınamadıysa Türkçe not.
        kur_guncel_mi: Kurlar bugün alındıysa True; kur gerekmediyse None.
        butce_tl: Hedefler sekmesinde girilen bütçe; yoksa None (alınacaklarla karşılaştırılır).
    """

    ozet: MaliyetOzeti
    sasi_elimde: bool = False
    kur_notu: str | None = None
    kur_guncel_mi: bool | None = None
    butce_tl: float | None = None

    @property
    def butce_kalan_tl(self) -> float | None:
        """
        Bütçeden kalan, TL; bütçe girilmediyse None.

        Bütçe yalnızca alınacak kalemlerle karşılaştırılır (elimdekiler için para harcanmaz).
        """
        if self.butce_tl is None:
            return None
        return self.butce_tl - self.ozet.toplamlar[GRUP_ALINACAK].tl


class MaliyetServisi:
    """
    Fiyat kaydetme ve maliyet özetini yönetir.

    Parametreler:
        elektronik: Drone ve parça bilgilerine erişen ElektronikServisi.
        veri_klasoru: veri/ klasörü.
        kur_getirici: TCMB XML'ini indiren fonksiyon; testlerde sahtesi verilir.
        veritabani: Ortak Veritabani; verilmezse veri klasöründeki dosya açılır.
    """

    def __init__(
        self,
        elektronik: ElektronikServisi,
        veri_klasoru: Path,
        kur_getirici: Callable[[], bytes] = tcmb_xml_getir,
        veritabani: Veritabani | None = None,
    ) -> None:
        vt = veritabani or Veritabani(veri_klasoru / VERITABANI_DOSYA_ADI)
        self._elektronik = elektronik
        self._parca_fiyatlari = ParcaFiyatDeposu(vt)
        self._sasi_fiyatlari = SasiFiyatDeposu(vt)
        self._kurlar = KurServisi(KurDeposu(vt), kur_getirici)
        self._hesap = MaliyetHesaplayici()

    def ozet(self, drone_kimlik: int, kurlari_yenile: bool = False) -> MaliyetSonucu:
        """
        Drone'un maliyet özeti.

        Parametreler:
            drone_kimlik: Drone kimliği.
            kurlari_yenile: True ise kur bugün alınmış olsa bile yeniden alınır.
        Hatalar:
            KayitBulunamadiHatasi: Drone yoksa.
        """
        # Uyum ve uçuş hesabı gerekmediği için tam elektronik özeti yerine hafif sorgular kullanılır.
        kalemler = self._elektronik.kalemler(drone_kimlik)
        hedefler = self._elektronik.hedefler(drone_kimlik)
        sasi = self._sasi_fiyatlari.getir(drone_kimlik)
        fiyatlar = self._parca_fiyatlari.getir_hepsi([p.kimlik for _, p in kalemler])

        girdiler = [MaliyetGirdisi(SASI_ADI, 1, sasi.elimde, sasi.fiyat)]
        for bag, parca in kalemler:
            kaynak = KalemKaynagi(parca_kimlik=parca.kimlik, bag_kimlik=bag.kimlik, durum=bag.durum)
            girdiler.append(
                MaliyetGirdisi(parca.gorunen_ad, bag.adet, parca_elimde_mi(bag.durum), fiyatlar.get(parca.kimlik), kaynak)
            )

        sonuc = MaliyetSonucu(ozet=MaliyetOzeti(kalemler=[]), sasi_elimde=sasi.elimde, butce_tl=hedefler.butce_tl)
        kurlar = {}
        if any(g.fiyat is not None and g.fiyat.para_birimi != TL for g in girdiler) or kurlari_yenile:
            durum = self._kurlar.kurlar(zorla=kurlari_yenile)
            kurlar, sonuc.kur_notu, sonuc.kur_guncel_mi = durum.kurlar, durum.hata, durum.guncel_mi
        sonuc.ozet = self._hesap.hesapla(girdiler, kurlar)
        return sonuc

    def parca_fiyati_kaydet(self, parca_kimlik: int, tutar: float | None, para_birimi: str = TL) -> None:
        """
        Katalog parçasının 1 adet fiyatını yazar (tüm dronelarda geçerli); tutar None ise siler.

        Hatalar:
            KayitBulunamadiHatasi: Parça yoksa.
            GecersizDegerHatasi: Fiyat geçersizse.
        """
        self._elektronik.parca_getir(parca_kimlik)
        self._parca_fiyatlari.kaydet(parca_kimlik, Fiyat(tutar, para_birimi) if tutar is not None else None)

    def sasi_maliyeti_kaydet(self, drone_kimlik: int, tutar: float | None, para_birimi: str, elimde: bool) -> None:
        """
        Drone'un şasi fiyatını ve elde olup olmadığını yazar.

        Hatalar:
            KayitBulunamadiHatasi: Drone yoksa.
            GecersizDegerHatasi: Fiyat geçersizse.
        """
        self._elektronik.drone_getir(drone_kimlik)  # drone yoksa KayitBulunamadiHatasi
        fiyat = Fiyat(tutar, para_birimi) if tutar is not None else None
        self._sasi_fiyatlari.kaydet(drone_kimlik, SasiMaliyeti(fiyat=fiyat, elimde=elimde))
