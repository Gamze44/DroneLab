"""
Elektronik, öneri ve drone uçlarının ortak kullandığı yanıt biçimleyicileri.

Bir rota dosyası başka bir rota dosyasından içe aktarma yapmasın diye (rotalar birbirine
bağımlı olmasın) arayüze gönderilen sözlükler ve formdan gelen parça bilgisi burada durur.
"""

from dataclasses import asdict
from typing import Any

from pydantic import BaseModel, Field

from drone.hedefler import DroneHedefleri
from elektronik.hesap.agirlik import AgirlikOzeti
from elektronik.hesap.sasi_pervane import SasiGorunumu
from elektronik.hesap.ucus import HesapDegeri, UcusOzeti
from elektronik.hesap.uyum import UyumSonucu
from elektronik.parcalar.diger_parca import DigerParca
from elektronik.parcalar.drone_parcasi import DroneParcasi
from elektronik.parcalar.parca import Parca
from elektronik.parcalar.serilestirme import ParcaSerilestirici
from elektronik.parcalar.turler import (
    DIGER_ALT_TUR_ADLARI,
    PARCA_DURUMU_ADLARI,
    PARCA_TURU_ADLARI,
    DigerAltTur,
    ParcaTuru,
)
from elektronik.zorunlu_parcalar import Zorunluluk


class ParcaBilgisi(BaseModel):
    """Formdan (veya seçilen öneriden) gelen parça bilgisi."""

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


def sasi_gorunumu_sozlugu(g: SasiGorunumu | None) -> dict[str, Any] | None:
    """Şasinin üstten görünüş ölçülerini (mm ve inç) sözlüğe çevirir; şasi ölçüsü yoksa None."""
    return asdict(g) if g is not None else None


def hedef_sozlugu(h: DroneHedefleri) -> dict[str, Any]:
    """Drone hedeflerini sözlüğe çevirir."""
    return {"ucus_suresi_dk": h.ucus_suresi_dk, "yuk_g": h.yuk_g, "butce_tl": h.butce_tl}
