"""
Asistanın her soruda gördüğü kısa bağlam: hangi ekrandayız ve açık drone'un özeti.

Bağlam bilerek kısa tutulur (her istekte gönderilir, kotayı ve süreyi etkiler).
Ayrıntı gerektiğinde model araçları çağırır.
"""

from typing import Final

from asistan.ayarlar import BAGLAM_DRONE_SINIRI, BILINMEYEN_EKRAN, EKRAN_ADLARI
from cekirdek.bicim import sayi_yaz
from drone.modeller import BASLANGIC_TURU_ADLARI, DRONE_TURU_ADLARI
from drone.servis import DroneServisi
from elektronik.hesap.ucus import HesapDegeri
from elektronik.hesap.uyum import UyumDurumu
from elektronik.servis import ElektronikServisi
from elektronik.zorunlu_parcalar import ZorunlulukDurumu
from sartname.servis import SartnameServisi

TAHMINI_EKI: Final[str] = " (tahmini)"
YOK: Final[str] = "–"


def ekran_adi(ekran: str) -> str:
    """Arayüzün gönderdiği ekran anahtarının görünen adı."""
    return EKRAN_ADLARI.get(ekran, BILINMEYEN_EKRAN)


def _deger(h: HesapDegeri, birim: str = "") -> str:
    """Hesap değerini "7,5 dk (tahmini)" ya da "hesaplanamadı – neden" biçiminde yazar."""
    if h.deger is None:
        return f"hesaplanamadı – {h.aciklama}"
    return f"{sayi_yaz(h.deger)}{birim}{TAHMINI_EKI if h.tahmini else ''}"


class BaglamToplayici:
    """
    Ekran ve drone özetini modele verilecek kısa metne çevirir.

    Parametreler:
        elektronik: Drone özeti için ElektronikServisi.
        sartname: Bağlı şartname için SartnameServisi.
        dronelar: Ana sayfadaki drone listesi için DroneServisi.
    """

    def __init__(self, elektronik: ElektronikServisi, sartname: SartnameServisi, dronelar: DroneServisi) -> None:
        self._elektronik = elektronik
        self._sartname = sartname
        self._dronelar = dronelar

    def topla(self, ekran: str, drone_kimlik: int | None) -> str:
        """
        Parametreler:
            ekran: Arayüzdeki ekran anahtarı (ör. "elektronik").
            drone_kimlik: Açık drone; ana sayfa ve ayarlarda None.
        Dönüş:
            Bağlam metni.
        Hatalar:
            KayitBulunamadiHatasi: Drone verilmiş ama yoksa.
        """
        satirlar = [f"Ekran: {ekran_adi(ekran)}"]
        if drone_kimlik is None:
            satirlar += self._genel()
        else:
            satirlar += self._drone(drone_kimlik)
        return "\n".join(satirlar)

    def _genel(self) -> list[str]:
        """Açık drone yokken: kayıtlı dronelar."""
        dronelar = self._dronelar.listele()
        satirlar = ["Açık drone yok; drone'a özel araçlar bu ekranda kullanılamaz. Bir drone hakkında "
                    "ayrıntılı soru için kullanıcı o drone'un sayfasını açmalıdır."]
        if not dronelar:
            return satirlar + ["Kayıtlı drone yok."]
        liste = "; ".join(
            f"\"{d.ad}\" ({DRONE_TURU_ADLARI[d.drone_turu]}, {d.amac})" for d in dronelar[:BAGLAM_DRONE_SINIRI]
        )
        return satirlar + [f"Kayıtlı dronelar ({len(dronelar)}): {liste}"]

    def _drone(self, drone_kimlik: int) -> list[str]:
        """Açık drone'un kısa özeti."""
        ozet = self._elektronik.ozet(drone_kimlik)
        d = ozet.drone
        eksikler = [z.etiket for z in ozet.zorunluluklar if z.durum is ZorunlulukDurumu.EKSIK]
        sayilar = {durum: sum(1 for u in ozet.uyum if u.durum is durum) for durum in UyumDurumu}
        h = ozet.hedefler
        sartname = self._sartname.drone_sartnamesi(drone_kimlik)
        a = ozet.agirlik
        return [
            f"Açık drone: \"{d.ad}\"; {DRONE_TURU_ADLARI[d.drone_turu]}; amaç: {d.amac}; "
            f"{BASLANGIC_TURU_ADLARI[d.baslangic_turu]}.",
            f"Parça satırı: {len(ozet.kalemler)}. Eksik zorunlu parça: {', '.join(eksikler) or 'yok'}.",
            f"Toplam ağırlık: {sayi_yaz(a.toplam_g)} g{TAHMINI_EKI if a.tahmini else ''}. "
            f"İtki/ağırlık: {_deger(ozet.ucus.itki_agirlik_orani)}. Uçuş süresi: {_deger(ozet.ucus.ucus_suresi_dk, ' dk')}.",
            "Uyum: " + ", ".join(f"{sayilar[durum]} {durum.value}" for durum in UyumDurumu) + ".",
            f"Hedefler: uçuş süresi {sayi_yaz(h.ucus_suresi_dk) if h.ucus_suresi_dk else YOK} dk; "
            f"yük {sayi_yaz(h.yuk_g) if h.yuk_g else YOK} g; bütçe {sayi_yaz(h.butce_tl) if h.butce_tl else YOK} TL; "
            f"itki/ağırlık hedefi {sayi_yaz(ozet.ucus.hedef_itki_agirlik)} "
            f"({'kullanıcı girdi' if ozet.ucus.hedef_itki_agirlik_elle_mi else 'kullanım amacına göre varsayılan'}).",
            f"Şartname: \"{sartname.ad}\" bağlı." if sartname else "Şartname: bağlı değil.",
            "Ayrıntı (parça listesi, uyum açıklamaları, uçuş hesabı, şartname maddeleri) için araçları kullan.",
        ]
