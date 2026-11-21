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
    PUT    /api/dronelar/{kimlik}/sasi/parcalar       -> parçalı şasi: parça rolü ve adedi
    POST   /api/dronelar/{kimlik}/sasi/dingil-hesapla -> parçalı şasi: dingili gövde ve koldan tahmin et (kaydetmez)
    PUT    /api/dronelar/{kimlik}/sasi/dingil         -> dingil mesafesini kaydet / sil
    PUT    /api/dronelar/{kimlik}/hedefler     -> uçuş süresi / yük / bütçe hedefleri

Uçlar bilerek senkron (def) yazıldı: dosya okuma işlemci yoğun olduğu için
FastAPI bunları ayrı iş parçacığında çalıştırır ve sunucu donmaz.
"""

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, UploadFile
from pydantic import BaseModel, Field

from arayuz.elektronik_sozlukleri import hedef_sozlugu
from arayuz.parametreler import Kimlik
from arayuz.yukleme import dosya_adi, gecici_yukleme
from cekirdek.ayarlar import EN_BUYUK_YUKLEME_MB
from cekirdek.birimler import UZUNLUK_CARPANLARI_MM, BirimDonusturucu
from drone.dogrulama import EN_FAZLA_PARCA_ADEDI
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
from drone.servis import DroneServisi, ParcaDegisikligi
from elektronik.hesap.sasi_pervane import EnBuyukPervaneTahmincisi
from sasi.dingil import KOL_BAGLANTISI_ADLARI, KolBaglantisi
from sasi.modeller import (
    PARCA_ROLU_ADLARI,
    BirimOnerisi,
    DingilKaynagi,
    KayitliSasi,
    SasiOlculeri,
    SasiParcasi,
)
from sasi.okuyucular.zip_okuyucu import EN_FAZLA_SASI_PARCASI


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


class ParcaIstegi(BaseModel):
    """Parçalı şaside bir parçanın rolü ve adedi (denetim serviste, Türkçe mesajla)."""

    sira: int
    rol: str
    adet: int


class ParcalarIstegi(BaseModel):
    """Parçalı şasinin değişen parçaları."""

    parcalar: list[ParcaIstegi] = Field(max_length=EN_FAZLA_SASI_PARCASI)


class DingilHesapIstegi(BaseModel):
    """Dingil tahmini için seçilen kol ve gövde parçası."""

    kol_sira: int
    govde_sira: int | None = None
    baglanti: KolBaglantisi = KolBaglantisi.MERKEZ


class DingilIstegi(BaseModel):
    """Kaydedilecek dingil; None dingili siler."""

    dingil_mm: float | None
    kaynak: DingilKaynagi = DingilKaynagi.ELLE


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
        "parcali": sasi.parcali_mi,
        "parcalar": [parca_sozlugu(p) for p in sasi.parcalar],
        "parca_rolleri": [{"deger": r.value, "ad": ad} for r, ad in PARCA_ROLU_ADLARI.items()],
        "kol_baglantilari": [{"deger": b.value, "ad": ad} for b, ad in KOL_BAGLANTISI_ADLARI.items()],
        "en_fazla_parca_adedi": EN_FAZLA_PARCA_ADEDI,
    }


def parca_sozlugu(p: SasiParcasi) -> dict[str, Any]:
    """Parçalı şasinin bir parçasını sözlüğe çevirir (ölçüler dosya biriminde)."""
    g = p.geometri
    return {
        "sira": p.sira,
        "dosya_adi": g.dosya_adi,
        "tur": g.tur.value,
        "olculer_ham": list(g.olculer),
        "tek_govde_olculeri_ham": list(g.tek_govde_olculeri) if g.tek_govde_olculeri else None,
        "hacim_ham": g.hacim,
        "alan_ham": g.alan,
        "govde_sayisi": g.govde_sayisi,
        "ozdes_govde_sayisi": g.ozdes_govde_sayisi,
        "kapali_mi": g.kapali_mi,
        "rol": p.rol.value,
        "rol_adi": PARCA_ROLU_ADLARI[p.rol],
        "adet": p.adet,
        "uyarilar": g.uyarilar,
    }


def olculer_sozlugu(olculer: SasiOlculeri | None) -> dict[str, Any] | None:
    """
    Onaylanmış ölçüleri sözlüğe çevirir; onay yoksa None.

    Arayüz birim çevirmesin diye alan ve hacim cm cinsinden de gönderilir. etkin_dingil_mm,
    pervane hesabında kullanılan dingildir (girilen ya da dış ölçüden tahmin; bilinmiyorsa None).
    """
    if olculer is None:
        return None
    sozluk = asdict(olculer)
    sozluk["alan_cm2"] = BirimDonusturucu.mm2_yi_cm2_ye_cevir(olculer.alan_mm2) if olculer.alan_mm2 is not None else None
    sozluk["hacim_cm3"] = BirimDonusturucu.mm3_u_cm3_e_cevir(olculer.hacim_mm3) if olculer.hacim_mm3 is not None else None
    sozluk["dingil_kaynagi"] = olculer.dingil_kaynagi.value if olculer.dingil_kaynagi else None
    sozluk["etkin_dingil_mm"] = EnBuyukPervaneTahmincisi().dingil_mesafesi_mm(olculer)
    sozluk["parcali_mi"] = olculer.parcali_mi
    sozluk["dingil_bilinmiyor"] = olculer.dingil_bilinmiyor
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

    @rotalar.put("/dronelar/{kimlik}/sasi/parcalar")
    def parcalari_guncelle(kimlik: Kimlik, istek: ParcalarIstegi) -> dict[str, Any]:
        """Parçalı şaside parçaların rolünü ve adedini kaydeder."""
        sasi = servis.parcalari_guncelle(
            kimlik, [ParcaDegisikligi(sira=p.sira, rol=p.rol, adet=p.adet) for p in istek.parcalar]
        )
        return {
            "yukleme": yukleme_sozlugu(sasi, servis.birim_oner(sasi.geometri)),
            "olculer": olculer_sozlugu(sasi.olculer),
        }

    @rotalar.post("/dronelar/{kimlik}/sasi/dingil-hesapla")
    def dingil_hesapla(kimlik: Kimlik, istek: DingilHesapIstegi) -> dict[str, Any]:
        """Seçilen gövde ve koldan dingili tahmin eder; KAYDETMEZ (kullanıcı onaylayınca PUT /dingil)."""
        tahmin = servis.dingil_hesapla(kimlik, istek.kol_sira, istek.baglanti, istek.govde_sira)
        return {**asdict(tahmin), "tahmini": True}

    @rotalar.put("/dronelar/{kimlik}/sasi/dingil")
    def dingil_kaydet(kimlik: Kimlik, istek: DingilIstegi) -> dict[str, Any]:
        """Dingil mesafesini kaydeder veya siler; güncel ölçüleri döndürür."""
        return {"olculer": olculer_sozlugu(servis.dingil_kaydet(kimlik, istek.dingil_mm, istek.kaynak))}

    @rotalar.put("/dronelar/{kimlik}/hedefler")
    def hedefleri_kaydet(kimlik: Kimlik, istek: HedefIstegi) -> dict[str, Any]:
        """Drone hedeflerini (uçuş süresi, yük, bütçe) kaydeder."""
        hedefler = DroneHedefleri(ucus_suresi_dk=istek.ucus_suresi_dk, yuk_g=istek.yuk_g, butce_tl=istek.butce_tl)
        return hedef_sozlugu(servis.hedefleri_kaydet(kimlik, hedefler))

    return rotalar
