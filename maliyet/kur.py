"""
Döviz kurları: TCMB günlük kur dosyası (anahtar gerektirmez).

Kurlar kodla alınır, yapay zekaya sorulmaz. Günde en çok bir kez internetten
alınır ve veritabanında saklanır. Alınamazsa son kayıtlı kur tarihiyle kullanılır;
hiç kur yoksa o para birimindeki fiyatlar toplama katılmaz ve bu ekranda yazılır.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
import logging
from typing import Final
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

from cekirdek.ag import ssl_baglami
from depolama.veritabani import Veritabani
from maliyet.para import PARA_BIRIMLERI, TL

TCMB_ADRESI: Final[str] = "https://www.tcmb.gov.tr/kurlar/today.xml"
ZAMAN_ASIMI_SN: Final[float] = 10.0
EN_BUYUK_YANIT_BAYT: Final[int] = 1_000_000

# DEĞİŞTİRİLEBİLİR: Kullanılan kur türü. "ForexSelling" döviz satış kurudur; yurt dışından
# kartla alışverişte ödenen tutara alış kurundan daha yakındır.
KUR_ALANI: Final[str] = "ForexSelling"

gunluk = logging.getLogger(__name__)


@dataclass(frozen=True)
class Kur:
    """
    Alanlar:
        para_birimi: Kod (ör. "USD").
        tl_karsiligi: 1 biriminin TL karşılığı.
        kur_tarihi: TCMB bülteninin tarihi (GG.AA.YYYY).
        alinma_gunu: Programın kuru aldığı gün (ISO); günde bir kez almak için.
    """

    para_birimi: str
    tl_karsiligi: float
    kur_tarihi: str
    alinma_gunu: str


def tcmb_xml_getir() -> bytes:
    """
    TCMB kur dosyasını indirir.

    Hatalar:
        OSError / urllib.error.URLError: Bağlantı kurulamazsa.
    """
    with urllib.request.urlopen(TCMB_ADRESI, timeout=ZAMAN_ASIMI_SN, context=ssl_baglami()) as yanit:
        return yanit.read(EN_BUYUK_YANIT_BAYT)


class TcmbKurOkuyucu:
    """TCMB XML'inden istenen para birimlerinin kurunu okur."""

    @staticmethod
    def oku(xml: bytes, alinma_gunu: str) -> dict[str, Kur]:
        """
        Parametreler:
            xml: today.xml içeriği.
            alinma_gunu: Bugünün ISO tarihi.
        Dönüş:
            Kod → Kur (PARA_BIRIMLERI'nde olup XML'de bulunanlar).
        Hatalar:
            ValueError / ET.ParseError: Dosya beklenen biçimde değilse.
        """
        kok = ET.fromstring(xml)
        kur_tarihi = kok.get("Tarih") or ""
        kurlar: dict[str, Kur] = {}
        for doviz in kok.iter("Currency"):
            kod = doviz.get("CurrencyCode") or doviz.get("Kod")
            if kod not in PARA_BIRIMLERI or kod == TL:
                continue
            deger, birim = doviz.findtext(KUR_ALANI), doviz.findtext("Unit") or "1"
            if not deger:
                continue
            # Bazı birimler 100 adet için verilir (ör. JPY); 1 birime indirilir.
            tl = float(deger) / float(birim)
            if tl > 0:
                kurlar[kod] = Kur(kod, tl, kur_tarihi, alinma_gunu)
        return kurlar


class KurDeposu:
    """Son alınan kurları veritabanında tutar."""

    def __init__(self, veritabani: Veritabani) -> None:
        self._vt = veritabani

    def hepsi(self) -> dict[str, Kur]:
        with self._vt.baglanti() as bag:
            satirlar = bag.execute("SELECT * FROM kurlar").fetchall()
        return {s["para_birimi"]: Kur(s["para_birimi"], s["tl_karsiligi"], s["kur_tarihi"], s["alinma_gunu"]) for s in satirlar}

    def kaydet(self, kurlar: dict[str, Kur]) -> None:
        with self._vt.baglanti() as bag:
            bag.executemany(
                "INSERT OR REPLACE INTO kurlar (para_birimi, tl_karsiligi, kur_tarihi, alinma_gunu) VALUES (?, ?, ?, ?)",
                [(k.para_birimi, k.tl_karsiligi, k.kur_tarihi, k.alinma_gunu) for k in kurlar.values()],
            )


@dataclass
class KurDurumu:
    """
    Alanlar:
        kurlar: Kullanılabilir kurlar.
        guncel_mi: Bugün alınmış mı (False ise son kayıtlı kur kullanılıyor).
        hata: Kur alınamadıysa Türkçe not.
    """

    kurlar: dict[str, Kur]
    guncel_mi: bool
    hata: str | None = None


class KurServisi:
    """
    Kurları günde bir kez TCMB'den alır, alamazsa kayıtlı olanları kullanır.

    Parametreler:
        depo: KurDeposu.
        getirici: XML'i indiren fonksiyon; testlerde sahtesi verilir (internete çıkılmaz).
        bugun: Bugünün tarihini veren fonksiyon (testler için).
    """

    def __init__(
        self,
        depo: KurDeposu,
        getirici: Callable[[], bytes] = tcmb_xml_getir,
        bugun: Callable[[], date] = date.today,
    ) -> None:
        self._depo = depo
        self._getirici = getirici
        self._bugun = bugun
        self._okuyucu = TcmbKurOkuyucu()

    def kurlar(self, zorla: bool = False) -> KurDurumu:
        """
        Kullanılacak kurları döndürür.

        Parametreler:
            zorla: True ise bugün alınmış olsa bile yeniden alınır ("Kurları yenile" düğmesi).
        """
        bugun = self._bugun().isoformat()
        kayitli = self._depo.hepsi()
        if not zorla and kayitli and all(k.alinma_gunu == bugun for k in kayitli.values()):
            return KurDurumu(kayitli, guncel_mi=True)
        try:
            yeni = self._okuyucu.oku(self._getirici(), bugun)
            if not yeni:
                raise ValueError("kur dosyasında beklenen para birimleri yok")
        except (OSError, urllib.error.URLError, ValueError, ET.ParseError) as hata:
            gunluk.warning("TCMB kurları alınamadı: %s", hata)
            not_ = "TCMB'den güncel kur alınamadı (internet bağlantısını kontrol edin)."
            if kayitli:
                not_ += " Son kayıtlı kur kullanıldı."
            return KurDurumu(kayitli, guncel_mi=False, hata=not_)
        self._depo.kaydet(yeni)
        return KurDurumu({**kayitli, **yeni}, guncel_mi=True)
