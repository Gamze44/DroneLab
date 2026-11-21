"""
Zip tabanlı dosyaların (Word .docx, 3MF) açılmadan önce denetimi.

Bu dosyalar aslında zip arşividir. Kötü amaçlı bir arşiv 100 KB görünüp açılınca
gigabaytlarca veri üretebilir ("zip bombası"). python-docx ve trimesh arşiv üyelerini
belleğe tümüyle açtığı için böyle bir dosya programı dondurabilir veya belleği bitirebilir.

Denetim arşivi açmaz; yalnızca zip'in içindekiler listesindeki (central directory)
boyutlara bakar. Python'un zipfile modülü bir üyeyi açarken listedeki boyuttan fazlasını
üretmez (fazlası CRC hatası verir); bu yüzden listedeki boyutlara güvenmek yeterlidir.
"""

from pathlib import Path
from typing import Final
import zipfile

from cekirdek.ayarlar import (
    EN_BUYUK_ACIK_ARSIV_MB,
    EN_BUYUK_SIKISTIRMA_ORANI,
    EN_FAZLA_ARSIV_UYESI,
    ORAN_DENETIM_ESIGI_MB,
)
from cekirdek.hatalar import DosyaOkumaHatasi

BAYT_BIR_MB: Final[int] = 1024 * 1024
BOZUK_ARSIV_MESAJI: Final[str] = (
    "Dosya açılamadı; bozuk veya beklenen biçimde değil. Dosyayı programında yeniden kaydedip tekrar deneyin."
)
SUPHELI_ARSIV_MESAJI: Final[str] = (
    "Dosya açıldığında olağan dışı büyüyor ({neden}). Bozuk veya kötü amaçlı bir dosya olabilir; "
    "dosyayı programında yeniden kaydedip tekrar deneyin."
)


class ArsivDenetleyici:
    """
    Zip arşivinin açılmış boyutunu, sıkıştırma oranını ve üye sayısını denetler.

    Parametreler:
        en_buyuk_acik_mb: İçindekilerin açılmış toplam boyutu için sınır (MB).
        en_buyuk_oran: Bir üyenin en çok sıkıştırma oranı.
        oran_esigi_mb: Oranın denetlendiği en küçük üye boyutu (MB).
        en_fazla_uye: Arşivdeki en çok dosya sayısı.
    """

    def __init__(
        self,
        en_buyuk_acik_mb: int = EN_BUYUK_ACIK_ARSIV_MB,
        en_buyuk_oran: int = EN_BUYUK_SIKISTIRMA_ORANI,
        oran_esigi_mb: int = ORAN_DENETIM_ESIGI_MB,
        en_fazla_uye: int = EN_FAZLA_ARSIV_UYESI,
    ) -> None:
        self.en_buyuk_acik_mb = en_buyuk_acik_mb
        self.en_buyuk_oran = en_buyuk_oran
        self.oran_esigi_mb = oran_esigi_mb
        self.en_fazla_uye = en_fazla_uye

    def denetle(self, yol: Path) -> None:
        """
        Parametreler:
            yol: Zip tabanlı dosya.
        Hatalar:
            DosyaOkumaHatasi: Dosya geçerli bir zip değilse veya sınırlardan biri aşılıyorsa.
        """
        try:
            with zipfile.ZipFile(yol) as arsiv:
                uyeler = arsiv.infolist()
        except (zipfile.BadZipFile, OSError, ValueError) as hata:
            raise DosyaOkumaHatasi(BOZUK_ARSIV_MESAJI) from hata

        if len(uyeler) > self.en_fazla_uye:
            raise DosyaOkumaHatasi(
                SUPHELI_ARSIV_MESAJI.format(neden=f"{len(uyeler)} iç dosya var, sınır {self.en_fazla_uye}")
            )
        toplam = sum(u.file_size for u in uyeler)
        if toplam > self.en_buyuk_acik_mb * BAYT_BIR_MB:
            raise DosyaOkumaHatasi(
                SUPHELI_ARSIV_MESAJI.format(
                    neden=f"açılmış hali {toplam // BAYT_BIR_MB} MB, sınır {self.en_buyuk_acik_mb} MB"
                )
            )
        esik = self.oran_esigi_mb * BAYT_BIR_MB
        for uye in uyeler:
            if uye.file_size <= esik:
                continue
            # Sıkışık boyutu 0 olan büyük bir üye ancak sahte bir arşivde olur.
            oran = uye.file_size / max(uye.compress_size, 1)
            if oran > self.en_buyuk_oran:
                raise DosyaOkumaHatasi(
                    SUPHELI_ARSIV_MESAJI.format(neden=f"bir iç dosya {oran:.0f} kat sıkıştırılmış, sınır {self.en_buyuk_oran}")
                )
