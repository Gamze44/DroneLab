"""
Parçaların teknik değerlerinin JSON'a çevrilmesi ve geri okunması.

Ortak alanlar (üretici, model, ağırlık…) veritabanında ayrı sütunlardadır;
türe özel teknik alanlar tek bir JSON sütununda durur. Bu sınıf ikisi
arasındaki dönüşümü yapar.
"""

from dataclasses import MISSING, asdict, fields
from enum import Enum
import json
from typing import Any, Final

from cekirdek.hatalar import GecersizDegerHatasi
from elektronik.parcalar.cekirdek_parcalar import ItkiNoktasi, Motor
from elektronik.parcalar.kayit import parca_sinifi
from elektronik.parcalar.parca import Parca
from elektronik.parcalar.turler import ParcaTuru

ITKI_TABLOSU_ALANI: Final[str] = "itki_tablosu"
EKSIK_PARCA_BILGISI_MESAJI: Final[str] = (
    "Parça bilgileri eksik veya hatalı. Üretici, model ve (Diğer türünde) alt tür zorunludur."
)
HATALI_ITKI_TABLOSU_MESAJI: Final[str] = (
    "İtki tablosu hatalı: her satırda gerilim, gaz ve itki olmalı; tanınmayan sütun bulunmamalı."
)


def _eksik_zorunlu_alanlar(sinif: type, degerler: dict[str, Any]) -> list[str]:
    """
    Dataclass'ın varsayılanı olmayan ve verilmemiş alanlarını döndürür.

    Parametreler:
        sinif: Dataclass sınıfı.
        degerler: Verilen alanlar.
    Dönüş:
        Eksik alan adları.
    """
    return [
        f.name for f in fields(sinif)
        if f.init and f.default is MISSING and f.default_factory is MISSING and f.name not in degerler
    ]


def _itki_noktalari(ham: Any) -> list[ItkiNoktasi]:
    """
    İtki tablosu satırlarını ItkiNoktasi nesnelerine çevirir.

    Hatalar:
        GecersizDegerHatasi: Tablo liste değilse, satır sözlük değilse, tanınmayan sütun
            varsa veya zorunlu sütun eksikse.
    """
    bilinen = {f.name for f in fields(ItkiNoktasi)}
    if not isinstance(ham, list):
        raise GecersizDegerHatasi(HATALI_ITKI_TABLOSU_MESAJI)
    noktalar = []
    for satir in ham:
        if not isinstance(satir, dict) or set(satir) - bilinen or _eksik_zorunlu_alanlar(ItkiNoktasi, satir):
            raise GecersizDegerHatasi(HATALI_ITKI_TABLOSU_MESAJI)
        noktalar.append(ItkiNoktasi(**satir))
    return noktalar


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
            elif ad == ITKI_TABLOSU_ALANI and deger is not None:
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
        # Eksik zorunlu alan önceden denetlenir: her TypeError'ı "eksik bilgi" saymak,
        # programdaki bir hatayı kullanıcıya veri girişi hatası gibi gösterirdi.
        if _eksik_zorunlu_alanlar(sinif, {**ortak, **teknik}):
            raise GecersizDegerHatasi(EKSIK_PARCA_BILGISI_MESAJI)
        if sinif is Motor and teknik.get(ITKI_TABLOSU_ALANI):
            teknik[ITKI_TABLOSU_ALANI] = _itki_noktalari(teknik[ITKI_TABLOSU_ALANI])
        return sinif(**ortak, **teknik)

    @staticmethod
    def teknik_sozluk(parca: Parca) -> dict[str, Any]:
        """Teknik değerleri JSON'a uygun sözlük olarak döndürür (arayüze göndermek için)."""
        return json.loads(ParcaSerilestirici.teknik_json(parca))
