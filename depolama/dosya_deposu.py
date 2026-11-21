"""
Yüklenen şasi dosyalarının kopyalarının diskte saklanması.

Her drone'un dosyası veri/sasi_dosyalari/<drone kimliği>/ klasöründe durur.
Dosya adı olarak kullanıcının verdiği ad değil sabit bir ad kullanılır;
böylece Windows'ta geçersiz karakterler veya "..\\" gibi yollar sorun çıkarmaz.
Asıl dosya adı veritabanında saklanır.
"""

from pathlib import Path
import shutil
from typing import Final

SAKLANAN_DOSYA_KOKU: Final[str] = "sasi"


class SasiDosyaDeposu:
    """
    Şasi dosyalarını drone başına bir klasörde saklar.

    Parametreler:
        kok: Şasi dosyalarının ana klasörü (ör. veri/sasi_dosyalari).
    """

    def __init__(self, kok: Path) -> None:
        self.kok: Path = kok

    def _klasor(self, drone_kimlik: int) -> Path:
        """Drone'un dosya klasörünün yolu."""
        return self.kok / str(drone_kimlik)

    def kaydet(self, drone_kimlik: int, kaynak: Path) -> str:
        """
        Dosyayı drone'un klasörüne kopyalar; önceki dosyayı siler.

        Parametreler:
            drone_kimlik: Drone kimliği.
            kaynak: Kopyalanacak dosya (uzantısı korunur).
        Dönüş:
            Kopyanın, kök klasörün bir üstüne (veri klasörüne) göre yolu, '/' ayraçlı.
        """
        klasor = self._klasor(drone_kimlik)
        if klasor.exists():
            shutil.rmtree(klasor)
        klasor.mkdir(parents=True)
        hedef = klasor / (SAKLANAN_DOSYA_KOKU + kaynak.suffix.lower())
        shutil.copyfile(kaynak, hedef)
        return hedef.relative_to(self.kok.parent).as_posix()

    def tam_yol(self, goreli_yol: str) -> Path:
        """
        kaydet'in döndürdüğü göreli yolu tam yola çevirir.

        Parametreler:
            goreli_yol: Veri klasörüne göre yol.
        Dönüş:
            Tam dosya yolu.
        """
        return self.kok.parent / Path(goreli_yol)

    def sil(self, drone_kimlik: int) -> None:
        """Drone'un dosya klasörünü (varsa) siler."""
        klasor = self._klasor(drone_kimlik)
        if klasor.exists():
            shutil.rmtree(klasor)
