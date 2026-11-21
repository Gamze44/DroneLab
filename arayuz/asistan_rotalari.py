"""
DroneLab Asistan API uçları.

    POST   /api/asistan/sohbet                      -> soru sor; yanıt akış olarak (text/event-stream) gelir
    GET    /api/asistan/gecmis?drone_kimlik=        -> sohbet geçmişi ve öneri kartları
    DELETE /api/asistan/gecmis?drone_kimlik=        -> "Yeni sohbet": geçmişi sil
    POST   /api/asistan/oneriler/{kimlik}/uygula    -> öneriyi uygula (kullanıcı onayı)
    POST   /api/asistan/oneriler/{kimlik}/vazgec    -> öneriden vazgeç

drone_kimlik verilmezse ana sayfa/ayarlar "genel sohbet"i kullanılır.

Akış biçimi (Server-Sent Events): her olay "event: <tür>" ve "data: <JSON>" satırlarıdır.
Türler: metin, arac, oneri, sifirla, hata, bitti. Anahtar yok, günlük sınır dolu gibi
hatalar akış başlamadan normal JSON hata ({"hata": ...}) olarak döner.
"""

from collections.abc import Iterator
import json
from typing import Any, Final

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from arayuz.parametreler import GovdeKimligi, Kimlik, SorguKimligi
from asistan.servis import AsistanServisi

AKIS_ICERIK_TURU: Final[str] = "text/event-stream"
# Akışın ara katmanlarda (vekil sunucu, tarayıcı önbelleği) bekletilmemesi için.
AKIS_BASLIKLARI: Final[dict[str, str]] = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
# Ekran anahtarı arayüzden gelir (ör. "elektronik"); uzun metin kabul edilmez.
EN_UZUN_EKRAN_ANAHTARI: Final[int] = 40


class SohbetIstegi(BaseModel):
    """Kullanıcının sorusu ve bulunduğu ekran."""

    mesaj: str
    drone_kimlik: GovdeKimligi | None = None
    ekran: str = Field(default="", max_length=EN_UZUN_EKRAN_ANAHTARI)


def sse_olayi(olay: dict[str, Any]) -> str:
    """Olayı Server-Sent Events biçimine çevirir."""
    return f"event: {olay['tur']}\ndata: {json.dumps(olay, ensure_ascii=False)}\n\n"


def _akis(olaylar: Iterator[dict[str, Any]]) -> Iterator[str]:
    for olay in olaylar:
        yield sse_olayi(olay)


def asistan_rotalarini_olustur(servis: AsistanServisi) -> APIRouter:
    """
    Asistan uçlarını oluşturur.

    Parametreler:
        servis: AsistanServisi.
    """
    rotalar = APIRouter(prefix="/api/asistan")

    @rotalar.post("/sohbet")
    def sohbet(istek: SohbetIstegi) -> StreamingResponse:
        """Soruyu yanıtlar; yanıt parça parça akar."""
        olaylar = servis.baslat(istek.drone_kimlik, istek.ekran, istek.mesaj)
        return StreamingResponse(_akis(olaylar), media_type=AKIS_ICERIK_TURU, headers=AKIS_BASLIKLARI)

    @rotalar.get("/gecmis")
    def gecmis(drone_kimlik: SorguKimligi = None) -> dict[str, Any]:
        """Sohbet geçmişi."""
        return {"mesajlar": servis.gecmis(drone_kimlik)}

    @rotalar.delete("/gecmis")
    def gecmisi_sil(drone_kimlik: SorguKimligi = None) -> dict[str, bool]:
        """Sohbeti temizler."""
        servis.temizle(drone_kimlik)
        return {"silindi": True}

    @rotalar.post("/oneriler/{kimlik}/uygula")
    def uygula(kimlik: Kimlik) -> dict[str, Any]:
        """Öneriyi uygular."""
        return {"oneri": servis.oneriyi_uygula(kimlik)}

    @rotalar.post("/oneriler/{kimlik}/vazgec")
    def vazgec(kimlik: Kimlik) -> dict[str, Any]:
        """Öneriden vazgeçer."""
        return {"oneri": servis.oneriden_vazgec(kimlik)}

    return rotalar
