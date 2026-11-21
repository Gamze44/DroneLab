"""
Şartname API uçları.

    GET    /api/sartname-secenekleri               -> büyüklükler, sınır türleri, madde sınıfları
    GET    /api/sartnameler                        -> önceden yüklenmiş şartnameler (kütüphane)
    POST   /api/sartnameler                        -> belge yükle (form: dosya, ad, drone_kimlik?)
    GET    /api/sartnameler/{kimlik}               -> şartname + maddeler
    DELETE /api/sartnameler/{kimlik}               -> kullanılmayan şartnameyi sil
    PUT    /api/sartnameler/{kimlik}/maddeler      -> madde tablosunu kaydet
    POST   /api/sartnameler/{kimlik}/cikar         -> Gemini ile maddeleri çıkar (mevcutların yerine)
    GET    /api/dronelar/{kimlik}/sartname         -> drone'un şartnamesi + uyum raporu
    PUT    /api/dronelar/{kimlik}/sartname         -> kütüphaneden şartname bağla
    DELETE /api/dronelar/{kimlik}/sartname         -> drone'dan şartnameyi kaldır
"""

from pathlib import Path
import tempfile
from typing import Any

from fastapi import APIRouter, Form, UploadFile
from pydantic import BaseModel, Field

from arayuz.drone_rotalari import GECICI_DOSYA_ADI, gecici_dosyaya_yaz
from arayuz.parametreler import GovdeKimligi, Kimlik
from cekirdek.ayarlar import EN_BUYUK_SARTNAME_MB
from sartname.kontrol import MaddeSonucu, durum_adi
from sartname.modeller import BUYUKLUK_TANIMLARI, MADDE_SINIFI_ADLARI, SINIR_TURU_ADLARI, Madde, Sartname
from sartname.servis import SartnameServisi


class MaddeTablosu(BaseModel):
    """Düzenlenmiş madde tablosu (ham satırlar; doğrulama serviste)."""

    maddeler: list[dict[str, Any]] = Field(default_factory=list)


class BaglamaIstegi(BaseModel):
    """Kütüphaneden seçilen şartname."""

    sartname_kimlik: GovdeKimligi


def sartname_sozlugu(s: Sartname) -> dict[str, Any]:
    """Şartnameyi sözlüğe çevirir (belge metni gönderilmez, yalnızca uzunluğu)."""
    return {
        "kimlik": s.kimlik, "ad": s.ad, "dosya_adi": s.dosya_adi, "yuklenme_zamani": s.yuklenme_zamani,
        "metin_uzunlugu": s.metin_uzunlugu, "madde_sayisi": s.madde_sayisi,
        "onayli_madde_sayisi": s.onayli_madde_sayisi, "kullanan_drone_sayisi": s.kullanan_drone_sayisi,
    }


def madde_sozlugu(m: Madde) -> dict[str, Any]:
    """Maddeyi sözlüğe çevirir."""
    tanim = BUYUKLUK_TANIMLARI[m.buyukluk]
    return {
        "kimlik": m.kimlik, "madde_no": m.madde_no, "sayfa": m.sayfa, "aciklama": m.aciklama,
        "buyukluk": m.buyukluk.value, "buyukluk_adi": tanim.ad, "birim": tanim.birim,
        "sinir_turu": m.sinir_turu.value, "sinir_turu_adi": SINIR_TURU_ADLARI[m.sinir_turu],
        "deger": m.deger, "sinif": m.sinif.value, "onaylandi": m.onaylandi,
    }


def madde_sonucu_sozlugu(s: MaddeSonucu) -> dict[str, Any]:
    """Rapor satırını sözlüğe çevirir."""
    return {
        "madde": madde_sozlugu(s.madde), "durum": s.durum.value, "durum_adi": durum_adi(s.durum),
        "tasarim": s.tasarim, "aciklama": s.aciklama, "tahmini": s.tahmini,
    }


def sartname_rotalarini_olustur(servis: SartnameServisi) -> APIRouter:
    """
    Şartname uçlarını oluşturur.

    Parametreler:
        servis: SartnameServisi.
    """
    rotalar = APIRouter(prefix="/api")

    @rotalar.get("/sartname-secenekleri")
    def secenekler() -> dict[str, Any]:
        """Madde tablosunun seçenekleri."""
        return {
            "buyuklukler": [
                {"deger": b.value, "ad": t.ad, "birim": t.birim, "parca_mi": t.parca_mi}
                for b, t in BUYUKLUK_TANIMLARI.items()
            ],
            "sinir_turleri": [{"deger": s.value, "ad": ad} for s, ad in SINIR_TURU_ADLARI.items()],
            "siniflar": [{"deger": s.value, "ad": ad} for s, ad in MADDE_SINIFI_ADLARI.items()],
        }

    @rotalar.get("/sartnameler")
    def listele() -> list[dict[str, Any]]:
        """Önceden yüklenmiş şartnameler."""
        return [sartname_sozlugu(s) for s in servis.listele()]

    @rotalar.post("/sartnameler")
    def yukle(dosya: UploadFile, ad: str = Form(...), drone_kimlik: GovdeKimligi | None = Form(None)) -> dict[str, Any]:
        """Şartname belgesini yükler; drone verilirse ona bağlar."""
        dosya_adi = Path(dosya.filename or "").name
        servis.dosya_turunu_denetle(dosya_adi)
        with tempfile.TemporaryDirectory() as klasor:
            gecici = Path(klasor) / (GECICI_DOSYA_ADI + Path(dosya_adi).suffix.lower())
            gecici_dosyaya_yaz(dosya, gecici, EN_BUYUK_SARTNAME_MB)
            sartname = servis.yukle(gecici, dosya_adi, ad, drone_kimlik)
        return sartname_sozlugu(sartname)

    @rotalar.get("/sartnameler/{kimlik}")
    def getir(kimlik: Kimlik) -> dict[str, Any]:
        """Şartname ve maddeleri."""
        sartname, maddeler = servis.getir(kimlik)
        return {**sartname_sozlugu(sartname), "maddeler": [madde_sozlugu(m) for m in maddeler]}

    @rotalar.delete("/sartnameler/{kimlik}")
    def sil(kimlik: Kimlik) -> dict[str, bool]:
        """Kullanılmayan şartnameyi siler."""
        servis.sil(kimlik)
        return {"silindi": True}

    @rotalar.put("/sartnameler/{kimlik}/maddeler")
    def maddeleri_kaydet(kimlik: Kimlik, tablo: MaddeTablosu) -> list[dict[str, Any]]:
        """Madde tablosunu kaydeder (bu şartnameyi kullanan tüm dronelar etkilenir)."""
        return [madde_sozlugu(m) for m in servis.maddeleri_kaydet(kimlik, tablo.maddeler)]

    @rotalar.post("/sartnameler/{kimlik}/cikar")
    def maddeleri_cikar(kimlik: Kimlik) -> dict[str, Any]:
        """Gemini ile maddeleri çıkarır (günlük sınıra sayılır)."""
        r = servis.maddeleri_cikar(kimlik)
        return {
            "maddeler": [madde_sozlugu(m) for m in r.maddeler], "atlanan": r.atlanan,
            "bugun_kullanilan": r.bugun_kullanilan, "gunluk_sinir": r.gunluk_sinir,
        }

    @rotalar.get("/dronelar/{kimlik}/sartname")
    def drone_sartnamesi(kimlik: Kimlik) -> dict[str, Any]:
        """Drone'un şartnamesi ve madde madde uyum raporu."""
        r = servis.rapor(kimlik)
        return {
            "sartname": sartname_sozlugu(r.sartname) if r.sartname else None,
            "rapor": [madde_sonucu_sozlugu(s) for s in r.sonuclar],
        }

    @rotalar.put("/dronelar/{kimlik}/sartname")
    def bagla(kimlik: Kimlik, istek: BaglamaIstegi) -> dict[str, Any]:
        """Kütüphanedeki şartnameyi drone'a bağlar."""
        return sartname_sozlugu(servis.bagla(kimlik, istek.sartname_kimlik))

    @rotalar.delete("/dronelar/{kimlik}/sartname")
    def bagi_kaldir(kimlik: Kimlik) -> dict[str, bool]:
        """Drone'un şartnamesini kaldırır (kütüphanede kalır)."""
        servis.bagi_kaldir(kimlik)
        return {"kaldirildi": True}

    return rotalar
