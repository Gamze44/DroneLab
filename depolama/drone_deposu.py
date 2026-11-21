"""
Drone kayıtlarının veritabanında oluşturulması, okunması, güncellenmesi ve silinmesi.
"""

from datetime import datetime
import sqlite3

from cekirdek.hatalar import KayitBulunamadiHatasi
from depolama.veritabani import Veritabani
from drone.modeller import BaslangicTuru, Drone, DroneTuru

DRONE_SORGUSU = """
SELECT d.*, EXISTS(SELECT 1 FROM sasiler s WHERE s.drone_kimlik = d.kimlik) AS sasi_var
FROM dronelar d
"""


def _simdi() -> str:
    """Şu anki yerel zamanı saniye hassasiyetinde ISO metni olarak döndürür."""
    return datetime.now().isoformat(timespec="seconds")


class DroneDeposu:
    """
    'dronelar' tablosu üzerindeki işlemler.

    Parametreler:
        veritabani: Bağlantı sağlayan Veritabani nesnesi.
    """

    def __init__(self, veritabani: Veritabani) -> None:
        self._vt = veritabani

    @staticmethod
    def _satirdan_drone(satir: sqlite3.Row) -> Drone:
        """Veritabanı satırını Drone nesnesine çevirir."""
        return Drone(
            kimlik=satir["kimlik"],
            ad=satir["ad"],
            baslangic_turu=BaslangicTuru(satir["baslangic_turu"]),
            drone_turu=DroneTuru(satir["drone_turu"]),
            amac=satir["amac"],
            olusturma_zamani=satir["olusturma_zamani"],
            guncelleme_zamani=satir["guncelleme_zamani"],
            sasi_agirlik_g=satir["sasi_agirlik_g"],
            sasi_var=bool(satir["sasi_var"]),
        )

    def olustur(self, ad: str, baslangic_turu: BaslangicTuru, drone_turu: DroneTuru, amac: str) -> Drone:
        """
        Yeni drone kaydı oluşturur.

        Parametreler:
            ad: Doğrulanmış drone adı.
            baslangic_turu: Sıfırdan / elimdeki.
            drone_turu: Drone türü.
            amac: Doğrulanmış kullanım amacı.
        Dönüş:
            Oluşturulan Drone.
        """
        zaman = _simdi()
        with self._vt.baglanti() as bag:
            imlec = bag.execute(
                "INSERT INTO dronelar (ad, baslangic_turu, drone_turu, amac, olusturma_zamani, guncelleme_zamani) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (ad, baslangic_turu.value, drone_turu.value, amac, zaman, zaman),
            )
            kimlik = int(imlec.lastrowid)
        return self.getir(kimlik)

    def listele(self) -> list[Drone]:
        """
        Tüm droneları son değiştirilen en üstte olacak şekilde döndürür.

        Dönüş:
            Drone listesi.
        """
        with self._vt.baglanti() as bag:
            satirlar = bag.execute(DRONE_SORGUSU + " ORDER BY d.guncelleme_zamani DESC, d.kimlik DESC").fetchall()
        return [self._satirdan_drone(s) for s in satirlar]

    def getir(self, kimlik: int) -> Drone:
        """
        Kimliği verilen drone'u döndürür.

        Hatalar:
            KayitBulunamadiHatasi: Drone yoksa.
        """
        with self._vt.baglanti() as bag:
            satir = bag.execute(DRONE_SORGUSU + " WHERE d.kimlik = ?", (kimlik,)).fetchone()
        if satir is None:
            raise KayitBulunamadiHatasi("Drone bulunamadı. Silinmiş olabilir.")
        return self._satirdan_drone(satir)

    def sil(self, kimlik: int) -> None:
        """
        Drone'u ve (CASCADE ile) şasi kaydını siler.

        Hatalar:
            KayitBulunamadiHatasi: Drone yoksa.
        """
        with self._vt.baglanti() as bag:
            imlec = bag.execute("DELETE FROM dronelar WHERE kimlik = ?", (kimlik,))
        if imlec.rowcount == 0:
            raise KayitBulunamadiHatasi("Silinecek drone bulunamadı.")

    def sasi_agirligini_ayarla(self, kimlik: int, agirlik_g: float | None) -> Drone:
        """
        Elle girilen şasi ağırlığını kaydeder (None verilirse siler).

        Parametreler:
            kimlik: Drone kimliği.
            agirlik_g: Ağırlık, gram veya None.
        Dönüş:
            Güncellenmiş Drone.
        """
        with self._vt.baglanti() as bag:
            bag.execute(
                "UPDATE dronelar SET sasi_agirlik_g = ?, guncelleme_zamani = ? WHERE kimlik = ?",
                (agirlik_g, _simdi(), kimlik),
            )
        return self.getir(kimlik)

    def guncellendi_olarak_isaretle(self, kimlik: int) -> None:
        """
        Son değişiklik zamanını şimdiye çeker.

        Şasi gibi başka tablolarda değişiklik olduğunda kayıtlı dronelar
        listesinde doğru sırada görünmesi için çağrılır.
        """
        with self._vt.baglanti() as bag:
            bag.execute("UPDATE dronelar SET guncelleme_zamani = ? WHERE kimlik = ?", (_simdi(), kimlik))
