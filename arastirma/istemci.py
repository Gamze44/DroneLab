"""
Yapay zekaya istek göndermenin ortak adımları: anahtar var mı, günlük sınır
aşıldı mı, hangi model kullanılacak. Öneri ve şartname madde çıkarımı bu sınıfı
kullanır; böylece sınır ve anahtar kuralları tek yerde durur.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from arastirma.anahtar import AnahtarDeposu
from arastirma.ayarlar import YapayZekaAyarDeposu
from arastirma.gemini import GeminiSaglayicisi
from arastirma.kullanim import GunlukKullanimSayaci
from arastirma.saglayici import ArastirmaSaglayicisi
from cekirdek.ayarlar import VERITABANI_DOSYA_ADI
from cekirdek.hatalar import YapayZekaHatasi
from depolama.veritabani import Veritabani

HTTP_YETKISIZ: Final[int] = 401
ANAHTAR_YOK_MESAJI: Final[str] = (
    "Gemini API anahtarı bulunamadı. Ana sayfadaki Ayarlar bölümünden anahtar girin; "
    "o zamana kadar bilgileri elle girebilirsiniz."
)

SaglayiciUretici = Callable[[str, str], ArastirmaSaglayicisi]


def gemini_uret(anahtar: str, model: str) -> ArastirmaSaglayicisi:
    """Varsayılan sağlayıcı üretici (gerçek Gemini)."""
    return GeminiSaglayicisi(anahtar, model)


@dataclass
class YapayZekaYaniti:
    """
    Alanlar:
        veri: Modelin JSON yanıtı.
        bugun_kullanilan / gunluk_sinir: Günlük kullanım bilgisi.
        model: Kullanılan model.
    """

    veri: dict[str, Any]
    bugun_kullanilan: int
    gunluk_sinir: int
    model: str


class YapayZekaIstemcisi:
    """
    Anahtar ve günlük sınır kontrolüyle yapay zekaya şemalı istek gönderir.

    Parametreler:
        veri_klasoru: veri/ klasörü (anahtar, ayarlar, kullanım sayacı).
        saglayici_uretici: (anahtar, model) -> sağlayıcı; testlerde sahtesi verilir.
        veritabani: Ortak Veritabani; verilmezse veri klasöründeki dosya açılır.
    """

    def __init__(
        self,
        veri_klasoru: Path,
        saglayici_uretici: SaglayiciUretici = gemini_uret,
        veritabani: Veritabani | None = None,
    ) -> None:
        self.anahtar = AnahtarDeposu(veri_klasoru)
        self.ayarlar = YapayZekaAyarDeposu(veri_klasoru)
        self.sayac = GunlukKullanimSayaci(veritabani or Veritabani(veri_klasoru / VERITABANI_DOSYA_ADI))
        self._uretici = saglayici_uretici

    def istek(self, sistem_talimati: str, istem: str, sema: dict[str, Any]) -> YapayZekaYaniti:
        """
        Hatalar:
            YapayZekaHatasi: Anahtar yoksa, günlük sınır dolduysa veya istek başarısızsa.
        """
        anahtar = self.anahtar.oku()
        if not anahtar:
            raise YapayZekaHatasi(ANAHTAR_YOK_MESAJI, HTTP_YETKISIZ)
        ayarlar = self.ayarlar.oku()
        kullanilan = self.sayac.harca(ayarlar.gunluk_sinir)
        veri = self._uretici(anahtar, ayarlar.model).json_uret(sistem_talimati, istem, sema)
        return YapayZekaYaniti(veri, kullanilan, ayarlar.gunluk_sinir, ayarlar.model)
