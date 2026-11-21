"""
Şartname belgesinden (PDF veya Word .docx) düz metin çıkarma.

PDF'te her sayfanın başına "[Sayfa N]" işareti konur; böylece madde çıkarımında
maddenin sayfası da bulunabilir. Taranmış (resim) PDF'lerde metin çıkmaz; bu
durumda boş metin döner ve kullanıcı maddeleri elle girer (OCR sonraki sürümde).
"""

from pathlib import Path
from typing import Final

from cekirdek.hatalar import DesteklenmeyenDosyaHatasi, DosyaOkumaHatasi

PDF_UZANTISI: Final[str] = ".pdf"
WORD_UZANTISI: Final[str] = ".docx"
DESTEKLENEN_UZANTILAR: Final[tuple[str, ...]] = (PDF_UZANTISI, WORD_UZANTISI)

# DEĞİŞTİRİLEBİLİR: Saklanacak en uzun metin (karakter); çok büyük belgeler veritabanını şişirmesin.
EN_UZUN_METIN: Final[int] = 1_000_000


class SartnameMetinCikarici:
    """PDF ve .docx belgelerinden metin çıkarır."""

    @staticmethod
    def uzantiyi_denetle(dosya_adi: str) -> str:
        """
        Dönüş:
            Küçük harfli uzantı.
        Hatalar:
            DesteklenmeyenDosyaHatasi: Uzantı .pdf veya .docx değilse.
        """
        uzanti = Path(dosya_adi).suffix.lower()
        if uzanti not in DESTEKLENEN_UZANTILAR:
            rehber = []
            if uzanti == ".doc":
                rehber = ["Word'de dosyayı açın → Farklı Kaydet → 'Word Belgesi (*.docx)' seçin."]
            raise DesteklenmeyenDosyaHatasi(
                f"'{uzanti or dosya_adi}' türü okunamıyor. Şartnameyi PDF veya Word (.docx) olarak yükleyin.", rehber
            )
        return uzanti

    def cikar(self, yol: Path) -> str:
        """
        Parametreler:
            yol: Belge dosyası.
        Dönüş:
            Metin (taranmış belgede boş olabilir).
        Hatalar:
            DosyaOkumaHatasi: Belge bozuksa veya şifreliyse.
        """
        uzanti = self.uzantiyi_denetle(yol.name)
        try:
            metin = self._pdf(yol) if uzanti == PDF_UZANTISI else self._word(yol)
        except DosyaOkumaHatasi:
            raise
        except Exception as hata:  # kütüphaneler bozuk dosyada çok farklı hatalar fırlatıyor
            raise DosyaOkumaHatasi(
                "Belge okunamadı; dosya bozuk veya beklenen biçimde değil. Belgeyi yeniden kaydedip tekrar deneyin."
            ) from hata
        return metin.strip()[:EN_UZUN_METIN]

    @staticmethod
    def _pdf(yol: Path) -> str:
        from pypdf import PdfReader

        okuyucu = PdfReader(str(yol))
        if okuyucu.is_encrypted:
            try:
                okuyucu.decrypt("")  # yalnızca kopyalama korumalı (parolasız) PDF'ler açılabilir
            except Exception:
                raise DosyaOkumaHatasi("PDF parola korumalı. Parolasız bir kopyasını yükleyin.") from None
        parcalar = []
        for sira, sayfa in enumerate(okuyucu.pages, start=1):
            metin = (sayfa.extract_text() or "").strip()
            if metin:
                parcalar.append(f"[Sayfa {sira}]\n{metin}")
        return "\n\n".join(parcalar)

    @staticmethod
    def _word(yol: Path) -> str:
        import docx

        belge = docx.Document(str(yol))
        satirlar = [p.text for p in belge.paragraphs if p.text.strip()]
        # Şartnamelerde sınırlar çoğu zaman tablolarda olur; tablo hücreleri de alınır.
        for tablo in belge.tables:
            for satir in tablo.rows:
                hucreler = [h.text.strip() for h in satir.cells if h.text.strip()]
                if hucreler:
                    satirlar.append(" | ".join(dict.fromkeys(hucreler)))
        return "\n".join(satirlar)
