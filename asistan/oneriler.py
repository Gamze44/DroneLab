"""
Asistanın değişiklik önerileri: saklama ve kullanıcı onayıyla uygulama.

Asistanın doğrudan yazma yetkisi yoktur. degisiklik_oner aracı yalnızca "bekliyor" durumunda
bir öneri kaydeder; öneri, kullanıcı karttaki "Uygula"ya bastığında yeniden doğrulanır ve
programın mevcut güncelleme yollarıyla (ElektronikServisi, DroneServisi) uygulanır.
"""

from dataclasses import dataclass, field, replace
from enum import Enum
import json
import sqlite3
from typing import Any

from asistan.senaryo import Degisiklik, DegisiklikTuru, HEDEF_ALANLARI, SenaryoHesaplayici, degisiklikleri_coz
from cekirdek.hatalar import DroneProgramHatasi, GecersizDegerHatasi, KayitBulunamadiHatasi
from cekirdek.zaman import simdi_iso
from depolama.veritabani import Veritabani
from drone.servis import DroneServisi
from elektronik.parcalar.turler import ParcaDurumu
from elektronik.servis import ElektronikServisi

# Asistanın eklediği parçalar drone'da "önerilen" durumuyla görünür.
EKLENEN_PARCA_DURUMU = ParcaDurumu.ONERILEN


class OneriDurumu(str, Enum):
    """Önerinin durumu. Değerler veritabanında saklanır; değiştirilmemeli."""

    BEKLIYOR = "bekliyor"
    UYGULANDI = "uygulandi"
    VAZGECILDI = "vazgecildi"


@dataclass
class Oneri:
    """
    Alanlar:
        kimlik: Öneri numarası.
        drone_kimlik: Önerinin drone'u.
        mesaj_kimlik: Önerinin yapıldığı asistan mesajı (tur bitmeden None).
        gerekce: Asistanın gerekçesi.
        degisiklikler: Değişiklikler (sözlük biçiminde).
        sonuc: Öneri anındaki senaryo sonucu (önce/sonra), kartta gösterilir.
        durum: Bekliyor / uygulandı / vazgeçildi.
        zaman: ISO zaman.
    """

    kimlik: int
    drone_kimlik: int
    mesaj_kimlik: int | None
    gerekce: str
    degisiklikler: list[dict[str, Any]]
    sonuc: dict[str, Any] = field(default_factory=dict)
    durum: OneriDurumu = OneriDurumu.BEKLIYOR
    zaman: str = ""

    def sozluk(self) -> dict[str, Any]:
        """Öneri kartının arayüze gönderilen biçimi."""
        return {
            "kimlik": self.kimlik, "durum": self.durum.value, "gerekce": self.gerekce,
            "aciklamalar": self.sonuc.get("aciklamalar", []), "once": self.sonuc.get("once", {}),
            "sonra": self.sonuc.get("sonra", {}), "uyum_degisimleri": self.sonuc.get("uyum_degisimleri", []),
        }


def _oneri(satir: sqlite3.Row) -> Oneri:
    return Oneri(
        kimlik=int(satir["kimlik"]), drone_kimlik=int(satir["drone_kimlik"]), mesaj_kimlik=satir["mesaj_kimlik"],
        gerekce=satir["gerekce"], degisiklikler=json.loads(satir["degisiklikler_json"]),
        sonuc=json.loads(satir["sonuc_json"]), durum=OneriDurumu(satir["durum"]), zaman=satir["zaman"],
    )


class OneriDeposu:
    """
    Önerileri veritabanında saklar.

    Parametreler:
        veritabani: Ortak Veritabani.
    """

    def __init__(self, veritabani: Veritabani) -> None:
        self._vt = veritabani

    def ekle(self, drone_kimlik: int, gerekce: str, degisiklikler: list[Degisiklik], sonuc: dict[str, Any]) -> Oneri:
        """Yeni öneriyi "bekliyor" durumunda kaydeder."""
        with self._vt.baglanti() as bag:
            imlec = bag.execute(
                "INSERT INTO asistan_onerileri (drone_kimlik, gerekce, degisiklikler_json, sonuc_json, durum, zaman) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    drone_kimlik, gerekce, json.dumps([d.sozluk() for d in degisiklikler], ensure_ascii=False),
                    json.dumps(sonuc, ensure_ascii=False), OneriDurumu.BEKLIYOR.value, simdi_iso(),
                ),
            )
            kimlik = int(imlec.lastrowid)
        return self.getir(kimlik)

    def getir(self, kimlik: int) -> Oneri:
        """Hatalar: KayitBulunamadiHatasi."""
        with self._vt.baglanti() as bag:
            satir = bag.execute("SELECT * FROM asistan_onerileri WHERE kimlik = ?", (kimlik,)).fetchone()
        if satir is None:
            raise KayitBulunamadiHatasi("Öneri bulunamadı. Sohbet temizlenmiş olabilir.")
        return _oneri(satir)

    def mesaja_bagla(self, oneri_kimlikleri: list[int], mesaj_kimlik: int) -> None:
        """Turda yapılan önerileri asistanın yanıt mesajına bağlar."""
        with self._vt.baglanti() as bag:
            bag.executemany(
                "UPDATE asistan_onerileri SET mesaj_kimlik = ? WHERE kimlik = ?",
                [(mesaj_kimlik, k) for k in oneri_kimlikleri],
            )

    def mesajlarin_onerileri(self, mesaj_kimlikleri: list[int]) -> dict[int, list[Oneri]]:
        """Mesaj kimliği -> o mesajdaki öneriler."""
        if not mesaj_kimlikleri:
            return {}
        with self._vt.baglanti() as bag:
            satirlar = bag.execute(
                "SELECT * FROM asistan_onerileri WHERE mesaj_kimlik IN (SELECT value FROM json_each(?)) ORDER BY kimlik",
                (json.dumps(mesaj_kimlikleri),),
            ).fetchall()
        sonuc: dict[int, list[Oneri]] = {}
        for satir in satirlar:
            oneri = _oneri(satir)
            sonuc.setdefault(oneri.mesaj_kimlik, []).append(oneri)
        return sonuc

    def durumu_degistir(self, kimlik: int, durum: OneriDurumu) -> Oneri:
        """Önerinin durumunu yazar."""
        with self._vt.baglanti() as bag:
            bag.execute("UPDATE asistan_onerileri SET durum = ? WHERE kimlik = ?", (durum.value, kimlik))
        return self.getir(kimlik)

    def sil(self, kimlikler: list[int]) -> None:
        """Önerileri siler (yarıda kalıp baştan alınan turun önerileri için)."""
        with self._vt.baglanti() as bag:
            bag.executemany("DELETE FROM asistan_onerileri WHERE kimlik = ?", [(k,) for k in kimlikler])

    def baglanmamislari_sil(self, drone_kimlik: int) -> None:
        """Hiçbir mesaja bağlanmamış (yanıtı yarıda kalmış) önerileri siler ("Yeni sohbet")."""
        with self._vt.baglanti() as bag:
            bag.execute("DELETE FROM asistan_onerileri WHERE drone_kimlik = ? AND mesaj_kimlik IS NULL", (drone_kimlik,))


class OneriUygulayici:
    """
    Kullanıcının onayladığı öneriyi uygular veya reddeder.

    Parametreler:
        depo: OneriDeposu.
        senaryo: Uygulamadan önce son denetim için SenaryoHesaplayici.
        elektronik: Parça ekleme/değiştirme için ElektronikServisi.
        drone_servisi: Hedefleri kaydetmek için DroneServisi.
    """

    def __init__(
        self, depo: OneriDeposu, senaryo: SenaryoHesaplayici, elektronik: ElektronikServisi, drone_servisi: DroneServisi
    ) -> None:
        self._depo = depo
        self._senaryo = senaryo
        self._elektronik = elektronik
        self._dronelar = drone_servisi

    def uygula(self, kimlik: int) -> Oneri:
        """
        Öneriyi uygular.

        Önce bugünkü veriyle senaryo yeniden hesaplanır; öneri yapıldıktan sonra drone
        değiştiyse (ör. parça elle silindiyse) hiçbir şey değiştirilmeden hata verilir.

        Hatalar:
            KayitBulunamadiHatasi: Öneri yoksa.
            GecersizDegerHatasi: Öneri bekliyor durumunda değilse veya artık uygulanamıyorsa.
        """
        oneri = self._bekleyen(kimlik)
        degisiklikler = degisiklikleri_coz(oneri.degisiklikler)
        try:
            self._senaryo.hesapla(oneri.drone_kimlik, degisiklikler)
        except DroneProgramHatasi as hata:
            raise GecersizDegerHatasi(
                f"Öneri artık uygulanamıyor; drone öneriden sonra değişmiş. ({hata.mesaj}) Asistana yeniden sorun."
            ) from None
        for degisiklik in degisiklikler:
            self._degisikligi_uygula(oneri.drone_kimlik, degisiklik)
        return self._depo.durumu_degistir(kimlik, OneriDurumu.UYGULANDI)

    def vazgec(self, kimlik: int) -> Oneri:
        """
        Öneriyi reddeder; drone değişmez.

        Hatalar:
            KayitBulunamadiHatasi, GecersizDegerHatasi (bekliyor durumunda değilse).
        """
        self._bekleyen(kimlik)
        return self._depo.durumu_degistir(kimlik, OneriDurumu.VAZGECILDI)

    def _bekleyen(self, kimlik: int) -> Oneri:
        oneri = self._depo.getir(kimlik)
        if oneri.durum is not OneriDurumu.BEKLIYOR:
            durum = "uygulandı" if oneri.durum is OneriDurumu.UYGULANDI else "reddedildi"
            raise GecersizDegerHatasi(f"Bu öneri zaten {durum}.")
        return oneri

    def _degisikligi_uygula(self, drone_kimlik: int, d: Degisiklik) -> None:
        """Tek değişikliği mevcut servis yollarıyla uygular."""
        if d.islem is DegisiklikTuru.PARCA_EKLE:
            self._elektronik.katalogdan_ekle(drone_kimlik, d.parca_kimlik, d.adet or 1, EKLENEN_PARCA_DURUMU)
        elif d.islem is DegisiklikTuru.PARCA_DEGISTIR:
            eski_adet = next(bag.adet for bag, _ in self._elektronik.kalemler(drone_kimlik) if bag.kimlik == d.bag_kimlik)
            self._elektronik.bag_sil(drone_kimlik, d.bag_kimlik)
            self._elektronik.katalogdan_ekle(drone_kimlik, d.parca_kimlik, d.adet or eski_adet, EKLENEN_PARCA_DURUMU)
        elif d.islem is DegisiklikTuru.ADET_DEGISTIR:
            self._elektronik.bag_guncelle(drone_kimlik, d.bag_kimlik, d.adet, None)
        elif d.islem is DegisiklikTuru.PARCA_CIKAR:
            self._elektronik.bag_sil(drone_kimlik, d.bag_kimlik)
        else:
            degerler = {alan: getattr(d, alan) for alan in HEDEF_ALANLARI if getattr(d, alan) is not None}
            self._dronelar.hedefleri_kaydet(drone_kimlik, replace(self._elektronik.hedefler(drone_kimlik), **degerler))
