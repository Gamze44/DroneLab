"""
Parça alanlarının temel denetimi.

Burada yalnızca fiziksel olarak imkânsız değerler reddedilir (negatif ağırlık,
yarım kanat, en az > en çok gibi). "KV 100–10.000 arası mı" gibi makullük
denetimleri yapay zekadan gelen verileri süzmek içindir ve sonraki aşamada
ayrı bir yerde yapılacak.
"""

import math
import types
import typing
from typing import Any, Final

from cekirdek.hatalar import GecersizDegerHatasi
from elektronik.parcalar.turler import alan_etiketi

IZINLI_URL_ONEKLERI: Final[tuple[str, ...]] = ("http://", "https://")


class AlanCinsi:
    """Bir alanın tür ipucundan çıkarılan denetim cinsi."""

    TAMSAYI: Final[str] = "tamsayi"
    SAYI: Final[str] = "sayi"
    METIN: Final[str] = "metin"
    MANTIKSAL: Final[str] = "mantiksal"
    METIN_LISTESI: Final[str] = "metin_listesi"
    SAYI_LISTESI: Final[str] = "sayi_listesi"
    DIGER: Final[str] = "diger"  # enum, nesne listesi gibi türe özel denetlenenler


class DegerDenetleyici:
    """Sayı, metin, liste ve bağlantı alanlarını denetleyen yardımcı."""

    @staticmethod
    def alan_cinsi(tur_ipucu: Any) -> str:
        """
        Alanın tür ipucundan (ör. "int | None", "list[str] | None") denetim cinsini bulur.

        Denetim değerin kendisine değil tanımlı türe bakar; böylece sayı alanına
        "45" gibi metin verilirse fark edilir.
        """
        if isinstance(tur_ipucu, types.UnionType) or typing.get_origin(tur_ipucu) is typing.Union:
            adaylar = [t for t in typing.get_args(tur_ipucu) if t is not type(None)]
            tur_ipucu = adaylar[0] if len(adaylar) == 1 else None
        if tur_ipucu is bool:
            return AlanCinsi.MANTIKSAL
        if tur_ipucu is int:
            return AlanCinsi.TAMSAYI
        if tur_ipucu is float:
            return AlanCinsi.SAYI
        if tur_ipucu is str:
            return AlanCinsi.METIN
        if typing.get_origin(tur_ipucu) is list:
            ic = typing.get_args(tur_ipucu)
            if ic == (str,):
                return AlanCinsi.METIN_LISTESI
            if ic in ((float,), (int,)):
                return AlanCinsi.SAYI_LISTESI
        return AlanCinsi.DIGER

    @staticmethod
    def mantiksal(alan: str, deger: Any) -> None:
        """Değerin True/False (veya None) olduğunu denetler."""
        if deger is not None and not isinstance(deger, bool):
            raise GecersizDegerHatasi(f"{alan_etiketi(alan)} evet/hayır olmalı (girilen: {deger!r}).")

    @staticmethod
    def metin(alan: str, deger: Any) -> str | None:
        """Değerin metin olduğunu denetler; kırpar, boşsa None döndürür."""
        if deger is None:
            return None
        if not isinstance(deger, str):
            raise GecersizDegerHatasi(f"{alan_etiketi(alan)} metin olmalı (girilen: {deger!r}).")
        return deger.strip() or None

    @staticmethod
    def zorunlu_metin(alan: str, deger: Any) -> str:
        """
        Boş olmaması gereken metni denetler ve kırpar.

        Hatalar:
            GecersizDegerHatasi: Değer metin değilse veya boşsa.
        """
        if not isinstance(deger, str) or not deger.strip():
            raise GecersizDegerHatasi(f"{alan_etiketi(alan)} boş olamaz.")
        return deger.strip()

    @staticmethod
    def secimli_metin(deger: Any) -> str | None:
        """Boş metni None'a çevirir, diğerlerini kırpar."""
        if deger is None:
            return None
        metin = str(deger).strip()
        return metin or None

    @staticmethod
    def pozitif_sayi(alan: str, deger: Any, tamsayi: bool = False) -> None:
        """
        Sayının sonlu ve sıfırdan büyük olduğunu denetler; None serbesttir.

        Parametreler:
            alan: Alan adı (hata mesajında etiketiyle gösterilir).
            deger: Denetlenecek değer.
            tamsayi: True ise kesirli değer (ör. 2,5 kanat) reddedilir.
        Hatalar:
            GecersizDegerHatasi: Değer sayı değilse, sonsuz/NaN ise, sıfır veya negatifse.
        """
        if deger is None:
            return
        etiket = alan_etiketi(alan)
        if isinstance(deger, bool) or not isinstance(deger, (int, float)) or not math.isfinite(deger):
            raise GecersizDegerHatasi(f"{etiket} geçerli bir sayı olmalı (girilen: {deger!r}).")
        if tamsayi and not isinstance(deger, int):
            raise GecersizDegerHatasi(f"{etiket} tam sayı olmalı (girilen: {deger}).")
        if deger <= 0:
            raise GecersizDegerHatasi(f"{etiket} sıfırdan büyük olmalı (girilen: {deger}).")

    @classmethod
    def pozitif_sayi_listesi(cls, alan: str, degerler: Any) -> None:
        """Listedeki her sayının pozitif olduğunu denetler; None serbesttir."""
        if degerler is None:
            return
        if not isinstance(degerler, list):
            raise GecersizDegerHatasi(f"{alan_etiketi(alan)} bir liste olmalı.")
        for deger in degerler:
            if not isinstance(deger, (int, float)) or isinstance(deger, bool):
                raise GecersizDegerHatasi(f"{alan_etiketi(alan)} listesinde sayı olmayan değer var: {deger!r}.")
            cls.pozitif_sayi(alan, deger)

    @staticmethod
    def metin_listesi(alan: str, degerler: Any) -> list[str] | None:
        """
        Metin listesini denetler; boş öğeleri atar, tekrarları siler (sırayı korur).

        Dönüş:
            Temizlenmiş liste; boş kalırsa None.
        """
        if degerler is None:
            return None
        if not isinstance(degerler, list) or not all(isinstance(d, str) for d in degerler):
            raise GecersizDegerHatasi(f"{alan_etiketi(alan)} metinlerden oluşan bir liste olmalı.")
        temiz = list(dict.fromkeys(d.strip() for d in degerler if d.strip()))
        return temiz or None

    @staticmethod
    def aralik_sirasi(alt_alan: str, alt: float | None, ust_alan: str, ust: float | None) -> None:
        """
        İkisi de girilmişse alt sınırın üst sınırdan büyük olmadığını denetler.

        Hatalar:
            GecersizDegerHatasi: alt > ust ise.
        """
        if alt is not None and ust is not None and alt > ust:
            raise GecersizDegerHatasi(
                f"{alan_etiketi(alt_alan)} ({alt}), {alan_etiketi(ust_alan)} ({ust}) değerinden büyük olamaz."
            )

    @staticmethod
    def baglanti(alan: str, deger: str | None) -> str | None:
        """
        Kaynak bağlantısının http(s) ile başladığını denetler.

        Arayüzde tıklanabilir bağlantı olarak gösterileceği için "javascript:" gibi
        tehlikeli adresler kabul edilmez.
        """
        if deger is None:
            return None
        if not deger.lower().startswith(IZINLI_URL_ONEKLERI):
            raise GecersizDegerHatasi(f"{alan_etiketi(alan)} http:// veya https:// ile başlamalı.")
        return deger
