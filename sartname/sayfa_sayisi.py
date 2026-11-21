"""
Şartname belgesinin sayfa sayısını bulur ve sayfa sınırını denetler.

- PDF: sayfa sayısı kesindir (belgedeki sayfa nesneleri sayılır).
- Word (.docx): sabit sayfa yoktur; sayfalama açılırken yazı tipi ve kenar boşluğuna göre
  hesaplanır. Word, kaydederken bulduğu sayfa sayısını docProps/app.xml içine ("Pages")
  yazar; bu değer varsa o kullanılır. Yoksa sayfa sayısı kelime sayısından tahmin edilir
  ve sonuç "tahmini" diye gösterilir (kullanıcı kararı).

Not: Word dışındaki araçlarla üretilen bazı .docx dosyalarında "Pages" değeri şablondan
kalmış ve güncellenmemiş olabilir; Word ve LibreOffice kaydederken günceller.
"""

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Final
import xml.etree.ElementTree as ET
import zipfile

from cekirdek.ayarlar import EN_FAZLA_SARTNAME_SAYFASI, SAYFA_BASINA_KELIME
from cekirdek.hatalar import GecersizDegerHatasi
from sartname.metin_cikarici import PDF_UZANTISI

WORD_OZELLIK_DOSYASI: Final[str] = "docProps/app.xml"
WORD_SAYFA_ETIKETI: Final[str] = "{http://schemas.openxmlformats.org/officeDocument/2006/extended-properties}Pages"


@dataclass(frozen=True)
class SayfaSayisi:
    """
    Alanlar:
        sayi: Sayfa sayısı.
        tahmini: Kelime sayısından tahmin edildiyse True.
    """

    sayi: int
    tahmini: bool = False

    def metin(self) -> str:
        """Kullanıcıya gösterilecek biçim (ör. "73 sayfa" ya da "≈ 52 sayfa (tahmini)")."""
        return f"≈ {self.sayi} sayfa (tahmini, kelime sayısından)" if self.tahmini else f"{self.sayi} sayfa"


class SayfaSayaci:
    """
    Belgenin sayfa sayısını bulur.

    Parametreler:
        sayfa_basina_kelime: Word'de sayfa bilgisi yoksa tahminde kullanılan oran.
    """

    def __init__(self, sayfa_basina_kelime: int = SAYFA_BASINA_KELIME) -> None:
        self.sayfa_basina_kelime = sayfa_basina_kelime

    def say(self, yol: Path, metin: str) -> SayfaSayisi:
        """
        Parametreler:
            yol: Belge dosyası (uzantısı .pdf veya .docx; daha önce denetlenmiş olmalı).
            metin: Belgeden çıkarılmış metin (Word tahmini için).
        Dönüş:
            SayfaSayisi.
        """
        if yol.suffix.lower() == PDF_UZANTISI:
            return SayfaSayisi(self._pdf_sayfa(yol))
        kayitli = self._word_kayitli_sayfa(yol)
        if kayitli is not None:
            return SayfaSayisi(kayitli)
        kelime = len(metin.split())
        return SayfaSayisi(max(1, math.ceil(kelime / self.sayfa_basina_kelime)), tahmini=True)

    @staticmethod
    def _pdf_sayfa(yol: Path) -> int:
        from pypdf import PdfReader

        okuyucu = PdfReader(str(yol))
        if okuyucu.is_encrypted:
            okuyucu.decrypt("")  # metin çıkarıcı parolalı PDF'i zaten reddetti; burada yalnızca kopyalama korumalı olanlar gelir
        return len(okuyucu.pages)

    @staticmethod
    def _word_kayitli_sayfa(yol: Path) -> int | None:
        """Word'ün kaydettiği sayfa sayısı; yoksa veya okunamazsa None."""
        try:
            with zipfile.ZipFile(yol) as arsiv:
                kok = ET.fromstring(arsiv.read(WORD_OZELLIK_DOSYASI))
        except (KeyError, zipfile.BadZipFile, ET.ParseError, OSError):
            return None
        deger = kok.findtext(WORD_SAYFA_ETIKETI)
        if deger is None or not deger.strip().isdigit() or int(deger) < 1:
            return None
        return int(deger)


class SayfaSiniriDenetleyici:
    """
    Belgenin sayfa sınırını aşıp aşmadığını denetler.

    Parametreler:
        en_fazla: En çok sayfa sayısı.
    """

    def __init__(self, en_fazla: int = EN_FAZLA_SARTNAME_SAYFASI) -> None:
        self.en_fazla = en_fazla
        self._sayac = SayfaSayaci()

    def denetle(self, yol: Path, metin: str) -> SayfaSayisi:
        """
        Dönüş:
            Bulunan sayfa sayısı.
        Hatalar:
            GecersizDegerHatasi: Sınır aşılıyorsa.
        """
        sayfa = self._sayac.say(yol, metin)
        if sayfa.sayi > self.en_fazla:
            raise GecersizDegerHatasi(
                f"Şartname en çok {self.en_fazla} sayfa olabilir; bu belge {sayfa.metin()}. "
                "Yalnızca teknik kuralların bulunduğu bölümü ayrı bir belge olarak kaydedip yükleyin."
            )
        return sayfa
