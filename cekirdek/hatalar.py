"""
Programa özel hata sınıfları.

Tüm özel hatalar DroneProgramHatasi sınıfından türer. Böylece arayüz katmanı
yalnızca bu temel sınıfı yakalayarak kullanıcıya anlaşılır bir Türkçe mesaj
gösterebilir; beklenmeyen Python hataları ise ayrı ele alınır.
"""

from collections.abc import Iterable
from http import HTTPStatus


class DroneProgramHatasi(Exception):
    """
    Programdaki tüm özel hataların temel sınıfı.

    Parametreler:
        mesaj: Kullanıcıya gösterilecek Türkçe açıklama.
    """

    def __init__(self, mesaj: str) -> None:
        super().__init__(mesaj)
        self.mesaj: str = mesaj


class GecersizDegerHatasi(DroneProgramHatasi):
    """
    Bir değer geçersiz olduğunda fırlatılır (ör. negatif kütle, sayı olmayan girdi).

    Parametreler:
        mesaj: Neyin neden geçersiz olduğunu anlatan Türkçe açıklama.
    """


class DosyaOkumaHatasi(DroneProgramHatasi):
    """
    Desteklenen türdeki bir dosya açılamadığında veya içinden geometri
    çıkarılamadığında fırlatılır (bozuk dosya, boş çizim, çok büyük dosya gibi).

    Parametreler:
        mesaj: Sorunu ve kullanıcının ne yapabileceğini anlatan Türkçe açıklama.
    """


class DesteklenmeyenDosyaHatasi(DroneProgramHatasi):
    """
    Program dosya türünü okuyamadığında fırlatılır (ör. SLDPRT, F3D).

    Parametreler:
        mesaj: Neden okunamadığını ve hangi formatta dışa aktarılması gerektiğini
            anlatan Türkçe açıklama.
        rehber: Varsa dosyanın geldiği programa özel dışa aktarma adımları.
    """

    def __init__(self, mesaj: str, rehber: list[str] | None = None) -> None:
        super().__init__(mesaj)
        self.rehber: list[str] = rehber or []


class KayitBulunamadiHatasi(DroneProgramHatasi):
    """
    İstenen kayıt (ör. yüklenmiş şasi) bellekte bulunamadığında fırlatılır.

    Parametreler:
        mesaj: Kullanıcıya gösterilecek Türkçe açıklama.
    """


class KayitZatenVarHatasi(DroneProgramHatasi):
    """
    Aynı kayıt (ör. aynı üretici ve modeldeki parça) zaten varken tekrar
    eklenmeye çalışıldığında fırlatılır.

    Parametreler:
        mesaj: Kullanıcıya gösterilecek Türkçe açıklama.
        mevcut_kimlik: Var olan kaydın kimliği; arayüz kullanıcıyı ona yönlendirebilir.
    """

    def __init__(self, mesaj: str, mevcut_kimlik: int) -> None:
        super().__init__(mesaj)
        self.mevcut_kimlik: int = mevcut_kimlik


class YapayZekaHatasi(DroneProgramHatasi):
    """
    Yapay zeka (Gemini) isteği yapılamadığında fırlatılır: anahtar yok/geçersiz,
    kota doldu, günlük sınır aşıldı, bağlantı yok veya yanıt anlaşılamadı.

    Parametreler:
        mesaj: Kullanıcıya gösterilecek Türkçe açıklama (anahtarın kendisi asla yazılmaz).
        http_kodu: Arayüze döndürülecek HTTP durum kodu.
    """

    def __init__(self, mesaj: str, http_kodu: int = HTTPStatus.BAD_GATEWAY) -> None:
        super().__init__(mesaj)
        self.http_kodu: int = http_kodu


class BirimHatasi(DroneProgramHatasi):
    """
    Tanınmayan bir birim kullanıldığında fırlatılır.

    Parametreler:
        birim: Kullanıcının verdiği, tanınmayan birim adı.
        desteklenen_birimler: Kabul edilen birim adları; mesajda kullanıcıya listelenir.
    """

    def __init__(self, birim: str, desteklenen_birimler: Iterable[str]) -> None:
        self.birim: str = birim
        self.desteklenen_birimler: list[str] = list(desteklenen_birimler)
        mesaj = (
            f"'{birim}' birimi tanınmıyor. "
            f"Kullanılabilecek birimler: {', '.join(self.desteklenen_birimler)}."
        )
        super().__init__(mesaj)
