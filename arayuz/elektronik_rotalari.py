"""
Elektronik bölümünün API uçları.

    GET    /api/parca-turleri                          -> türler, alt türler, durumlar, form alanları
    GET    /api/katalog?metin=&tur=&alt_tur=            -> katalogda arama
    PUT    /api/katalog/{parca_kimlik}                  -> katalog parçasını düzenle
    GET    /api/dronelar/{kimlik}/elektronik            -> parça listesi + zorunlular + ağırlık + uyum + uçuş
    POST   /api/dronelar/{kimlik}/parcalar              -> yeni parça ya da katalogdan parça ekle
    PATCH  /api/dronelar/{kimlik}/parcalar/{bag}        -> adet / durum değiştir
    PUT    /api/katalog/{parca_kimlik}/itki-tablosu     -> motorun itki tablosu
    DELETE /api/dronelar/{kimlik}/parcalar/{bag}        -> parçayı drone'dan kaldır

(Hedefler: PUT /api/dronelar/{kimlik}/hedefler drone_rotalari.py'dedir.)
"""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from arayuz.elektronik_sozlukleri import (
    ParcaBilgisi,
    agirlik_sozlugu,
    bag_sozlugu,
    hedef_sozlugu,
    parca_sozlugu,
    sasi_gorunumu_sozlugu,
    ucus_sozlugu,
    uyum_sozlugu,
    zorunluluk_sozlugu,
)
from arayuz.parametreler import GovdeKimligi, Kimlik
from cekirdek.hatalar import GecersizDegerHatasi
from elektronik.parcalar.alan_tanimlari import alan_tanimlari
from elektronik.parcalar.kayit import PARCA_SINIFLARI
from elektronik.parcalar.turler import (
    DIGER_ALT_TUR_ADLARI,
    PARCA_DURUMU_ADLARI,
    PARCA_TURU_ADLARI,
    DigerAltTur,
    ParcaDurumu,
    ParcaTuru,
)
from elektronik.servis import ElektronikServisi


class ParcaEklemeIstegi(BaseModel):
    """Drone'a parça ekleme: ya yeni parça bilgisi ya da katalogdaki parçanın kimliği verilir."""

    parca: ParcaBilgisi | None = None
    parca_kimlik: GovdeKimligi | None = None
    adet: int = 1
    durum: ParcaDurumu = ParcaDurumu.PLANLANAN


class ItkiSatiri(BaseModel):
    """İtki tablosunun bir satırı (gerilim, gaz ve itki zorunlu)."""

    gerilim_v: float | None = None
    gaz_yuzde: float | None = None
    itki_g: float | None = None
    pervane: str | None = None
    akim_a: float | None = None
    guc_w: float | None = None


class ItkiTablosuIstegi(BaseModel):
    """Motorun bütün itki tablosu; boş liste tabloyu siler."""

    satirlar: list[ItkiSatiri] = Field(default_factory=list)


class BagGuncellemeIstegi(BaseModel):
    """Adet ve/veya durum değişikliği."""

    adet: int | None = None
    durum: ParcaDurumu | None = None


# ---------- Uçlar ----------


def elektronik_rotalarini_olustur(servis: ElektronikServisi) -> APIRouter:
    """
    Elektronik API uçlarını oluşturur.

    Parametreler:
        servis: İşlemleri yürüten ElektronikServisi.
    """
    rotalar = APIRouter(prefix="/api")

    @rotalar.get("/parca-turleri")
    def parca_turleri() -> dict[str, Any]:
        """Parça formunun seçenekleri ve her türün teknik alanları."""
        return {
            "turler": [
                {"deger": t.value, "ad": PARCA_TURU_ADLARI[t], "alanlar": alan_tanimlari(PARCA_SINIFLARI[t])}
                for t in ParcaTuru
            ],
            "alt_turler": [{"deger": t.value, "ad": DIGER_ALT_TUR_ADLARI[t]} for t in DigerAltTur],
            "durumlar": [{"deger": d.value, "ad": PARCA_DURUMU_ADLARI[d]} for d in ParcaDurumu],
        }

    @rotalar.get("/katalog")
    def katalog_ara(metin: str = "", tur: ParcaTuru | None = None, alt_tur: DigerAltTur | None = None) -> list[dict[str, Any]]:
        """Katalogda parça arar."""
        return [parca_sozlugu(p) for p in servis.katalog_ara(metin, tur=tur, alt_tur=alt_tur)]

    @rotalar.put("/katalog/{parca_kimlik}")
    def katalog_parcasi_guncelle(parca_kimlik: Kimlik, bilgi: ParcaBilgisi) -> dict[str, Any]:
        """Katalog parçasının bilgilerini değiştirir (onu kullanan tüm droneları etkiler)."""
        return parca_sozlugu(servis.parca_guncelle(parca_kimlik, bilgi.ortak(), bilgi.teknik))

    @rotalar.get("/dronelar/{kimlik}/elektronik")
    def elektronik_ozeti(kimlik: Kimlik) -> dict[str, Any]:
        """Drone'un parça listesi, zorunlu parça durumu ve ağırlık özeti."""
        ozet = servis.ozet(kimlik)
        return {
            "kalemler": [{"bag": bag_sozlugu(b), "parca": parca_sozlugu(p)} for b, p in ozet.kalemler],
            "zorunluluklar": [zorunluluk_sozlugu(z) for z in ozet.zorunluluklar],
            "agirlik": agirlik_sozlugu(ozet.agirlik),
            "uyum": [uyum_sozlugu(u) for u in ozet.uyum],
            "ucus": ucus_sozlugu(ozet.ucus),
            "hedefler": hedef_sozlugu(ozet.hedefler),
            "sasi_gorunumu": sasi_gorunumu_sozlugu(ozet.sasi_gorunumu),
            "motor_sayisi": ozet.drone.motor_sayisi,
        }

    @rotalar.put("/katalog/{parca_kimlik}/itki-tablosu")
    def itki_tablosu_kaydet(parca_kimlik: Kimlik, istek: ItkiTablosuIstegi) -> dict[str, Any]:
        """Motorun itki tablosunu kaydeder (bu motoru kullanan tüm dronelarda geçerli)."""
        return parca_sozlugu(servis.itki_tablosu_kaydet(parca_kimlik, [s.model_dump() for s in istek.satirlar]))

    @rotalar.post("/dronelar/{kimlik}/parcalar")
    def parca_ekle(kimlik: Kimlik, istek: ParcaEklemeIstegi) -> dict[str, Any]:
        """Yeni parçayı (kataloğa da kaydederek) ya da katalogdaki parçayı drone'a ekler."""
        if (istek.parca is None) == (istek.parca_kimlik is None):
            raise GecersizDegerHatasi("Ya yeni parça bilgisi ya da katalogdaki parça seçilmeli.")
        if istek.parca_kimlik is not None:
            bag = servis.katalogdan_ekle(kimlik, istek.parca_kimlik, istek.adet, istek.durum)
        else:
            bilgi = istek.parca
            parca = servis.parca_olustur(bilgi.tur, bilgi.alt_tur, bilgi.ortak(), bilgi.teknik)
            bag = servis.yeni_parca_ekle(kimlik, parca, istek.adet, istek.durum)
        return bag_sozlugu(bag)

    @rotalar.patch("/dronelar/{kimlik}/parcalar/{bag_kimlik}")
    def bag_guncelle(kimlik: Kimlik, bag_kimlik: Kimlik, istek: BagGuncellemeIstegi) -> dict[str, Any]:
        """Parçanın bu drone'daki adedini/durumunu değiştirir."""
        return bag_sozlugu(servis.bag_guncelle(kimlik, bag_kimlik, istek.adet, istek.durum))

    @rotalar.delete("/dronelar/{kimlik}/parcalar/{bag_kimlik}")
    def bag_sil(kimlik: Kimlik, bag_kimlik: Kimlik) -> dict[str, bool]:
        """Parçayı drone'dan kaldırır (katalogda kalır)."""
        servis.bag_sil(kimlik, bag_kimlik)
        return {"kaldirildi": True}

    return rotalar
