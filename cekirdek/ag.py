"""
İnternet bağlantılarında ortak kullanılan yardımcılar (Gemini istemcisi, TCMB kur dosyası).
"""

from pathlib import Path
import ssl
import sys


def ssl_baglami() -> ssl.SSLContext:
    """
    Sertifika doğrulaması her zaman açık bir SSL bağlamı döndürür.

    MSYS2 Python'da sistem sertifika deposu boş gelebildiği için o durumda
    MSYS2'nin sertifika paketi yüklenir.
    """
    baglam = ssl.create_default_context()
    if not baglam.cert_store_stats()["x509_ca"]:
        kok = Path(sys.base_prefix)
        for aday in (kok / "etc/ssl/certs/ca-bundle.crt", kok.parent / "usr/ssl/certs/ca-bundle.crt",
                     kok.parent / "usr/ssl/cert.pem"):
            if aday.is_file():
                baglam.load_verify_locations(cafile=str(aday))
                break
    return baglam
