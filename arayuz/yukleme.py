"""
Yüklenen dosyaların geçici klasöre güvenli biçimde yazılması.

Şasi ve şartname uçları aynı adımları izler: kullanıcının dosya adından yalnızca ad
kısmı alınır, dosya geçici klasöre sabit bir adla ve boyut sınırı denetlenerek yazılır,
iş bitince klasör silinir. Adımlar tek yerde durur ki iki uç farklı davranmasın.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import tempfile
from typing import Final

from fastapi import UploadFile

from cekirdek.birimler import BAYT_BIR_MB
from cekirdek.hatalar import DosyaOkumaHatasi

OKUMA_PARCA_BOYUTU: Final[int] = BAYT_BIR_MB
# Kullanıcının dosya adı geçici klasöre yazılmaz (ör. "..\..\x.stl" gibi adlara karşı);
# okuyucular yalnızca uzantıya baktığı için sabit bir ad yeterlidir.
GECICI_DOSYA_ADI: Final[str] = "yuklenen"
BOS_DOSYA_MESAJI: Final[str] = "Yüklenen dosya boş."
BUYUK_DOSYA_MESAJI: Final[str] = "Dosya {mb} MB sınırını aşıyor. Daha küçük bir dosya deneyin."


def dosya_adi(dosya: UploadFile) -> str:
    """
    Yüklenen dosyanın yalnızca adını (klasör kısmı olmadan) döndürür.

    Parametreler:
        dosya: Yüklenen dosya.
    Dönüş:
        ör. "sasi.stl"; ad yoksa boş metin.
    """
    return Path(dosya.filename or "").name


def diske_yaz(dosya: UploadFile, hedef: Path, sinir_mb: int) -> None:
    """
    Yüklenen dosyayı boyut sınırını denetleyerek parça parça diske yazar.

    Parametreler:
        dosya: Yüklenen dosya.
        hedef: Yazılacak yol.
        sinir_mb: En büyük boyut, MB.
    Hatalar:
        DosyaOkumaHatasi: Dosya boşsa veya boyut sınırını aşıyorsa.
    """
    sinir = sinir_mb * BAYT_BIR_MB
    toplam = 0
    with hedef.open("wb") as cikti:
        while parca := dosya.file.read(OKUMA_PARCA_BOYUTU):
            toplam += len(parca)
            if toplam > sinir:
                raise DosyaOkumaHatasi(BUYUK_DOSYA_MESAJI.format(mb=sinir_mb))
            cikti.write(parca)
    if toplam == 0:
        raise DosyaOkumaHatasi(BOS_DOSYA_MESAJI)


@contextmanager
def gecici_yukleme(dosya: UploadFile, sinir_mb: int) -> Iterator[Path]:
    """
    Dosyayı geçici klasöre yazar ve yolunu verir; blok bitince klasör silinir.

    Windows'ta açık dosya başka işlemce okunamadığı için NamedTemporaryFile yerine
    geçici klasör kullanılır.

    Parametreler:
        dosya: Yüklenen dosya.
        sinir_mb: En büyük boyut, MB.
    Dönüş:
        Geçici dosyanın yolu (uzantısı kullanıcının dosyasıyla aynı, küçük harf).
    Hatalar:
        DosyaOkumaHatasi: Dosya boşsa veya sınırı aşıyorsa.
    """
    uzanti = Path(dosya_adi(dosya)).suffix.lower()
    with tempfile.TemporaryDirectory() as klasor:
        yol = Path(klasor) / (GECICI_DOSYA_ADI + uzanti)
        diske_yaz(dosya, yol, sinir_mb)
        yield yol
