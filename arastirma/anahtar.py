"""
Gemini API anahtarının bulunması ve saklanması.

Arama sırası: ortam değişkenleri (GEMINI_API_KEY, GOOGLE_API_KEY), sonra
veri/gemini_anahtari.txt. Anahtar kodun içinde durmaz ve hiçbir API yanıtında
döndürülmez; dışarıya yalnızca "var / yok" ve nereden geldiği söylenir.
"""

import os
from pathlib import Path
from typing import Final

from cekirdek.ayarlar import ANAHTAR_DOSYA_ADI, ANAHTAR_ORTAM_DEGISKENLERI
from cekirdek.hatalar import GecersizDegerHatasi

KAYNAK_ORTAM: Final[str] = "ortam_degiskeni"
KAYNAK_DOSYA: Final[str] = "dosya"

# Anahtarlar bu uzunluk aralığında ve boşluksuz olmalı; yanlışlıkla yapıştırılan metni yakalamak için.
EN_KISA_ANAHTAR: Final[int] = 20
EN_UZUN_ANAHTAR: Final[int] = 200


class AnahtarDeposu:
    """
    API anahtarını okur, kaydeder ve siler.

    Parametreler:
        veri_klasoru: Anahtar dosyasının bulunduğu klasör (veri/).
    """

    def __init__(self, veri_klasoru: Path) -> None:
        self._dosya = veri_klasoru / ANAHTAR_DOSYA_ADI

    def _ortamdan(self) -> str | None:
        for ad in ANAHTAR_ORTAM_DEGISKENLERI:
            deger = os.environ.get(ad, "").strip()
            if deger:
                return deger
        return None

    def _dosyadan(self) -> str | None:
        try:
            deger = self._dosya.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        return deger or None

    def oku(self) -> str | None:
        """Anahtarı döndürür; hiçbir yerde yoksa None. Dönen değer asla ekrana/loga yazılmamalı."""
        return self._ortamdan() or self._dosyadan()

    def kaynak(self) -> str | None:
        """Anahtarın nereden geldiği: "ortam_degiskeni", "dosya" veya yoksa None."""
        if self._ortamdan():
            return KAYNAK_ORTAM
        if self._dosyadan():
            return KAYNAK_DOSYA
        return None

    def kaydet(self, anahtar: str) -> None:
        """
        Anahtarı veri/ klasöründeki dosyaya yazar.

        Hatalar:
            GecersizDegerHatasi: Anahtar boşsa, boşluk içeriyorsa veya uzunluğu anahtara benzemiyorsa.
        """
        anahtar = anahtar.strip()
        if not (EN_KISA_ANAHTAR <= len(anahtar) <= EN_UZUN_ANAHTAR) or any(ch.isspace() for ch in anahtar):
            raise GecersizDegerHatasi("Bu bir Gemini API anahtarına benzemiyor. Anahtarı Google AI Studio'dan kopyalayın.")
        self._dosya.parent.mkdir(parents=True, exist_ok=True)
        self._dosya.write_text(anahtar, encoding="utf-8")

    def sil(self) -> None:
        """Anahtar dosyasını siler (ortam değişkenine dokunmaz)."""
        self._dosya.unlink(missing_ok=True)
