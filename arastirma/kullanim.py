"""
Yapay zeka isteklerinin günlük sayımı ve sınırı.

İstek gönderilmeden ÖNCE sayaç artırılır: istek başarısız olsa bile kotadan
düşmüş olabileceği için güvenli taraf seçilir.
"""

from datetime import date

from cekirdek.hatalar import YapayZekaHatasi
from depolama.veritabani import Veritabani

HTTP_COK_ISTEK: int = 429


class GunlukKullanimSayaci:
    """
    Günlük istek sayısını veritabanında tutar.

    Parametreler:
        veritabani: Veritabani nesnesi.
    """

    def __init__(self, veritabani: Veritabani) -> None:
        self._vt = veritabani

    @staticmethod
    def _bugun() -> str:
        return date.today().isoformat()

    def bugun(self) -> int:
        """Bugün yapılan istek sayısı."""
        with self._vt.baglanti() as bag:
            satir = bag.execute("SELECT istek_sayisi FROM yapay_zeka_kullanimi WHERE gun = ?", (self._bugun(),)).fetchone()
        return satir["istek_sayisi"] if satir else 0

    def harca(self, gunluk_sinir: int) -> int:
        """
        Sınır aşılmadıysa sayacı bir artırır.

        Parametreler:
            gunluk_sinir: Günlük en çok istek sayısı.
        Dönüş:
            Artırmadan sonraki günlük sayı.
        Hatalar:
            YapayZekaHatasi: Günlük sınıra ulaşıldıysa (istek gönderilmez).
        """
        # Okuma ve artırma tek SQL komutunda yapılır: önce okuyup sonra yazınca, aynı anda
        # gelen iki istek ikisi de "19" görüp sınırı (20) aşabiliyordu.
        satir = None
        if gunluk_sinir >= 1:
            with self._vt.baglanti() as bag:
                satir = bag.execute(
                    "INSERT INTO yapay_zeka_kullanimi (gun, istek_sayisi) VALUES (?, 1) "
                    "ON CONFLICT(gun) DO UPDATE SET istek_sayisi = istek_sayisi + 1 WHERE istek_sayisi < ? "
                    "RETURNING istek_sayisi",
                    (self._bugun(), gunluk_sinir),
                ).fetchone()
        if satir is None:
            raise YapayZekaHatasi(
                f"Bugünkü öneri sınırına ({gunluk_sinir}) ulaşıldı. Yarın tekrar deneyin veya "
                "Ayarlar sayfasından sınırı değiştirin.",
                HTTP_COK_ISTEK,
            )
        return int(satir["istek_sayisi"])
