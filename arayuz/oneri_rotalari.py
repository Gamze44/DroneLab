"""
Yapay zeka önerisi ve ayarlarının API uçları.

    POST   /api/dronelar/{kimlik}/oneriler        -> Gemini'den aday iste ve değerlendir
    POST   /api/dronelar/{kimlik}/oneriler/sec    -> seçilen adayı drone'a "önerilen" olarak ekle
    GET    /api/ayarlar/yapay-zeka                -> anahtar var/yok, model, günlük sınır, kullanım
    PUT    /api/ayarlar/yapay-zeka                -> model / sınır / anahtar değiştir
    DELETE /api/ayarlar/yapay-zeka/anahtar        -> anahtar dosyasını sil

Anahtar hiçbir yanıtta döndürülmez.
"""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from arastirma.ayarlar import EN_BUYUK_GUNLUK_SINIR
from arastirma.gemini import MODELLER
from arayuz.elektronik_rotalari import ParcaBilgisi, bag_sozlugu, hesap_degeri_sozlugu, parca_sozlugu, uyum_sozlugu
from elektronik.oneri.servis import OneriAdayi, OneriServisi
from elektronik.parcalar.turler import DigerAltTur, ParcaTuru


class OneriIstegi(BaseModel):
    """Hangi parça türü için öneri isteniyor."""

    tur: ParcaTuru
    alt_tur: DigerAltTur | None = None


class OneriSecimi(BaseModel):
    """Seçilen aday: katalogdaysa kimliği, değilse parça bilgisi."""

    parca: ParcaBilgisi | None = None
    parca_kimlik: int | None = None
    adet: int = 1


class AyarGuncelleme(BaseModel):
    """Verilmeyen alan değişmez. Anahtar yalnızca yazılır, asla geri okunmaz."""

    model: str | None = None
    gunluk_sinir: int | None = None
    anahtar: str | None = None


def aday_sozlugu(a: OneriAdayi) -> dict[str, Any]:
    """Adayı arayüze gönderilecek sözlüğe çevirir."""
    d = a.degerlendirme
    return {
        "parca": parca_sozlugu(a.parca),
        "gerekce": a.gerekce,
        "katalog_kimlik": a.katalog_kimlik,
        "silinen_alanlar": a.silinen_alanlar,
        "adet": d.adet,
        "uyum": [uyum_sozlugu(u) for u in d.ilgili_sonuclar],
        "sayilar": d.sayilar,
        "itki_agirlik": hesap_degeri_sozlugu(d.itki_agirlik) if d.itki_agirlik else None,
        "ucus_suresi_dk": hesap_degeri_sozlugu(d.ucus_suresi_dk) if d.ucus_suresi_dk else None,
        "sartname_ihlalleri": [
            {"madde_no": s.madde.madde_no, "aciklama": s.aciklama, "tasarim": s.tasarim} for s in d.sartname_ihlalleri
        ],
    }


def oneri_rotalarini_olustur(servis: OneriServisi) -> APIRouter:
    """
    Öneri ve yapay zeka ayarı uçlarını oluşturur.

    Parametreler:
        servis: OneriServisi.
    """
    rotalar = APIRouter(prefix="/api")

    @rotalar.post("/dronelar/{kimlik}/oneriler")
    def oner(kimlik: int, istek: OneriIstegi) -> dict[str, Any]:
        """Gemini'den aday ister (günlük sınıra sayılır)."""
        sonuc = servis.oner(kimlik, istek.tur, istek.alt_tur)
        return {
            "adaylar": [aday_sozlugu(a) for a in sonuc.adaylar],
            "atlanan": sonuc.atlanan,
            "bugun_kullanilan": sonuc.bugun_kullanilan,
            "gunluk_sinir": sonuc.gunluk_sinir,
            "model": sonuc.model,
        }

    @rotalar.post("/dronelar/{kimlik}/oneriler/sec")
    def sec(kimlik: int, secim: OneriSecimi) -> dict[str, Any]:
        """Seçilen adayı drone'a ekler."""
        bilgi = secim.parca
        bag = servis.sec(
            kimlik,
            secim.adet,
            parca_kimlik=secim.parca_kimlik,
            tur=bilgi.tur if bilgi else None,
            alt_tur=bilgi.alt_tur if bilgi else None,
            ortak=bilgi.ortak() if bilgi else None,
            teknik=bilgi.teknik if bilgi else None,
        )
        return bag_sozlugu(bag)

    @rotalar.get("/ayarlar/yapay-zeka")
    def ayarlar() -> dict[str, Any]:
        """Yapay zeka ayarları (anahtarın kendisi yok)."""
        return {**servis.ayar_durumu(), "modeller": list(MODELLER), "en_buyuk_gunluk_sinir": EN_BUYUK_GUNLUK_SINIR}

    @rotalar.put("/ayarlar/yapay-zeka")
    def ayarlari_guncelle(istek: AyarGuncelleme) -> dict[str, Any]:
        """Ayarları değiştirir."""
        durum = servis.ayarlari_guncelle(istek.model, istek.gunluk_sinir, istek.anahtar)
        return {**durum, "modeller": list(MODELLER), "en_buyuk_gunluk_sinir": EN_BUYUK_GUNLUK_SINIR}

    @rotalar.delete("/ayarlar/yapay-zeka/anahtar")
    def anahtari_sil() -> dict[str, Any]:
        """Anahtar dosyasını siler."""
        return {**servis.anahtari_sil(), "modeller": list(MODELLER), "en_buyuk_gunluk_sinir": EN_BUYUK_GUNLUK_SINIR}

    return rotalar
