"""
Maliyet sekmesinin API uçları.

    GET  /api/para-birimleri                      -> seçilebilen para birimleri
    GET  /api/dronelar/{kimlik}/maliyet?yenile=   -> kalemler, toplamlar, kurlar
    PUT  /api/dronelar/{kimlik}/sasi/fiyat        -> şasi fiyatı ve "elimde" bilgisi
    PUT  /api/katalog/{parca_kimlik}/fiyat        -> parçanın 1 adet fiyatı (tüm dronelarda geçerli)
"""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from arayuz.parametreler import Kimlik

from elektronik.parcalar.turler import PARCA_DURUMU_ADLARI
from maliyet.hesap import MaliyetKalemi, Toplam
from maliyet.para import PARA_BIRIMLERI, TL
from maliyet.servis import MaliyetServisi


class FiyatIstegi(BaseModel):
    """tutar boş (null) gönderilirse fiyat silinir."""

    tutar: float | None = None
    para_birimi: str = TL


class SasiFiyatIstegi(FiyatIstegi):
    """Şasi fiyatı ve şasinin elde olup olmadığı."""

    elimde: bool = False


def _kalem_sozlugu(k: MaliyetKalemi) -> dict[str, Any]:
    return {
        "ad": k.ad, "adet": k.adet, "elimde": k.elimde,
        "tutar": k.fiyat.tutar if k.fiyat else None,
        "para_birimi": k.fiyat.para_birimi if k.fiyat else None,
        "tl_tutar": k.tl_tutar, "tahmini": k.tahmini, "eksik": k.eksik,
    }


def _toplam_sozlugu(t: Toplam) -> dict[str, Any]:
    return {"tl": t.tl, "tahmini": t.tahmini, "eksik_kalem_sayisi": t.eksik_kalem_sayisi}


def maliyet_rotalarini_olustur(servis: MaliyetServisi) -> APIRouter:
    """
    Maliyet uçlarını oluşturur.

    Parametreler:
        servis: MaliyetServisi.
    """
    rotalar = APIRouter(prefix="/api")

    @rotalar.get("/para-birimleri")
    def para_birimleri() -> list[dict[str, str]]:
        """Para birimi seçenekleri (TL ilk sırada)."""
        return [{"deger": kod, "ad": ad} for kod, ad in PARA_BIRIMLERI.items()]

    @rotalar.get("/dronelar/{kimlik}/maliyet")
    def maliyet(kimlik: Kimlik, yenile: bool = False) -> dict[str, Any]:
        """Maliyet özeti; yenile=true ise kurlar TCMB'den yeniden alınır."""
        s = servis.ozet(kimlik, kurlari_yenile=yenile)
        kalemler = []
        for kalem, satir in zip(s.ozet.kalemler, s.satirlar):
            sozluk = _kalem_sozlugu(kalem)
            if satir is None:
                sozluk["tip"] = "sasi"
            else:
                bag, parca = satir
                sozluk.update(tip="parca", parca_kimlik=parca.kimlik, bag_kimlik=bag.kimlik,
                              durum=bag.durum.value, durum_adi=PARCA_DURUMU_ADLARI[bag.durum])
            kalemler.append(sozluk)
        return {
            "kalemler": kalemler,
            "toplamlar": {ad: _toplam_sozlugu(t) for ad, t in s.ozet.toplamlar.items()},
            "kurlar": [
                {"para_birimi": k.para_birimi, "tl_karsiligi": k.tl_karsiligi, "kur_tarihi": k.kur_tarihi, "alinma_gunu": k.alinma_gunu}
                for k in s.ozet.kullanilan_kurlar
            ],
            "kur_notu": s.kur_notu,
            "kur_guncel_mi": s.kur_guncel_mi,
            "sasi_elimde": s.sasi_elimde,
            "butce_tl": s.butce_tl,
            # Bütçe yalnızca alınacak kalemlerle karşılaştırılır (elimdekiler için para harcanmaz).
            "butce_kalan_tl": s.butce_tl - s.ozet.toplamlar["alinacak"].tl if s.butce_tl is not None else None,
        }

    @rotalar.put("/dronelar/{kimlik}/sasi/fiyat")
    def sasi_fiyati(kimlik: Kimlik, istek: SasiFiyatIstegi) -> dict[str, bool]:
        """Şasi fiyatını kaydeder."""
        servis.sasi_maliyeti_kaydet(kimlik, istek.tutar, istek.para_birimi, istek.elimde)
        return {"kaydedildi": True}

    @rotalar.put("/katalog/{parca_kimlik}/fiyat")
    def parca_fiyati(parca_kimlik: Kimlik, istek: FiyatIstegi) -> dict[str, bool]:
        """Parçanın 1 adet fiyatını kaydeder."""
        servis.parca_fiyati_kaydet(parca_kimlik, istek.tutar, istek.para_birimi)
        return {"kaydedildi": True}

    return rotalar
