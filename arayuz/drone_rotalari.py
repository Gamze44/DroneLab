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

Uçlar bilerek senkron (def) yazıldı: dosya okuma işlemci yoğun olduğu için
FastAPI bunları ayrı iş parçacığında çalıştırır ve sunucu donmaz.
"""

from dataclasses import asdict
from pathlib import Path
import tempfile
from typing import Any, Final

from fastapi import APIRouter, UploadFile
from pydantic import BaseModel

from cekirdek.ayarlar import EN_BUYUK_YUKLEME_MB
from cekirdek.birimler import UZUNLUK_CARPANLARI_MM
from cekirdek.hatalar import DosyaOkumaHatasi
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

BAYT_BIR_MB: Final[int] = 1024 * 1024
OKUMA_PARCA_BOYUTU: Final[int] = BAYT_BIR_MB
# Kullanıcının dosya adı geçici klasöre yazılmaz (ör. "..\..\x.stl" gibi adlara karşı);
# okuyucular yalnızca uzantıya baktığı için sabit bir ad yeterlidir.
GECICI_DOSYA_ADI: Final[str] = "yuklenen"


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
    """Onaylanmış ölçüleri sözlüğe çevirir; onay yoksa None."""
    return asdict(olculer) if olculer is not None else None


# ---------- Yardımcılar ----------


def gecici_dosyaya_yaz(dosya: UploadFile, hedef: Path, sinir_mb: int = EN_BUYUK_YUKLEME_MB) -> None:
    """
    Yüklenen dosyayı boyut sınırını denetleyerek parça parça diske yazar.

    Parametreler:
        dosya: Yüklenen dosya.
        hedef: Yazılacak yol.
        sinir_mb: En büyük boyut, MB.
    Hatalar:
        DosyaOkumaHatasi: Dosya boşsa veya boyut sınırını aşıyorsa.
    """
    sinir = sinir_mb * BAYT_BIR_MB
    toplam = 0
    with hedef.open("wb") as cikti:
        while parca := dosya.file.read(OKUMA_PARCA_BOYUTU):
            toplam += len(parca)
            if toplam > sinir:
                raise DosyaOkumaHatasi(
                    f"Dosya {sinir_mb} MB sınırını aşıyor. Daha küçük bir dosya deneyin veya sınırı ayarlardan artırın."
                )
            cikti.write(parca)
    if toplam == 0:
        raise DosyaOkumaHatasi("Yüklenen dosya boş.")


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
    def drone_ayrintisi(kimlik: int) -> dict[str, Any]:
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
    def drone_sil(kimlik: int) -> dict[str, bool]:
        """Drone'u ve şasi dosyasını siler."""
        servis.sil(kimlik)
        return {"silindi": True}

    @rotalar.post("/dronelar/{kimlik}/sasi")
    def sasi_yukle(kimlik: int, dosya: UploadFile) -> dict[str, Any]:
        """Şasi dosyasını okur ve drone'a kaydeder."""
        dosya_adi = Path(dosya.filename or "").name
        servis.dosya_turunu_denetle(dosya_adi)

        # Windows'ta açık dosya başka işlemce okunamadığı için NamedTemporaryFile
        # yerine geçici klasör kullanılır; klasör iş bitince kendiliğinden silinir.
        with tempfile.TemporaryDirectory() as klasor:
            gecici_yol = Path(klasor) / (GECICI_DOSYA_ADI + Path(dosya_adi).suffix.lower())
            gecici_dosyaya_yaz(dosya, gecici_yol)
            sasi, drone = servis.sasi_yukle(kimlik, gecici_yol, dosya_adi)

        return {
            "drone": drone_sozlugu(drone),
            "yukleme": yukleme_sozlugu(sasi, servis.birim_oner(sasi.geometri)),
            "olculer": None,
        }

    @rotalar.post("/dronelar/{kimlik}/sasi/birim")
    def birim_onayla(kimlik: int, istek: BirimIstegi) -> dict[str, Any]:
        """Birimi onaylar; mm ölçülerini döndürür."""
        return {"olculer": olculer_sozlugu(servis.birim_onayla(kimlik, istek.birim))}

    @rotalar.put("/dronelar/{kimlik}/sasi/agirlik")
    def agirlik_ayarla(kimlik: int, istek: AgirlikIstegi) -> dict[str, Any]:
        """Şasi ağırlığını elle kaydeder veya siler."""
        return {"drone": drone_sozlugu(servis.sasi_agirligini_ayarla(kimlik, istek.agirlik_g))}

    return rotalar
