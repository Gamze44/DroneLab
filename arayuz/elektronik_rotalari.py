"""
Elektronik bölümünün API uçları.

    GET    /api/parca-turleri                          -> türler, alt türler, durumlar, form alanları
    GET    /api/katalog?metin=&tur=&alt_tur=            -> katalogda arama
    PUT    /api/katalog/{parca_kimlik}                  -> katalog parçasını düzenle
    GET    /api/dronelar/{kimlik}/elektronik            -> parça listesi + zorunlular + ağırlık + uyum + uçuş
    POST   /api/dronelar/{kimlik}/parcalar              -> yeni parça ya da katalogdan parça ekle
    PATCH  /api/dronelar/{kimlik}/parcalar/{bag}        -> adet / durum değiştir
    PUT    /api/dronelar/{kimlik}/hedefler              -> uçuş süresi / yük / bütçe hedefleri
    PUT    /api/katalog/{parca_kimlik}/itki-tablosu     -> motorun itki tablosu
    DELETE /api/dronelar/{kimlik}/parcalar/{bag}        -> parçayı drone'dan kaldır
"""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from arayuz.parametreler import GovdeKimligi, Kimlik
from cekirdek.hatalar import GecersizDegerHatasi
from drone.hedefler import DroneHedefleri
from elektronik.hesap.agirlik import AgirlikOzeti
from elektronik.hesap.sasi_pervane import EnBuyukPervaneTahmincisi
from sasi.modeller import SasiOlculeri
from elektronik.hesap.ucus import HesapDegeri, UcusOzeti
from elektronik.hesap.uyum import UyumSonucu
from elektronik.parcalar.alan_tanimlari import alan_tanimlari
from elektronik.parcalar.diger_parca import DigerParca
from elektronik.parcalar.drone_parcasi import DroneParcasi
from elektronik.parcalar.kayit import PARCA_SINIFLARI
from elektronik.parcalar.parca import Parca
from elektronik.parcalar.serilestirme import ParcaSerilestirici
from elektronik.parcalar.turler import (
    DIGER_ALT_TUR_ADLARI,
    PARCA_DURUMU_ADLARI,
    PARCA_TURU_ADLARI,
    DigerAltTur,
    ParcaDurumu,
    ParcaTuru,
)
from elektronik.servis import ElektronikServisi
from elektronik.zorunlu_parcalar import Zorunluluk


class ParcaBilgisi(BaseModel):
    """Formdan gelen parça bilgisi."""

    tur: ParcaTuru
    alt_tur: DigerAltTur | None = None
    uretici: str
    model: str
    ad: str | None = None
    agirlik_g: float | None = None
    kaynak_url: str | None = None
    notlar: str | None = None
    teknik: dict[str, Any] = Field(default_factory=dict)

    def ortak(self) -> dict[str, Any]:
        """Ortak alanlar sözlüğü."""
        return {
            "uretici": self.uretici, "model": self.model, "ad": self.ad, "agirlik_g": self.agirlik_g,
            "kaynak_url": self.kaynak_url, "notlar": self.notlar,
        }


class ParcaEklemeIstegi(BaseModel):
    """Drone'a parça ekleme: ya yeni parça bilgisi ya da katalogdaki parçanın kimliği verilir."""

    parca: ParcaBilgisi | None = None
    parca_kimlik: GovdeKimligi | None = None
    adet: int = 1
    durum: ParcaDurumu = ParcaDurumu.PLANLANAN


class HedefIstegi(BaseModel):
    """Drone hedefleri; boş (null) alan o hedefin girilmediği anlamına gelir."""

    ucus_suresi_dk: float | None = None
    yuk_g: float | None = None
    butce_tl: float | None = None


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


# ---------- JSON'a çeviriciler ----------


def parca_sozlugu(parca: Parca) -> dict[str, Any]:
    """Parçayı arayüze gönderilecek sözlüğe çevirir."""
    alt_tur = parca.alt_tur if isinstance(parca, DigerParca) else None
    return {
        "kimlik": parca.kimlik,
        "tur": parca.tur.value,
        "tur_adi": PARCA_TURU_ADLARI[parca.tur],
        "alt_tur": alt_tur.value if alt_tur else None,
        "alt_tur_adi": DIGER_ALT_TUR_ADLARI[alt_tur] if alt_tur else None,
        "uretici": parca.uretici,
        "model": parca.model,
        "ad": parca.ad,
        "gorunen_ad": parca.gorunen_ad,
        "agirlik_g": parca.agirlik_g,
        "dogrulandi": parca.dogrulandi,
        "kaynak_url": parca.kaynak_url,
        "notlar": parca.notlar,
        "teknik": ParcaSerilestirici.teknik_sozluk(parca),
        "eksik_alanlar": parca.eksik_teknik_alanlar(),
    }


def bag_sozlugu(bag: DroneParcasi) -> dict[str, Any]:
    """Drone–parça bağını sözlüğe çevirir."""
    return {
        "kimlik": bag.kimlik,
        "parca_kimlik": bag.parca_kimlik,
        "adet": bag.adet,
        "durum": bag.durum.value,
        "durum_adi": PARCA_DURUMU_ADLARI[bag.durum],
    }


def zorunluluk_sozlugu(z: Zorunluluk) -> dict[str, Any]:
    """Zorunluluk sonucunu sözlüğe çevirir."""
    return {"etiket": z.etiket, "gereken": z.gereken, "mevcut": z.mevcut, "durum": z.durum.value, "aciklama": z.aciklama}


def agirlik_sozlugu(a: AgirlikOzeti) -> dict[str, Any]:
    """Ağırlık özetini sözlüğe çevirir."""
    return {
        "sasi_g": a.sasi_g, "parcalar_g": a.parcalar_g, "yuk_g": a.yuk_g, "kablo_payi_g": a.kablo_payi_g,
        "toplam_g": a.toplam_g, "agirligi_eksik_parcalar": a.agirligi_eksik_parcalar,
        "tahmini": a.tahmini, "eksiksiz_mi": a.eksiksiz_mi,
    }


def uyum_sozlugu(u: UyumSonucu) -> dict[str, Any]:
    """Uyum kontrolü sonucunu sözlüğe çevirir."""
    return {
        "kod": u.kod, "baslik": u.baslik, "durum": u.durum.value, "aciklama": u.aciklama,
        "ilgili_parcalar": list(u.ilgili_parcalar), "tahmini": u.tahmini,
    }


def hesap_degeri_sozlugu(h: HesapDegeri) -> dict[str, Any]:
    """Tek hesap çıktısını sözlüğe çevirir."""
    return {"deger": h.deger, "tahmini": h.tahmini, "aciklama": h.aciklama}


def ucus_sozlugu(u: UcusOzeti) -> dict[str, Any]:
    """Uçuş hesabını sözlüğe çevirir."""
    return {
        "toplam_agirlik_g": hesap_degeri_sozlugu(u.toplam_agirlik_g),
        "toplam_itki_g": hesap_degeri_sozlugu(u.toplam_itki_g),
        "itki_agirlik_orani": hesap_degeri_sozlugu(u.itki_agirlik_orani),
        "hedef_itki_agirlik": u.hedef_itki_agirlik,
        "hedefe_ulasiyor_mu": u.hedefe_ulasiyor_mu,
        "asili_gaz_yuzde": hesap_degeri_sozlugu(u.asili_gaz_yuzde),
        "asili_akim_a": hesap_degeri_sozlugu(u.asili_akim_a),
        "toplam_maks_akim_a": hesap_degeri_sozlugu(u.toplam_maks_akim_a),
        "ucus_suresi_dk": hesap_degeri_sozlugu(u.ucus_suresi_dk),
        "hedef_ucus_suresi_dk": u.hedef_ucus_suresi_dk,
        "ucus_suresi_hedefe_ulasiyor_mu": u.ucus_suresi_hedefe_ulasiyor_mu,
        "notlar": u.notlar,
    }


def sasi_gorunumu_sozlugu(olculer: SasiOlculeri | None, motor_sayisi: int) -> dict[str, Any] | None:
    """
    Şasinin üstten görünüş çizimi için ölçüler (mm). Motor yerleri tahminidir (bkz. sasi_pervane.py).

    Dönüş:
        Şasi birimi onaylanmadıysa None.
    """
    if olculer is None:
        return None
    tahminci = EnBuyukPervaneTahmincisi()
    return {
        "en_mm": olculer.en_mm,
        "boy_mm": olculer.boy_mm,
        "dingil_mm": tahminci.dingil_mesafesi_mm(olculer),
        "en_buyuk_pervane_inc": tahminci.tahmin_et(olculer, motor_sayisi),
    }


def hedef_sozlugu(h: DroneHedefleri) -> dict[str, Any]:
    """Drone hedeflerini sözlüğe çevirir."""
    return {"ucus_suresi_dk": h.ucus_suresi_dk, "yuk_g": h.yuk_g, "butce_tl": h.butce_tl}


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
            "sasi_gorunumu": sasi_gorunumu_sozlugu(ozet.sasi_olculeri, ozet.drone.motor_sayisi),
            "motor_sayisi": ozet.drone.motor_sayisi,
        }

    @rotalar.put("/dronelar/{kimlik}/hedefler")
    def hedefleri_kaydet(kimlik: Kimlik, istek: HedefIstegi) -> dict[str, Any]:
        """Drone hedeflerini (uçuş süresi, yük, bütçe) kaydeder."""
        hedefler = DroneHedefleri(ucus_suresi_dk=istek.ucus_suresi_dk, yuk_g=istek.yuk_g, butce_tl=istek.butce_tl)
        return hedef_sozlugu(servis.hedefleri_kaydet(kimlik, hedefler))

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
