"""
Drone işlemlerini yöneten servis.

Arayüz (API uçları) doğrudan veritabanına veya okuyuculara gitmez; bu sınıfı
çağırır. Böylece "şasi yükle" gibi birden çok adımlı işlemler (dosyayı oku,
kopyala, kaydet) tek yerde durur ve HTTP olmadan da test edilebilir.
"""

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final

from cekirdek.ayarlar import SASI_DOSYALARI_KLASOR_ADI, VERITABANI_DOSYA_ADI
from cekirdek.birimler import BirimDonusturucu
from cekirdek.hatalar import GecersizDegerHatasi, KayitBulunamadiHatasi
from depolama.dosya_deposu import SasiDosyaDeposu
from depolama.drone_deposu import DroneDeposu
from depolama.hedef_deposu import HedefDeposu
from depolama.sasi_kayit_deposu import SasiKayitDeposu
from depolama.veritabani import Veritabani
from drone.dogrulama import DroneGirdisiDogrulayici
from drone.hedefler import DroneHedefleri
from drone.modeller import BaslangicTuru, Drone, DroneTuru
from sasi.birim_dogrulayici import BirimDogrulayici
from sasi.dingil import DingilHesaplayici, DingilTahmini, KolBaglantisi
from sasi.modeller import (
    BirimOnerisi,
    DingilKaynagi,
    KayitliSasi,
    SasiGeometrisi,
    SasiOlculeri,
    SasiParcasi,
)
from sasi.okuyucu_secici import OkuyucuSecici
from sasi.parca_onerici import ParcaOnerici
from sasi.parcali_olcu import ParcaliSasiOzetleyici

SASI_YOK_MESAJI: Final[str] = "Bu drone için henüz şasi dosyası yüklenmedi."
BIRIM_ONAYSIZ_MESAJI: Final[str] = "Önce şasinin birimini onaylayın (Şasi sekmesi)."
PARCALI_DEGIL_MESAJI: Final[str] = "Bu işlem yalnızca parçalı (zip) şasilerde yapılır."


@dataclass(frozen=True)
class ParcaDegisikligi:
    """
    Kullanıcının bir şasi parçası için seçtiği rol ve adet.

    Alanlar:
        sira: Parçanın sırası.
        rol: Rol değeri ("govde", "kol", "ayak", "diger").
        adet: Adet.
    """

    sira: int
    rol: str
    adet: int


@dataclass
class DroneAyrintisi:
    """
    Bir drone'un çalışma sayfasında gereken tüm bilgisi.

    Alanlar:
        drone: Drone kaydı.
        sasi: Şasi kaydı; yüklenmediyse None.
    """

    drone: Drone
    sasi: KayitliSasi | None


class DroneServisi:
    """
    Drone oluşturma, listeleme, silme ve şasi adımlarını yönetir.

    Parametreler:
        veri_klasoru: Veritabanı ve şasi dosyalarının tutulacağı klasör.
        veritabani: Ortak Veritabani; verilmezse veri klasöründeki dosya açılır.
    """

    def __init__(self, veri_klasoru: Path, veritabani: Veritabani | None = None) -> None:
        veritabani = veritabani or Veritabani(veri_klasoru / VERITABANI_DOSYA_ADI)
        self._dronelar = DroneDeposu(veritabani)
        self._sasiler = SasiKayitDeposu(veritabani)
        self._hedefler = HedefDeposu(veritabani)
        self._dosyalar = SasiDosyaDeposu(veri_klasoru / SASI_DOSYALARI_KLASOR_ADI)
        self._okuyucu_secici = OkuyucuSecici()
        self._birim_dogrulayici = BirimDogrulayici()
        self._girdi_dogrulayici = DroneGirdisiDogrulayici()
        self._parca_onerici = ParcaOnerici()
        self._ozetleyici = ParcaliSasiOzetleyici(self._birim_dogrulayici)
        self._dingil = DingilHesaplayici()

    # ---------- Drone ----------

    def olustur(self, ad: str, baslangic_turu: BaslangicTuru, drone_turu: DroneTuru, amac: str) -> Drone:
        """
        Girdileri doğrulayıp yeni drone oluşturur.

        Hatalar:
            GecersizDegerHatasi: Ad veya amaç geçersizse.
        """
        return self._dronelar.olustur(
            self._girdi_dogrulayici.ad_dogrula(ad),
            baslangic_turu,
            drone_turu,
            self._girdi_dogrulayici.amac_dogrula(amac),
        )

    def listele(self) -> list[Drone]:
        """Kayıtlı droneları son değiştirilen en üstte olacak şekilde döndürür."""
        return self._dronelar.listele()

    def ayrinti(self, kimlik: int) -> DroneAyrintisi:
        """
        Drone'u ve şasi kaydını birlikte döndürür.

        Hatalar:
            KayitBulunamadiHatasi: Drone yoksa.
        """
        return DroneAyrintisi(drone=self._dronelar.getir(kimlik), sasi=self._sasiler.getir(kimlik))

    def sil(self, kimlik: int) -> None:
        """
        Drone'u, şasi kaydını ve saklanan şasi dosyasını siler.

        Hatalar:
            KayitBulunamadiHatasi: Drone yoksa.
        """
        self._dronelar.sil(kimlik)
        self._dosyalar.sil(kimlik)

    # ---------- Şasi ----------

    def dosya_turunu_denetle(self, dosya_adi: str) -> None:
        """
        Dosya türünün okunabildiğini denetler.

        Dosya diske yazılmadan önce çağrılır; böylece desteklenmeyen büyük
        bir dosya boşuna kaydedilmez.

        Hatalar:
            DesteklenmeyenDosyaHatasi: Tür desteklenmiyorsa.
        """
        self._okuyucu_secici.denetle(dosya_adi)

    def sasi_yukle(self, kimlik: int, gecici_yol: Path, dosya_adi: str) -> tuple[KayitliSasi, Drone]:
        """
        Şasi dosyasını (veya parçalı şasi zip'ini) okur, kopyasını saklar ve drone'a bağlar.

        Drone'un daha önce bir şasisi varsa yeni dosya onun yerine geçer ve
        elle girilen ağırlık silinir, çünkü o ağırlık eski şasiye aitti.
        Zip'te her parçaya rol ve adet önerilir; kullanıcı sonra değiştirebilir.

        Parametreler:
            kimlik: Drone kimliği.
            gecici_yol: Yüklenen dosyanın geçici yolu.
            dosya_adi: Kullanıcının dosyasının asıl adı.
        Dönüş:
            (yeni şasi kaydı, güncel drone).
        Hatalar:
            KayitBulunamadiHatasi, DesteklenmeyenDosyaHatasi, DosyaOkumaHatasi.
        """
        drone = self._dronelar.getir(kimlik)
        parcalar: list[SasiParcasi] = []
        if self._okuyucu_secici.parcali_mi(dosya_adi):
            okunan = self._okuyucu_secici.parcali_okuyucu().oku(gecici_yol)
            parcalar = self._parca_onerici.oner(okunan.parcalar, drone.motor_sayisi)
            geometri = self._ozetleyici.ozet_geometri(dosya_adi, parcalar, okunan.uyarilar)
        else:
            geometri = self._okuyucu_secici.sec(dosya_adi).oku(gecici_yol)
            geometri.dosya_adi = dosya_adi

        saklanan = self._dosyalar.kaydet(kimlik, gecici_yol)
        self._sasiler.kaydet(kimlik, saklanan, geometri, parcalar)

        if drone.sasi_var:
            drone = self._dronelar.sasi_agirligini_ayarla(kimlik, None)
        else:
            self._dronelar.guncellendi_olarak_isaretle(kimlik)
            drone = self._dronelar.getir(kimlik)
        return KayitliSasi(saklanan_dosya=saklanan, geometri=geometri, parcalar=parcalar), drone

    def birim_oner(self, geometri: SasiGeometrisi) -> BirimOnerisi:
        """Şasi geometrisi için birim önerisi döndürür."""
        return self._birim_dogrulayici.birim_oner(geometri)

    def birim_onayla(self, kimlik: int, birim: str) -> SasiOlculeri:
        """
        Onaylanan birimle mm ölçülerini hesaplar ve kaydeder.

        Daha önce girilen dingil korunur. Yalnızca parçalardan HESAPLANMIŞ dingil, birim
        değiştiyse silinir; çünkü o hesap eski birimle yapılmıştı.

        Hatalar:
            KayitBulunamadiHatasi: Drone yoksa veya şasi yüklenmemişse.
            BirimHatasi: Birim tanınmıyorsa.
        """
        drone = self._dronelar.getir(kimlik)
        sasi = self._sasi_getir(kimlik)
        birim = BirimDonusturucu.birimi_normallestir(birim)
        dingil, kaynak = None, None
        onceki = sasi.olculer
        if onceki is not None and onceki.dingil_mm is not None:
            if onceki.dingil_kaynagi is not DingilKaynagi.HESAP or onceki.birim == birim:
                dingil, kaynak = onceki.dingil_mm, onceki.dingil_kaynagi
        olculer = self._olculeri_hesapla(sasi, birim, drone.motor_sayisi, dingil, kaynak)
        self._sasiler.olculeri_kaydet(kimlik, olculer)
        self._dronelar.guncellendi_olarak_isaretle(kimlik)
        return olculer

    # ---------- Parçalı şasi ve dingil ----------

    def parcalari_guncelle(self, kimlik: int, degisiklikler: list[ParcaDegisikligi]) -> KayitliSasi:
        """
        Parçalı şaside parçaların rolünü ve adedini kaydeder; toplam hacmi ve ölçüleri yeniler.

        Parametreler:
            kimlik: Drone kimliği.
            degisiklikler: Değişen parçalar (listede olmayanlar değişmez).
        Dönüş:
            Güncel şasi kaydı.
        Hatalar:
            KayitBulunamadiHatasi: Drone, şasi veya parça yoksa.
            GecersizDegerHatasi: Şasi parçalı değilse, rol veya adet geçersizse.
        """
        drone = self._dronelar.getir(kimlik)
        sasi = self._parcali_sasi_getir(kimlik)
        parcalar = {p.sira: p for p in sasi.parcalar}
        for d in degisiklikler:
            parca = parcalar.get(d.sira)
            if parca is None:
                raise KayitBulunamadiHatasi("Şasi parçası bulunamadı; sayfayı yenileyip tekrar deneyin.")
            ad = parca.geometri.dosya_adi
            parcalar[d.sira] = replace(
                parca,
                rol=self._girdi_dogrulayici.parca_rolu_dogrula(d.rol, ad),
                adet=self._girdi_dogrulayici.parca_adedi_dogrula(d.adet, ad),
            )
        sasi.parcalar = sorted(parcalar.values(), key=lambda p: p.sira)
        sasi.geometri = self._ozetleyici.toplamlari_guncelle(sasi.geometri, sasi.parcalar)
        self._sasiler.parcalari_guncelle(kimlik, sasi.geometri, sasi.parcalar)
        if sasi.olculer is not None:
            o = sasi.olculer
            sasi.olculer = self._olculeri_hesapla(sasi, o.birim, drone.motor_sayisi, o.dingil_mm, o.dingil_kaynagi)
            self._sasiler.olculeri_kaydet(kimlik, sasi.olculer)
        self._dronelar.guncellendi_olarak_isaretle(kimlik)
        return sasi

    def dingil_hesapla(
        self, kimlik: int, kol_sira: int, baglanti: KolBaglantisi, govde_sira: int | None = None
    ) -> DingilTahmini:
        """
        Parçalı şaside seçilen gövde ve kol parçasından dingil mesafesini tahmin eder (KAYDETMEZ).

        Sonuç kullanıcıya gösterilir; kullanıcı onaylarsa dingil_kaydet çağrılır.

        Parametreler:
            kimlik: Drone kimliği.
            kol_sira: Kol parçasının sırası.
            baglanti: Kolların gövdeye bağlanma biçimi.
            govde_sira: Gövde parçasının sırası (kenar bağlantıda gerekir).
        Dönüş:
            DingilTahmini.
        Hatalar:
            KayitBulunamadiHatasi: Drone, şasi veya parça yoksa.
            GecersizDegerHatasi: Şasi parçalı değilse, birim onaylanmadıysa veya ölçüler hesaba elvermiyorsa.
        """
        self._dronelar.getir(kimlik)
        sasi = self._parcali_sasi_getir(kimlik)
        if sasi.olculer is None:
            raise GecersizDegerHatasi(BIRIM_ONAYSIZ_MESAJI)
        parcalar = {p.sira: p for p in sasi.parcalar}
        if kol_sira not in parcalar or (govde_sira is not None and govde_sira not in parcalar):
            raise KayitBulunamadiHatasi("Seçilen şasi parçası bulunamadı; sayfayı yenileyip tekrar deneyin.")
        govde = parcalar[govde_sira] if govde_sira is not None else None
        return self._dingil.hesapla(parcalar[kol_sira], sasi.olculer.birim, baglanti, govde)

    def dingil_kaydet(self, kimlik: int, dingil_mm: float | None, kaynak: DingilKaynagi) -> SasiOlculeri:
        """
        Dingil mesafesini kaydeder (elle girilen veya hesaplanıp onaylanan); None verilirse siler.

        Parçalı şaside tahmini dış ölçü de yeni dingile göre yenilenir.

        Parametreler:
            kimlik: Drone kimliği.
            dingil_mm: Çapraz motor–motor mesafesi, mm; None silmek için.
            kaynak: Dingilin kaynağı (elle / hesap).
        Dönüş:
            Güncel ölçüler.
        Hatalar:
            KayitBulunamadiHatasi: Drone veya şasi yoksa.
            GecersizDegerHatasi: Birim onaylanmadıysa veya dingil aralık dışındaysa.
        """
        drone = self._dronelar.getir(kimlik)
        sasi = self._sasi_getir(kimlik)
        if sasi.olculer is None:
            raise GecersizDegerHatasi(BIRIM_ONAYSIZ_MESAJI)
        dingil = self._girdi_dogrulayici.dingil_dogrula(dingil_mm)
        olculer = self._olculeri_hesapla(
            sasi, sasi.olculer.birim, drone.motor_sayisi, dingil, kaynak if dingil is not None else None
        )
        self._sasiler.olculeri_kaydet(kimlik, olculer)
        self._dronelar.guncellendi_olarak_isaretle(kimlik)
        return olculer

    def _olculeri_hesapla(
        self,
        sasi: KayitliSasi,
        birim: str,
        motor_sayisi: int,
        dingil_mm: float | None,
        dingil_kaynagi: DingilKaynagi | None,
    ) -> SasiOlculeri:
        """Tek dosyalı veya parçalı şasinin mm ölçüleri; dingil bilgisi eklenir."""
        if sasi.parcali_mi:
            return self._ozetleyici.olculeri_hesapla(
                sasi.geometri, sasi.parcalar, birim, motor_sayisi, dingil_mm, dingil_kaynagi
            )
        olculer = self._birim_dogrulayici.olculeri_mm_ye_cevir(sasi.geometri, birim)
        return replace(olculer, dingil_mm=dingil_mm, dingil_kaynagi=dingil_kaynagi)

    def _sasi_getir(self, kimlik: int) -> KayitliSasi:
        """Şasi kaydı; yoksa KayitBulunamadiHatasi."""
        sasi = self._sasiler.getir(kimlik)
        if sasi is None:
            raise KayitBulunamadiHatasi(SASI_YOK_MESAJI)
        return sasi

    def _parcali_sasi_getir(self, kimlik: int) -> KayitliSasi:
        """Parçalı şasi kaydı; şasi yoksa veya tek dosyaysa hata."""
        sasi = self._sasi_getir(kimlik)
        if not sasi.parcali_mi:
            raise GecersizDegerHatasi(PARCALI_DEGIL_MESAJI)
        return sasi

    def sasi_agirligini_ayarla(self, kimlik: int, agirlik_g: float | None) -> Drone:
        """
        Elle girilen şasi ağırlığını kaydeder; None verilirse siler.

        Şasi dosyası yüklenmemiş olsa da ağırlık girilebilir (ağırlık
        biliniyorsa dosya gerekmez).

        Hatalar:
            KayitBulunamadiHatasi: Drone yoksa.
            GecersizDegerHatasi: Ağırlık sıfır veya negatifse.
        """
        self._dronelar.getir(kimlik)
        return self._dronelar.sasi_agirligini_ayarla(kimlik, self._girdi_dogrulayici.agirlik_dogrula(agirlik_g))

    # ---------- Hedefler ----------

    def hedefleri_kaydet(self, kimlik: int, hedefler: DroneHedefleri) -> DroneHedefleri:
        """
        Drone'un hedeflerini (uçuş süresi, yük, bütçe) kaydeder.

        Hatalar:
            KayitBulunamadiHatasi: Drone yoksa.
        """
        self._dronelar.getir(kimlik)
        self._hedefler.kaydet(kimlik, hedefler)
        self._dronelar.guncellendi_olarak_isaretle(kimlik)
        return hedefler
