"""
Sayıların kullanıcıya gösterilecek kısa Türkçe biçimi.

Uyum kontrolleri, uçuş hesabı ve şartname raporu aynı biçimi kullanır; bu yüzden
yardımcı tek yerde durur.
"""

from typing import Final

# Mesajlarda gösterilen en çok ondalık basamak.
KISA_SAYI_BASAMAGI: Final[int] = 2
BILINMEYEN_SAYI: Final[str] = "?"


def sayi_yaz(deger: float | None) -> str:
    """
    Sayıyı Türkçe biçimde kısa yazar.

    Parametreler:
        deger: Sayı veya None.
    Dönüş:
        30.5 → "30,5", 4.0 → "4", None → "?".
    """
    if deger is None:
        return BILINMEYEN_SAYI
    return f"{deger:.{KISA_SAYI_BASAMAGI}f}".rstrip("0").rstrip(".").replace(".", ",")
