"""
Yapay zeka önerisinin API uçları (ayarların uçları: ayar_rotalari.py).

    POST   /api/dronelar/{kimlik}/oneriler        -> Gemini'den aday iste ve değerlendir
    POST   /api/dronelar/{kimlik}/oneriler/sec    -> seçilen adayı drone'a "önerilen" olarak ekle
"""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from arayuz.elektronik_sozlukleri import ParcaBilgisi, bag_sozlugu, hesap_degeri_sozlugu, parca_sozlugu, uyum_sozlugu
from arayuz.parametreler import GovdeKimligi, Kimlik
from elektronik.oneri.servis import OneriAdayi, OneriServisi
from elektronik.parcalar.turler import DigerAltTur, ParcaTuru


class OneriIstegi(BaseModel):
    """Hangi parça türü için öneri isteniyor."""

    tur: ParcaTuru
    alt_tur: DigerAltTur | None = None


class OneriSecimi(BaseModel):
    """Seçilen aday: katalogdaysa kimliği, değilse parça bilgisi."""

    parca: ParcaBilgisi | None = None
    parca_kimlik: GovdeKimligi | None = None
    adet: int = 1


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
    Öneri uçlarını oluşturur.

    Parametreler:
        servis: OneriServisi.
    """
    rotalar = APIRouter(prefix="/api")

    @rotalar.post("/dronelar/{kimlik}/oneriler")
    def oner(kimlik: Kimlik, istek: OneriIstegi) -> dict[str, Any]:
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
    def sec(kimlik: Kimlik, secim: OneriSecimi) -> dict[str, Any]:
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

    return rotalar
