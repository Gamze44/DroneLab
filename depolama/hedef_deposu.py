"""
Drone hedeflerinin ('drone_hedefleri' tablosu) saklanması.
"""

from depolama.veritabani import Veritabani
from drone.hedefler import DroneHedefleri


class HedefDeposu:
    """
    Her drone için en fazla bir hedef kaydı tutar.

    Parametreler:
        veritabani: Veritabani nesnesi.
    """

    def __init__(self, veritabani: Veritabani) -> None:
        self._vt = veritabani

    def getir(self, drone_kimlik: int) -> DroneHedefleri:
        """Drone'un hedefleri; kayıt yoksa hepsi boş hedefler."""
        with self._vt.baglanti() as bag:
            s = bag.execute("SELECT * FROM drone_hedefleri WHERE drone_kimlik = ?", (drone_kimlik,)).fetchone()
        if s is None:
            return DroneHedefleri()
        return DroneHedefleri(
            ucus_suresi_dk=s["ucus_suresi_dk"], yuk_g=s["yuk_g"], butce_tl=s["butce_tl"], itki_agirlik=s["itki_agirlik"]
        )

    def kaydet(self, drone_kimlik: int, hedefler: DroneHedefleri) -> None:
        """Drone'un hedeflerini yazar (öncekinin yerine geçer)."""
        with self._vt.baglanti() as bag:
            bag.execute(
                "INSERT OR REPLACE INTO drone_hedefleri (drone_kimlik, ucus_suresi_dk, yuk_g, butce_tl, itki_agirlik) "
                "VALUES (?, ?, ?, ?, ?)",
                (drone_kimlik, hedefler.ucus_suresi_dk, hedefler.yuk_g, hedefler.butce_tl, hedefler.itki_agirlik),
            )
