"""
Dronelara bağlı şasi kayıtlarının ('sasiler' tablosu) saklanması.
"""

from depolama.serilestirme import SasiSerilestirici
from depolama.veritabani import Veritabani
from sasi.modeller import KayitliSasi, SasiGeometrisi, SasiOlculeri


class SasiKayitDeposu:
    """
    Her drone için en fazla bir şasi kaydı tutar.

    Parametreler:
        veritabani: Bağlantı sağlayan Veritabani nesnesi.
    """

    def __init__(self, veritabani: Veritabani) -> None:
        self._vt = veritabani
        self._serilestirici = SasiSerilestirici()

    def kaydet(self, drone_kimlik: int, saklanan_dosya: str, geometri: SasiGeometrisi) -> None:
        """
        Drone'un şasisini kaydeder; önceki şasi varsa yerine geçer.

        Yeni dosya yüklendiğinde önceki birim onayı geçersizdir, bu yüzden
        ölçüler (olculer_json) sıfırlanır.

        Parametreler:
            drone_kimlik: Drone kimliği.
            saklanan_dosya: Dosya kopyasının veri klasörüne göre yolu.
            geometri: Okunan geometri.
        """
        with self._vt.baglanti() as bag:
            bag.execute(
                "INSERT OR REPLACE INTO sasiler (drone_kimlik, saklanan_dosya, geometri_json, olculer_json) "
                "VALUES (?, ?, ?, NULL)",
                (drone_kimlik, saklanan_dosya, self._serilestirici.geometriyi_yaz(geometri)),
            )

    def olculeri_kaydet(self, drone_kimlik: int, olculer: SasiOlculeri) -> None:
        """
        Birim onayından sonraki mm ölçülerini kaydeder.

        Parametreler:
            drone_kimlik: Drone kimliği.
            olculer: Onaylanmış ölçüler.
        """
        with self._vt.baglanti() as bag:
            bag.execute(
                "UPDATE sasiler SET olculer_json = ? WHERE drone_kimlik = ?",
                (self._serilestirici.olculeri_yaz(olculer), drone_kimlik),
            )

    def getir(self, drone_kimlik: int) -> KayitliSasi | None:
        """
        Drone'un şasi kaydını döndürür.

        Dönüş:
            KayitliSasi veya şasi yüklenmemişse None.
        """
        with self._vt.baglanti() as bag:
            satir = bag.execute("SELECT * FROM sasiler WHERE drone_kimlik = ?", (drone_kimlik,)).fetchone()
        if satir is None:
            return None
        olculer = self._serilestirici.olculeri_oku(satir["olculer_json"]) if satir["olculer_json"] else None
        return KayitliSasi(
            saklanan_dosya=satir["saklanan_dosya"],
            geometri=self._serilestirici.geometriyi_oku(satir["geometri_json"]),
            olculer=olculer,
        )
