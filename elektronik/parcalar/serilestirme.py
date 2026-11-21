"""
Parçaların teknik değerlerinin JSON'a çevrilmesi ve geri okunması.

Ortak alanlar (üretici, model, ağırlık…) veritabanında ayrı sütunlardadır;
türe özel teknik alanlar tek bir JSON sütununda durur. Bu sınıf ikisi
arasındaki dönüşümü yapar.
"""

from dataclasses import asdict
from enum import Enum
import json
from typing import Any

from cekirdek.hatalar import GecersizDegerHatasi
from elektronik.parcalar.cekirdek_parcalar import ItkiNoktasi, Motor
from elektronik.parcalar.kayit import parca_sinifi
from elektronik.parcalar.parca import Parca
from elektronik.parcalar.turler import ParcaTuru


class ParcaSerilestirici:
    """Parça nesnesi <-> (ortak alanlar + teknik JSON) dönüşümü."""

    @staticmethod
    def teknik_json(parca: Parca) -> str:
        """
        Parçanın teknik alanlarını JSON metnine çevirir.

        Enum'lar değerine, itki satırları sözlüğe çevrilir; None değerler de
        yazılır ki "bilinmiyor" bilgisi korunsun.
        """
        sozluk: dict[str, Any] = {}
        for ad, deger in parca.teknik_degerler().items():
            if isinstance(deger, Enum):
                deger = deger.value
            elif ad == "itki_tablosu" and deger is not None:
                deger = [asdict(n) for n in deger]
            sozluk[ad] = deger
        return json.dumps(sozluk, ensure_ascii=False)

    @classmethod
    def parca_olustur(cls, tur: ParcaTuru | str, ortak: dict[str, Any], teknik_json: str) -> Parca:
        """
        Veritabanı satırından parça nesnesini yeniden oluşturur.

        Parametreler:
            tur: Parça türü.
            ortak: Ortak alanlar (uretici, model, agirlik_g, ad, dogrulandi, kaynak_url, notlar, kimlik).
            teknik_json: teknik_json ile üretilmiş metin.
        Dönüş:
            Uygun alt sınıftan Parca.
        """
        return cls.sozlukten_olustur(tur, ortak, json.loads(teknik_json))

    @staticmethod
    def sozlukten_olustur(tur: ParcaTuru | str, ortak: dict[str, Any], teknik: dict[str, Any]) -> Parca:
        """
        Ortak alanlar ve teknik değer sözlüğünden parça oluşturur (veritabanı veya form verisi).

        Parametreler:
            tur: Parça türü (ör. "motor").
            ortak: Ortak alanlar; Parca.ORTAK_ALANLAR dışındakiler yok sayılır.
            teknik: Teknik alanlar; sınıfta olmayanlar yok sayılır (programın eski/yeni
                sürümünden kalan alanlar okumayı bozmasın diye).
        Dönüş:
            Uygun alt sınıftan Parca.
        Hatalar:
            GecersizDegerHatasi: Tür tanınmıyorsa, zorunlu alan eksikse veya bir değer geçersizse.
        """
        try:
            sinif = parca_sinifi(tur)
        except ValueError:
            raise GecersizDegerHatasi(f"Parça türü tanınmıyor: {tur!r}.") from None
        ortak = {ad: deger for ad, deger in ortak.items() if ad in Parca.ORTAK_ALANLAR}
        bilinen = set(sinif.teknik_alan_adlari())
        teknik = {ad: deger for ad, deger in teknik.items() if ad in bilinen}
        try:
            if sinif is Motor and teknik.get("itki_tablosu"):
                teknik["itki_tablosu"] = [ItkiNoktasi(**n) for n in teknik["itki_tablosu"]]
            return sinif(**ortak, **teknik)
        except TypeError as hata:
            # dataclass, eksik zorunlu alanda (ör. DigerParca'da alt tür) TypeError fırlatır.
            raise GecersizDegerHatasi(
                "Parça bilgileri eksik veya hatalı. Üretici, model ve (Diğer türünde) alt tür zorunludur."
            ) from hata

    @staticmethod
    def teknik_sozluk(parca: Parca) -> dict[str, Any]:
        """Teknik değerleri JSON'a uygun sözlük olarak döndürür (arayüze göndermek için)."""
        return json.loads(ParcaSerilestirici.teknik_json(parca))
