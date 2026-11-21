"""
Yapay zeka ayarlarının API uçları.

    GET    /api/ayarlar/yapay-zeka                -> anahtar var/yok, model, günlük sınır, kullanım
    PUT    /api/ayarlar/yapay-zeka                -> model / sınır / anahtar değiştir
    DELETE /api/ayarlar/yapay-zeka/anahtar        -> anahtar dosyasını sil

Anahtar hiçbir yanıtta döndürülmez.
"""

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from arastirma.ayar_servisi import YapayZekaAyarServisi


class AyarGuncelleme(BaseModel):
    """Verilmeyen alan değişmez. Anahtar yalnızca yazılır, asla geri okunmaz."""

    model: str | None = None
    gunluk_sinir: int | None = None
    anahtar: str | None = None


def ayar_rotalarini_olustur(servis: YapayZekaAyarServisi) -> APIRouter:
    """
    Yapay zeka ayarı uçlarını oluşturur.

    Parametreler:
        servis: YapayZekaAyarServisi.
    """
    rotalar = APIRouter(prefix="/api")

    @rotalar.get("/ayarlar/yapay-zeka")
    def ayarlar() -> dict[str, Any]:
        """Yapay zeka ayarları (anahtarın kendisi yok)."""
        return asdict(servis.durum())

    @rotalar.put("/ayarlar/yapay-zeka")
    def ayarlari_guncelle(istek: AyarGuncelleme) -> dict[str, Any]:
        """Ayarları değiştirir."""
        return asdict(servis.guncelle(istek.model, istek.gunluk_sinir, istek.anahtar))

    @rotalar.delete("/ayarlar/yapay-zeka/anahtar")
    def anahtari_sil() -> dict[str, Any]:
        """Anahtar dosyasını siler."""
        return asdict(servis.anahtari_sil())

    return rotalar
