"""
Drone ve şasi API uçları.

    GET    /api/secenekler                     -> form seçenekleri (tür, amaç)
    GET    /api/dronelar                       -> kayıtlı dronelar
    POST   /api/dronelar                       -> yeni drone
    GET    /api/dronelar/{kimlik}              -> drone + şasi ayrıntısı
    DELETE /api/dronelar/{kimlik}              -> drone'u sil
    POST   /api/dronelar/{kimlik}/sasi         -> şasi dosyası yükle
    POST   /api/dronelar/{kimlik}/sasi/birim   -> birimi onayla
    PUT    /api/dronelar/{kimlik}/sasi/agirlik -> şasi ağırlığını elle gir / sil
    PUT    /api/dronelar/{kimlik}/hedefler     -> uçuş süresi / yük / bütçe hedefleri

Uçlar bilerek senkron (def) yazıldı: dosya okuma işlemci yoğun olduğu için
FastAPI bunları ayrı iş parçacığında çalıştırır ve sunucu donmaz.
"""

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, UploadFile
from pydantic import BaseModel

from arayuz.elektronik_sozlukleri import hedef_sozlugu
from arayuz.parametreler import Kimlik
from arayuz.yukleme import dosya_adi, gecici_yukleme
from cekirdek.ayarlar import EN_BUYUK_YUKLEME_MB
from cekirdek.birimler import UZUNLUK_CARPANLARI_MM, BirimDonusturucu
from drone.hedefler import DroneHedefleri
from drone.modeller import (
    BASLANGIC_TURU_ADLARI,
    DRONE_TURU_ADLARI,
    KULLANIM_AMACLARI,
    MOTOR_SAYILARI,
    BaslangicTuru,
    Drone,
    DroneTuru,
)
from drone.servis import DroneServisi
from sasi.modeller import BirimOnerisi, KayitliSasi, SasiOlculeri


class DroneIstegi(BaseModel):
    """Yeni drone isteğinin gövdesi."""

    ad: str
    baslangic_turu: BaslangicTuru
    drone_turu: DroneTuru
    amac: str


class BirimIstegi(BaseModel):
    """Birim onayı isteğinin gövdesi."""

    birim: str


class AgirlikIstegi(BaseModel):
    """Şasi ağırlığı isteğinin gövdesi; None ağırlığı siler."""

    agirlik_g: float | None


class HedefIstegi(BaseModel):
    """Drone hedefleri; boş (null) alan o hedefin girilmediği anlamına gelir."""

    ucus_suresi_dk: float | None = None
    yuk_g: float | None = None
    butce_tl: float | None = None


# ---------- JSON'a çeviriciler ----------


def drone_sozlugu(drone: Drone) -> dict[str, Any]:
    """Drone nesnesini arayüzün kullanacağı sözlüğe çevirir (görünen adlar dahil)."""
    return {
        "kimlik": drone.kimlik,
        "ad": drone.ad,
        "baslangic_turu": drone.baslangic_turu.value,
        "baslangic_turu_adi": BASLANGIC_TURU_ADLARI[drone.baslangic_turu],
        "drone_turu": drone.drone_turu.value,
        "drone_turu_adi": DRONE_TURU_ADLARI[drone.drone_turu],
        "motor_sayisi": drone.motor_sayisi,
        "amac": drone.amac,
        "olusturma_zamani": drone.olusturma_zamani,
        "guncelleme_zamani": drone.guncelleme_zamani,
        "sasi_agirlik_g": drone.sasi_agirlik_g,
        "sasi_var": drone.sasi_var,
    }


def yukleme_sozlugu(sasi: KayitliSasi, oneri: BirimOnerisi) -> dict[str, Any]:
    """
    Şasi dosyasından okunan bilgileri ve birim önerisini sözlüğe çevirir.

    Parametreler:
        sasi: Şasi kaydı.
        oneri: Birim önerisi.
    """
    g = sasi.geometri
    return {
        "dosya_adi": g.dosya_adi,
        "tur": g.tur.value,
        "olculer_ham": list(g.olculer),
        "dosya_birimi": g.dosya_birimi,
        "ucgen_sayisi": g.ucgen_sayisi,
        "govde_sayisi": g.govde_sayisi,
        "kapali_mi": g.kapali_mi,
        "dis_kontur_sayisi": g.dis_kontur_sayisi,
        "delik_sayisi": g.delik_sayisi,
        "uyarilar": g.uyarilar,
        "oneri": {"birim": oneri.birim, "kaynak": oneri.kaynak.value, "aciklama": oneri.aciklama},
        # Arayüz, birim seçimi değişirken mm karşılığını anında gösterebilsin diye.
        "birim_carpanlari_mm": UZUNLUK_CARPANLARI_MM,
    }


def olculer_sozlugu(olculer: SasiOlculeri | None) -> dict[str, Any] | None:
    """
    Onaylanmış ölçüleri sözlüğe çevirir; onay yoksa None.

    Arayüz birim çevirmesin diye alan ve hacim cm cinsinden de gönderilir.
    """
    if olculer is None:
        return None
    sozluk = asdict(olculer)
    sozluk["alan_cm2"] = BirimDonusturucu.mm2_yi_cm2_ye_cevir(olculer.alan_mm2) if olculer.alan_mm2 is not None else None
    sozluk["hacim_cm3"] = BirimDonusturucu.mm3_u_cm3_e_cevir(olculer.hacim_mm3) if olculer.hacim_mm3 is not None else None
    return sozluk


# ---------- Uçlar ----------


def drone_rotalarini_olustur(servis: DroneServisi) -> APIRouter:
    """
    Drone ve şasi API uçlarını oluşturur.

    Parametreler:
        servis: İşlemleri yürüten DroneServisi.
    Dönüş:
        Sunucuya eklenecek APIRouter.
    """
    rotalar = APIRouter(prefix="/api")

    @rotalar.get("/secenekler")
    def secenekler() -> dict[str, Any]:
        """Yeni drone formundaki açılır listelerin seçenekleri."""
        return {
            "drone_turleri": [
                {"deger": t.value, "ad": DRONE_TURU_ADLARI[t], "motor_sayisi": MOTOR_SAYILARI[t]} for t in DroneTuru
            ],
            "baslangic_turleri": [{"deger": t.value, "ad": BASLANGIC_TURU_ADLARI[t]} for t in BaslangicTuru],
            "amaclar": list(KULLANIM_AMACLARI),
        }

    @rotalar.get("/dronelar")
    def dronelari_listele() -> list[dict[str, Any]]:
        """Kayıtlı droneları döndürür."""
        return [drone_sozlugu(d) for d in servis.listele()]

    @rotalar.post("/dronelar")
    def drone_olustur(istek: DroneIstegi) -> dict[str, Any]:
        """Yeni drone oluşturur."""
        return drone_sozlugu(servis.olustur(istek.ad, istek.baslangic_turu, istek.drone_turu, istek.amac))

    @rotalar.get("/dronelar/{kimlik}")
    def drone_ayrintisi(kimlik: Kimlik) -> dict[str, Any]:
        """Drone'u ve (varsa) şasi bilgilerini döndürür."""
        ayrinti = servis.ayrinti(kimlik)
        sasi = None
        if ayrinti.sasi is not None:
            sasi = {
                "yukleme": yukleme_sozlugu(ayrinti.sasi, servis.birim_oner(ayrinti.sasi.geometri)),
                "olculer": olculer_sozlugu(ayrinti.sasi.olculer),
            }
        return {"drone": drone_sozlugu(ayrinti.drone), "sasi": sasi}

    @rotalar.delete("/dronelar/{kimlik}")
    def drone_sil(kimlik: Kimlik) -> dict[str, bool]:
        """Drone'u ve şasi dosyasını siler."""
        servis.sil(kimlik)
        return {"silindi": True}

    @rotalar.post("/dronelar/{kimlik}/sasi")
    def sasi_yukle(kimlik: Kimlik, dosya: UploadFile) -> dict[str, Any]:
        """Şasi dosyasını okur ve drone'a kaydeder."""
        ad = dosya_adi(dosya)
        servis.dosya_turunu_denetle(ad)
        with gecici_yukleme(dosya, EN_BUYUK_YUKLEME_MB) as gecici_yol:
            sasi, drone = servis.sasi_yukle(kimlik, gecici_yol, ad)

        return {
            "drone": drone_sozlugu(drone),
            "yukleme": yukleme_sozlugu(sasi, servis.birim_oner(sasi.geometri)),
            "olculer": None,
        }

    @rotalar.post("/dronelar/{kimlik}/sasi/birim")
    def birim_onayla(kimlik: Kimlik, istek: BirimIstegi) -> dict[str, Any]:
        """Birimi onaylar; mm ölçülerini döndürür."""
        return {"olculer": olculer_sozlugu(servis.birim_onayla(kimlik, istek.birim))}

    @rotalar.put("/dronelar/{kimlik}/sasi/agirlik")
    def agirlik_ayarla(kimlik: Kimlik, istek: AgirlikIstegi) -> dict[str, Any]:
        """Şasi ağırlığını elle kaydeder veya siler."""
        return {"drone": drone_sozlugu(servis.sasi_agirligini_ayarla(kimlik, istek.agirlik_g))}

    @rotalar.put("/dronelar/{kimlik}/hedefler")
    def hedefleri_kaydet(kimlik: Kimlik, istek: HedefIstegi) -> dict[str, Any]:
        """Drone hedeflerini (uçuş süresi, yük, bütçe) kaydeder."""
        hedefler = DroneHedefleri(ucus_suresi_dk=istek.ucus_suresi_dk, yuk_g=istek.yuk_g, butce_tl=istek.butce_tl)
        return hedef_sozlugu(servis.hedefleri_kaydet(kimlik, hedefler))

    return rotalar
