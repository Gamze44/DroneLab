"""
Yapay zeka ayarları (model ve günlük istek sınırı) ve yerel ayar dosyası.

Ayarlar veri/ayarlar_yerel.json dosyasında "yapay_zeka" başlığı altında durur.
Dosya yoksa veya bozuksa varsayılanlar kullanılır.
"""

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Final

from arastirma.gemini import MODELLER, VARSAYILAN_MODEL
from cekirdek.ayarlar import YEREL_AYAR_DOSYA_ADI
from cekirdek.hatalar import GecersizDegerHatasi

AYAR_BASLIGI: Final[str] = "yapay_zeka"

# DEĞİŞTİRİLEBİLİR: Günde en çok kaç öneri isteği yapılabilir. Ücretsiz kotayı (ve olası
# ücretleri) aşmamak için bir güvenlik sınırıdır; her "Öner" tıklaması 1 istektir.
VARSAYILAN_GUNLUK_SINIR: Final[int] = 20
EN_BUYUK_GUNLUK_SINIR: Final[int] = 200


@dataclass
class YapayZekaAyarlari:
    """
    Alanlar:
        model: Kullanılacak Gemini modeli.
        gunluk_sinir: Günlük en çok istek sayısı.
    """

    model: str = VARSAYILAN_MODEL
    gunluk_sinir: int = VARSAYILAN_GUNLUK_SINIR

    def denetle(self) -> None:
        """Hatalar: GecersizDegerHatasi."""
        if self.model not in MODELLER:
            raise GecersizDegerHatasi(f"Model tanınmıyor: {self.model}. Seçenekler: {', '.join(MODELLER)}.")
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
