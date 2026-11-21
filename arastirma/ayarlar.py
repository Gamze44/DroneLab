"""
Yapay zeka ayarları (model ve günlük istek sınırı) ve yerel ayar dosyası.

Ayarlar veri/ayarlar_yerel.json dosyasında "yapay_zeka" başlığı altında durur.
Dosya yoksa veya bozuksa varsayılanlar kullanılır.
"""

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Final

from arastirma.gemini import MODELLER
from arastirma.model_secici import OTOMATIK_MODEL
from cekirdek.ayarlar import YEREL_AYAR_DOSYA_ADI
from cekirdek.hatalar import GecersizDegerHatasi

AYAR_BASLIGI: Final[str] = "yapay_zeka"
# Ayarlarda seçilebilen değerler: otomatik seçim (önerilen, varsayılan) veya belirli bir model.
SECILEBILIR_MODELLER: Final[tuple[str, ...]] = (OTOMATIK_MODEL, *MODELLER)

# DEĞİŞTİRİLEBİLİR: Günde en çok kaç yapay zeka isteği yapılabilir. Ücretsiz kotayı (ve olası
# ücretleri) aşmamak için bir güvenlik sınırıdır. Her "Öner" tıklaması 1 istektir; asistanda
# bir soru, araç kullanımına göre 1–5 istek tutabilir.
VARSAYILAN_GUNLUK_SINIR: Final[int] = 20
EN_BUYUK_GUNLUK_SINIR: Final[int] = 200


@dataclass
class YapayZekaAyarlari:
    """
    Alanlar:
        model: Kullanılacak Gemini modeli veya OTOMATIK_MODEL (program kota/yoğunluğa göre seçer).
        gunluk_sinir: Günlük en çok istek sayısı.
    """

    model: str = OTOMATIK_MODEL
    gunluk_sinir: int = VARSAYILAN_GUNLUK_SINIR

    def denetle(self) -> None:
        """Hatalar: GecersizDegerHatasi."""
        if self.model not in SECILEBILIR_MODELLER:
            raise GecersizDegerHatasi(f"Model tanınmıyor: {self.model}. Seçenekler: {', '.join(SECILEBILIR_MODELLER)}.")
        if isinstance(self.gunluk_sinir, bool) or not isinstance(self.gunluk_sinir, int) or not (
            1 <= self.gunluk_sinir <= EN_BUYUK_GUNLUK_SINIR
        ):
            raise GecersizDegerHatasi(f"Günlük sınır 1 ile {EN_BUYUK_GUNLUK_SINIR} arasında bir tam sayı olmalı.")


class YapayZekaAyarDeposu:
    """
    Yapay zeka ayarlarını yerel ayar dosyasından okur ve yazar.

    Parametreler:
        veri_klasoru: Ayar dosyasının bulunduğu klasör (veri/).
    """

    def __init__(self, veri_klasoru: Path) -> None:
        self._dosya = veri_klasoru / YEREL_AYAR_DOSYA_ADI

    def _tum_ayarlar(self) -> dict:
        try:
            veri = json.loads(self._dosya.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return veri if isinstance(veri, dict) else {}

    def oku(self) -> YapayZekaAyarlari:
        """Ayarları döndürür; geçersiz veya eksik değerler yerine varsayılan kullanılır."""
        ham = self._tum_ayarlar().get(AYAR_BASLIGI, {})
        ayarlar = YapayZekaAyarlari()
        if isinstance(ham, dict):
            aday = YapayZekaAyarlari(
                model=ham.get("model", ayarlar.model), gunluk_sinir=ham.get("gunluk_sinir", ayarlar.gunluk_sinir)
            )
            try:
                aday.denetle()
                ayarlar = aday
            except GecersizDegerHatasi:
                pass  # elle bozulmuş dosya programı durdurmasın; varsayılanlar kullanılır
        return ayarlar

    def kaydet(self, ayarlar: YapayZekaAyarlari) -> None:
        """
        Ayarları denetleyip dosyaya yazar; dosyadaki diğer başlıklar korunur.

        Hatalar:
            GecersizDegerHatasi: Değer geçersizse.
        """
        ayarlar.denetle()
        tum = self._tum_ayarlar()
        tum[AYAR_BASLIGI] = asdict(ayarlar)
        self._dosya.parent.mkdir(parents=True, exist_ok=True)
        self._dosya.write_text(json.dumps(tum, ensure_ascii=False, indent=2), encoding="utf-8")
