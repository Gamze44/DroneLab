"""
Elektronik bölümünün işlemlerini yöneten servis.

Arayüz (API uçları) katalog, drone–parça deposu ve hesaplara doğrudan gitmez;
bu sınıfı çağırır. Böylece "yeni parçayı kataloğa ekle ve drone'a bağla" gibi
çok adımlı işler tek yerde durur ve HTTP olmadan test edilebilir.
"""

from dataclasses import dataclass, field, fields, replace
from pathlib import Path
from typing import Any, Final

from cekirdek.ayarlar import VERITABANI_DOSYA_ADI
from cekirdek.hatalar import GecersizDegerHatasi
from depolama.drone_deposu import DroneDeposu
from depolama.hedef_deposu import HedefDeposu
from depolama.sasi_kayit_deposu import SasiKayitDeposu
from depolama.veritabani import Veritabani
from drone.hedefler import DroneHedefleri
from drone.modeller import Drone
from elektronik.parcalar.cekirdek_parcalar import ItkiNoktasi, Motor
from elektronik.drone_parca_deposu import DroneParcaDeposu
from elektronik.hesap.agirlik import AgirlikHesaplayici, AgirlikOzeti
from elektronik.hesap.ucus import UcusHesaplayici, UcusOzeti
from elektronik.hesap.uyum import UyumSonucu
from elektronik.hesap.uyumluluk import UyumlulukKontrolcusu
from elektronik.katalog import ParcaKatalogu
from elektronik.parcalar.drone_parcasi import DroneParcasi
from elektronik.parcalar.parca import Parca
from elektronik.parcalar.serilestirme import ParcaSerilestirici
from elektronik.parcalar.turler import DigerAltTur, ParcaDurumu, ParcaTuru
from elektronik.zorunlu_parcalar import Zorunluluk, ZorunluParcaDenetleyici
from sasi.modeller import SasiOlculeri

# İtki tablosu satırında kabul edilen alanlar (bilinmeyen alanlar yok sayılır).
ITKI_ALANLARI: Final[tuple[str, ...]] = tuple(f.name for f in fields(ItkiNoktasi))


@dataclass
class ElektronikOzeti:
    """
    Bir drone'un elektronik sekmesinde gösterilecek her şey.

    Alanlar:
        drone: Drone kaydı.
        kalemler: (bağ, parça) çiftleri, eklenme sırasıyla.
        zorunluluklar: Zorunlu parça sonuçları.
        agirlik: Ağırlık özeti.
        uyum: Uyum kontrolü sonuçları (K1–K13).
        ucus: Uçuş hesabı.
        sasi_olculeri: Birim onaylanmış şasi ölçüleri; yoksa None.
    """

    drone: Drone
    kalemler: list[tuple[DroneParcasi, Parca]]
    zorunluluklar: list[Zorunluluk]
    agirlik: AgirlikOzeti
    uyum: list[UyumSonucu]
    ucus: UcusOzeti
    sasi_olculeri: SasiOlculeri | None = None
    hedefler: DroneHedefleri = field(default_factory=DroneHedefleri)

    @property
    def parca_adetleri(self) -> list[tuple[Parca, int]]:
        """(parça, adet) listesi; hesap ve kontrol sınıflarının beklediği biçim."""
        return [(parca, bag.adet) for bag, parca in self.kalemler]


class ElektronikServisi:
    """
    Drone'a parça ekleme/çıkarma, katalog arama ve özet hesaplarını yönetir.

    Parametreler:
        veri_klasoru: Veritabanının bulunduğu klasör (veri/).
        veritabani: Ortak Veritabani; verilmezse veri klasöründeki dosya açılır.
    """

    def __init__(self, veri_klasoru: Path, veritabani: Veritabani | None = None) -> None:
        veritabani = veritabani or Veritabani(veri_klasoru / VERITABANI_DOSYA_ADI)
        self._dronelar = DroneDeposu(veritabani)
        self._katalog = ParcaKatalogu(veritabani)
        self._baglar = DroneParcaDeposu(veritabani)
        self._serilestirici = ParcaSerilestirici()
        self._sasiler = SasiKayitDeposu(veritabani)
        self._hedefler = HedefDeposu(veritabani)
        self._zorunlu = ZorunluParcaDenetleyici()
        self._agirlik = AgirlikHesaplayici()
        self._uyum = UyumlulukKontrolcusu()
        self._ucus = UcusHesaplayici()

    # ---------- Okuma ----------

    def ozet(self, drone_kimlik: int) -> ElektronikOzeti:
        """
        Drone'un parça listesini, zorunlu parça durumunu, ağırlık özetini, uyum
        kontrollerini ve uçuş hesabını döndürür.

        Hatalar:
            KayitBulunamadiHatasi: Drone yoksa.
        """
        drone = self._dronelar.getir(drone_kimlik)
        baglar = self._baglar.listele(drone_kimlik)
        parcalar = self._katalog.getir_hepsi(bag.parca_kimlik for bag in baglar)
        # Bağlı parça katalogdan silinemez (RESTRICT); yine de iki sorgu arasında bağ ve
        # parça birlikte silinmişse o kalem atlanır, özet hata vermez.
        kalemler = [(bag, parcalar[bag.parca_kimlik]) for bag in baglar if bag.parca_kimlik in parcalar]
        parca_adetleri = [(parca, bag.adet) for bag, parca in kalemler]
        sasi = self._sasiler.getir(drone_kimlik)
        hedefler = self._hedefler.getir(drone_kimlik)
        agirlik = self._agirlik.hesapla(drone.sasi_agirlik_g, parca_adetleri, yuk_g=hedefler.yuk_g or 0.0)
        return ElektronikOzeti(
            drone=drone,
            kalemler=kalemler,
            zorunluluklar=self._zorunlu.denetle(parca_adetleri, drone.motor_sayisi, drone.amac),
            agirlik=agirlik,
            uyum=self._uyum.kontrol_et(parca_adetleri, drone.motor_sayisi, sasi.olculer if sasi else None),
            ucus=self._ucus.hesapla(
                parca_adetleri, drone.motor_sayisi, drone.amac, agirlik, hedef_ucus_suresi_dk=hedefler.ucus_suresi_dk
            ),
            sasi_olculeri=sasi.olculer if sasi else None,
            hedefler=hedefler,
        )

    # ---------- Hedefler ve itki tablosu ----------

    def hedefleri_kaydet(self, drone_kimlik: int, hedefler: DroneHedefleri) -> DroneHedefleri:
        """
        Drone'un hedeflerini (uçuş süresi, yük, bütçe) kaydeder.

        Hatalar:
            KayitBulunamadiHatasi: Drone yoksa.
        """
        self._dronelar.getir(drone_kimlik)
        self._hedefler.kaydet(drone_kimlik, hedefler)
        self._dronelar.guncellendi_olarak_isaretle(drone_kimlik)
        return hedefler

    def itki_tablosu_kaydet(self, parca_kimlik: int, satirlar: list[dict[str, Any]]) -> Parca:
        """
        Katalogdaki motorun itki tablosunu değiştirir (boş liste tabloyu siler).

        Tablo katalogda durduğu için bu motoru kullanan tüm dronelarda geçerlidir.
        Parçanın "doğrulandı" durumu değişmez; yalnızca tablo yazılır.

        Hatalar:
            KayitBulunamadiHatasi: Parça yoksa.
            GecersizDegerHatasi: Parça motor değilse veya bir satır geçersizse.
        """
        motor = self._katalog.getir(parca_kimlik)
        if not isinstance(motor, Motor):
            raise GecersizDegerHatasi("İtki tablosu yalnızca motorlar için girilebilir.")
        noktalar = []
        for sira, satir in enumerate(satirlar, start=1):
            bilinen = {ad: satir.get(ad) for ad in ITKI_ALANLARI}
            try:
                noktalar.append(ItkiNoktasi(**bilinen))
            except GecersizDegerHatasi as hata:
                raise GecersizDegerHatasi(f"İtki tablosu {sira}. satır: {hata.mesaj}") from None
        return self._katalog.guncelle(replace(motor, itki_tablosu=noktalar or None))

    def drone_getir(self, drone_kimlik: int) -> Drone:
        """Drone kaydını döndürür. Hatalar: KayitBulunamadiHatasi."""
        return self._dronelar.getir(drone_kimlik)

    def parca_getir(self, parca_kimlik: int) -> Parca:
        """Katalogdaki parçayı döndürür. Hatalar: KayitBulunamadiHatasi."""
        return self._katalog.getir(parca_kimlik)

    def katalogdaki_karsiligi(self, parca: Parca) -> Parca | None:
        """Aynı tür, üretici ve modeldeki katalog kaydını döndürür; yoksa None."""
        return self._katalog.ayni_parcayi_bul(parca)

    def katalog_ara(
        self, metin: str = "", tur: ParcaTuru | None = None, alt_tur: DigerAltTur | None = None
    ) -> list[Parca]:
        """Katalogda parça arar (bkz. ParcaKatalogu.ara)."""
        return self._katalog.ara(metin, tur=tur, alt_tur=alt_tur)

    # ---------- Parça oluşturma ----------

    def parca_olustur(
        self, tur: ParcaTuru | str, alt_tur: DigerAltTur | str | None, ortak: dict[str, Any], teknik: dict[str, Any]
    ) -> Parca:
        """
        Form verisinden (henüz kaydedilmemiş) parça nesnesi oluşturur.

        Elle girilen parça "doğrulandı" sayılır: değerleri kullanıcı kendisi yazdı.

        Hatalar:
            GecersizDegerHatasi: Bir değer geçersizse.
        """
        teknik = dict(teknik)
        if ParcaTuru(tur) is ParcaTuru.DIGER:
            if not alt_tur:
                raise GecersizDegerHatasi("Diğer parçalar için alt tür (kamera, VTX, GPS…) seçilmeli.")
            teknik["alt_tur"] = alt_tur
        ortak = {**ortak, "dogrulandi": True, "kimlik": None}
        return self._serilestirici.sozlukten_olustur(tur, ortak, teknik)

    def oneri_parcasi_olustur(
        self, tur: ParcaTuru | str, alt_tur: DigerAltTur | str | None, ortak: dict[str, Any], teknik: dict[str, Any]
    ) -> Parca:
        """
        Yapay zekanın önerdiği parçayı "doğrulanmadı" olarak oluşturur (kaydetmez).

        Değerler internette aranmadan modelin bilgisinden geldiği için kullanıcı
        kontrol edip "Düzenle → Kaydet" ile onaylayana kadar doğrulanmamış sayılır.

        Hatalar:
            GecersizDegerHatasi: Bir değer geçersizse.
        """
        parca = self.parca_olustur(tur, alt_tur, ortak, teknik)
        parca.dogrulandi = False
        return parca

    # ---------- Drone'a parça ekleme / değiştirme ----------

    def yeni_parca_ekle(self, drone_kimlik: int, parca: Parca, adet: int, durum: ParcaDurumu | str) -> DroneParcasi:
        """
        Yeni parçayı kataloğa kaydeder ve drone'a bağlar.

        Hatalar:
            KayitBulunamadiHatasi: Drone yoksa.
            KayitZatenVarHatasi: Aynı parça katalogda varsa; arayüz mevcut kaydı önerir.
            GecersizDegerHatasi: Adet/durum geçersizse.
        """
        self._dronelar.getir(drone_kimlik)
        # Bağ, katalog kaydından ÖNCE denetlenir ki geçersiz adet yüzünden katalogda yetim kayıt kalmasın.
        DroneParcasi(drone_kimlik=drone_kimlik, parca_kimlik=0, adet=adet, durum=durum)
        kayitli = self._katalog.ekle(parca)
        return self._bagla(drone_kimlik, kayitli.kimlik, adet, durum)

    def katalogdan_ekle(self, drone_kimlik: int, parca_kimlik: int, adet: int, durum: ParcaDurumu | str) -> DroneParcasi:
        """
        Katalogdaki mevcut parçayı drone'a bağlar.

        Hatalar:
            KayitBulunamadiHatasi: Drone veya parça yoksa.
            KayitZatenVarHatasi: Parça bu drone'da zaten varsa.
        """
        self._dronelar.getir(drone_kimlik)
        self._katalog.getir(parca_kimlik)
        return self._bagla(drone_kimlik, parca_kimlik, adet, durum)

    def _bagla(self, drone_kimlik: int, parca_kimlik: int, adet: int, durum: ParcaDurumu | str) -> DroneParcasi:
        """Bağı kaydeder ve drone'un son değişiklik zamanını günceller."""
        bag = self._baglar.ekle(
            DroneParcasi(drone_kimlik=drone_kimlik, parca_kimlik=parca_kimlik, adet=adet, durum=durum)
        )
        self._dronelar.guncellendi_olarak_isaretle(drone_kimlik)
        return bag

    def bag_guncelle(
        self, drone_kimlik: int, bag_kimlik: int, adet: int | None, durum: ParcaDurumu | str | None
    ) -> DroneParcasi:
        """Drone'daki parçanın adedini/durumunu değiştirir."""
        bag = self._baglar.guncelle(drone_kimlik, bag_kimlik, adet=adet, durum=durum)
        self._dronelar.guncellendi_olarak_isaretle(drone_kimlik)
        return bag

    def bag_sil(self, drone_kimlik: int, bag_kimlik: int) -> None:
        """Parçayı drone'dan kaldırır; parça katalogda kalır."""
        self._baglar.sil(drone_kimlik, bag_kimlik)
        self._dronelar.guncellendi_olarak_isaretle(drone_kimlik)

    # ---------- Katalog parçasını düzenleme ----------

    def parca_guncelle(self, parca_kimlik: int, ortak: dict[str, Any], teknik: dict[str, Any]) -> Parca:
        """
        Katalogdaki parçanın bilgilerini değiştirir.

        Formda bulunmayan teknik alanlar (ör. itki tablosu) mevcut değerini korur.
        Kullanıcı değerleri kendisi düzenlediği için parça "doğrulandı" olur.
        Katalog ortak olduğu için değişiklik bu parçayı kullanan tüm droneları etkiler.

        Hatalar:
            KayitBulunamadiHatasi, KayitZatenVarHatasi, GecersizDegerHatasi.
        """
        mevcut = self._katalog.getir(parca_kimlik)
        birlesik_teknik = {**self._serilestirici.teknik_sozluk(mevcut), **teknik}
        yeni = self._serilestirici.sozlukten_olustur(
            mevcut.tur, {**ortak, "kimlik": parca_kimlik, "dogrulandi": True}, birlesik_teknik
        )
        return self._katalog.guncelle(yeni)
