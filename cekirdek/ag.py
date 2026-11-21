"""
İnternet bağlantılarında ortak kullanılan yardımcılar (Gemini istemcisi, TCMB kur dosyası).
"""

from pathlib import Path
import ssl
import sys
from typing import Final

# MSYS2 Python'un sertifika paketinin olası yerleri (Python kurulum köküne göre).
KOKE_GORE_SERTIFIKA_YOLLARI: Final[tuple[str, ...]] = ("etc/ssl/certs/ca-bundle.crt",)
UST_KLASORE_GORE_SERTIFIKA_YOLLARI: Final[tuple[str, ...]] = ("usr/ssl/certs/ca-bundle.crt", "usr/ssl/cert.pem")
CA_SAYISI_ANAHTARI: Final[str] = "x509_ca"


def ssl_baglami() -> ssl.SSLContext:
    """
    Sertifika doğrulaması her zaman açık bir SSL bağlamı döndürür.

    MSYS2 Python'da sistem sertifika deposu boş gelebildiği için o durumda
    MSYS2'nin sertifika paketi yüklenir.
    """
    baglam = ssl.create_default_context()
    if not baglam.cert_store_stats()[CA_SAYISI_ANAHTARI]:
        kok = Path(sys.base_prefix)
        adaylar = [kok / y for y in KOKE_GORE_SERTIFIKA_YOLLARI] + [kok.parent / y for y in UST_KLASORE_GORE_SERTIFIKA_YOLLARI]
        for aday in adaylar:
            if aday.is_file():
                baglam.load_verify_locations(cafile=str(aday))
                break
    return baglam
