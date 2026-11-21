"""
Drone işlemlerini yöneten servis.

Arayüz (API uçları) doğrudan veritabanına veya okuyuculara gitmez; bu sınıfı
çağırır. Böylece "şasi yükle" gibi birden çok adımlı işlemler (dosyayı oku,
kopyala, kaydet) tek yerde durur ve HTTP olmadan da test edilebilir.
"""

from dataclasses import dataclass
from pathlib import Path

from cekirdek.ayarlar import SASI_DOSYALARI_KLASOR_ADI, VERITABANI_DOSYA_ADI
from cekirdek.hatalar import KayitBulunamadiHatasi
from depolama.dosya_deposu import SasiDosyaDeposu
from depolama.drone_deposu import DroneDeposu
from depolama.sasi_kayit_deposu import SasiKayitDeposu
from depolama.veritabani import Veritabani
from drone.dogrulama import DroneGirdisiDogrulayici
from drone.modeller import BaslangicTuru, Drone, DroneTuru
from sasi.birim_dogrulayici import BirimDogrulayici
from sasi.modeller import BirimOnerisi, KayitliSasi, SasiGeometrisi, SasiOlculeri
from sasi.okuyucu_secici import OkuyucuSecici


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
        self._dosyalar = SasiDosyaDeposu(veri_klasoru / SASI_DOSYALARI_KLASOR_ADI)
        self._okuyucu_secici = OkuyucuSecici()
        self._birim_dogrulayici = BirimDogrulayici()
        self._girdi_dogrulayici = DroneGirdisiDogrulayici()

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
        self._okuyucu_secici.sec(dosya_adi)

    def sasi_yukle(self, kimlik: int, gecici_yol: Path, dosya_adi: str) -> tuple[KayitliSasi, Drone]:
        """
        Şasi dosyasını okur, kopyasını saklar ve drone'a bağlar.

        Drone'un daha önce bir şasisi varsa yeni dosya onun yerine geçer ve
        elle girilen ağırlık silinir, çünkü o ağırlık eski şasiye aitti.

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
        geometri = self._okuyucu_secici.sec(dosya_adi).oku(gecici_yol)
        geometri.dosya_adi = dosya_adi

        saklanan = self._dosyalar.kaydet(kimlik, gecici_yol)
        self._sasiler.kaydet(kimlik, saklanan, geometri)

        if drone.sasi_var:
            drone = self._dronelar.sasi_agirligini_ayarla(kimlik, None)
        else:
            self._dronelar.guncellendi_olarak_isaretle(kimlik)
            drone = self._dronelar.getir(kimlik)
        return KayitliSasi(saklanan_dosya=saklanan, geometri=geometri), drone

    def birim_oner(self, geometri: SasiGeometrisi) -> BirimOnerisi:
        """Şasi geometrisi için birim önerisi döndürür."""
        return self._birim_dogrulayici.birim_oner(geometri)

    def birim_onayla(self, kimlik: int, birim: str) -> SasiOlculeri:
        """
        Onaylanan birimle mm ölçülerini hesaplar ve kaydeder.

        Hatalar:
            KayitBulunamadiHatasi: Drone yoksa veya şasi yüklenmemişse.
            BirimHatasi: Birim tanınmıyorsa.
        """
        self._dronelar.getir(kimlik)
        sasi = self._sasiler.getir(kimlik)
        if sasi is None:
            raise KayitBulunamadiHatasi("Bu drone için henüz şasi dosyası yüklenmedi.")
        olculer = self._birim_dogrulayici.olculeri_mm_ye_cevir(sasi.geometri, birim.strip().lower())
        self._sasiler.olculeri_kaydet(kimlik, olculer)
        self._dronelar.guncellendi_olarak_isaretle(kimlik)
        return olculer

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
