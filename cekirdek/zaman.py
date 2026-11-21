"""
Zaman damgası yardımcısı.

Kayıtlardaki oluşturma/güncelleme zamanları hep aynı biçimde yazılsın diye tek yerde durur.
"""

from datetime import datetime


def simdi_iso() -> str:
    """
    Şu anki yerel zamanı saniye hassasiyetinde ISO metni olarak döndürür.

    Dönüş:
        ör. "2026-11-15T14:30:05"
    """
    return datetime.now().isoformat(timespec="seconds")
