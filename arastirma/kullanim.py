"""
Yapay zeka isteklerinin günlük sayımı ve sınırı.

İstek gönderilmeden ÖNCE sayaç artırılır: istek başarısız olsa bile kotadan
düşmüş olabileceği için güvenli taraf seçilir.
"""

from http import HTTPStatus

from cekirdek.hatalar import YapayZekaHatasi
from cekirdek.zaman import bugun_iso
from depolama.veritabani import Veritabani


class GunlukKullanimSayaci:
    """
    Günlük istek sayısını veritabanında tutar.

    Parametreler:
        veritabani: Veritabani nesnesi.
    """

    def __init__(self, veritabani: Veritabani) -> None:
        self._vt = veritabani

    def bugun(self) -> int:
        """Bugün yapılan istek sayısı."""
        with self._vt.baglanti() as bag:
            satir = bag.execute("SELECT istek_sayisi FROM yapay_zeka_kullanimi WHERE gun = ?", (bugun_iso(),)).fetchone()
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
                    (bugun_iso(), gunluk_sinir),
                ).fetchone()
        if satir is None:
            raise YapayZekaHatasi(self.sinir_mesaji(gunluk_sinir), HTTPStatus.TOO_MANY_REQUESTS)
        return int(satir["istek_sayisi"])

    @staticmethod
    def sinir_mesaji(gunluk_sinir: int) -> str:
        """Günlük sınır dolduğunda kullanıcıya gösterilecek mesaj."""
        return (
            f"Bugünkü yapay zeka istek sınırına ({gunluk_sinir}) ulaşıldı. Yarın tekrar deneyin veya "
            "Ayarlar sayfasından sınırı değiştirin."
        )
