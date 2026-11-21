"""
Drone–parça bağlarının ('drone_parcalari' tablosu) saklanması.

Her bağ bir drone'da kullanılan bir katalog parçasını, adedini ve durumunu
(elimde / önerilen / planlanan) tutar. Bir parça aynı drone'a iki kez
bağlanmaz; adet değiştirilir.
"""

import sqlite3

from cekirdek.hatalar import GecersizDegerHatasi, KayitBulunamadiHatasi, KayitZatenVarHatasi
from cekirdek.zaman import simdi_iso
from depolama.veritabani import Veritabani
from elektronik.parcalar.drone_parcasi import DroneParcasi
from elektronik.parcalar.turler import ParcaDurumu


class DroneParcaDeposu:
    """
    'drone_parcalari' tablosu üzerindeki işlemler.

    Parametreler:
        veritabani: Bağlantı sağlayan Veritabani nesnesi.
    """

    def __init__(self, veritabani: Veritabani) -> None:
        self._vt = veritabani

    @staticmethod
    def _satirdan_bag(satir: sqlite3.Row) -> DroneParcasi:
        """Veritabanı satırını DroneParcasi nesnesine çevirir."""
        return DroneParcasi(
            kimlik=satir["kimlik"],
            drone_kimlik=satir["drone_kimlik"],
            parca_kimlik=satir["parca_kimlik"],
            adet=satir["adet"],
            durum=ParcaDurumu(satir["durum"]),
            eklenme_zamani=satir["eklenme_zamani"],
        )

    def ekle(self, bag: DroneParcasi) -> DroneParcasi:
        """
        Parçayı drone'a bağlar.

        Hatalar:
            GecersizDegerHatasi: Bağın zaten kimliği varsa.
            KayitZatenVarHatasi: Aynı parça bu drone'da zaten varsa (adedi değiştirilmeli).
        """
        if bag.kimlik is not None:
            raise GecersizDegerHatasi("Bu bağ zaten kayıtlı; değiştirmek için güncelleme kullanın.")
        with self._vt.baglanti() as bag_vt:
            mevcut = bag_vt.execute(
                "SELECT kimlik FROM drone_parcalari WHERE drone_kimlik = ? AND parca_kimlik = ?",
                (bag.drone_kimlik, bag.parca_kimlik),
            ).fetchone()
            if mevcut is not None:
                raise KayitZatenVarHatasi(
                    "Bu parça bu drone'da zaten var. Yeniden eklemek yerine adedini değiştirin.", int(mevcut["kimlik"])
                )
            imlec = bag_vt.execute(
                "INSERT INTO drone_parcalari (drone_kimlik, parca_kimlik, adet, durum, eklenme_zamani) "
                "VALUES (?, ?, ?, ?, ?)",
                (bag.drone_kimlik, bag.parca_kimlik, bag.adet, bag.durum.value, simdi_iso()),
            )
            kimlik = int(imlec.lastrowid)
        return self.getir(bag.drone_kimlik, kimlik)

    def listele(self, drone_kimlik: int) -> list[DroneParcasi]:
        """Drone'un parça bağlarını eklenme sırasıyla döndürür."""
        with self._vt.baglanti() as bag_vt:
            satirlar = bag_vt.execute(
                "SELECT * FROM drone_parcalari WHERE drone_kimlik = ? ORDER BY kimlik", (drone_kimlik,)
            ).fetchall()
        return [self._satirdan_bag(s) for s in satirlar]

    def getir(self, drone_kimlik: int, kimlik: int) -> DroneParcasi:
        """
        Drone'a ait bağı döndürür. Başka drone'un bağı istenirse bulunamadı sayılır.

        Hatalar:
            KayitBulunamadiHatasi: Bağ yoksa veya başka drone'a aitse.
        """
        with self._vt.baglanti() as bag_vt:
            satir = bag_vt.execute(
                "SELECT * FROM drone_parcalari WHERE kimlik = ? AND drone_kimlik = ?", (kimlik, drone_kimlik)
            ).fetchone()
        if satir is None:
            raise KayitBulunamadiHatasi("Bu parça drone'da bulunamadı. Sayfayı yenileyin.")
        return self._satirdan_bag(satir)

    def guncelle(
        self, drone_kimlik: int, kimlik: int, adet: int | None = None, durum: ParcaDurumu | str | None = None
    ) -> DroneParcasi:
        """
        Bağın adedini ve/veya durumunu değiştirir; verilmeyen alan aynı kalır.

        Hatalar:
            KayitBulunamadiHatasi: Bağ yoksa.
            GecersizDegerHatasi: Adet veya durum geçersizse.
        """
        mevcut = self.getir(drone_kimlik, kimlik)
        # Doğrulama DroneParcasi'nda tek yerde yapılsın diye yeni nesne üzerinden geçilir.
        yeni = DroneParcasi(
            drone_kimlik=drone_kimlik,
            parca_kimlik=mevcut.parca_kimlik,
            adet=mevcut.adet if adet is None else adet,
            durum=mevcut.durum if durum is None else durum,
        )
        with self._vt.baglanti() as bag_vt:
            bag_vt.execute(
                "UPDATE drone_parcalari SET adet = ?, durum = ? WHERE kimlik = ?", (yeni.adet, yeni.durum.value, kimlik)
            )
        return self.getir(drone_kimlik, kimlik)

    def sil(self, drone_kimlik: int, kimlik: int) -> None:
        """
        Bağı siler (parça katalogda kalır).

        Hatalar:
            KayitBulunamadiHatasi: Bağ yoksa.
        """
        with self._vt.baglanti() as bag_vt:
            imlec = bag_vt.execute(
                "DELETE FROM drone_parcalari WHERE kimlik = ? AND drone_kimlik = ?", (kimlik, drone_kimlik)
            )
        if imlec.rowcount == 0:
            raise KayitBulunamadiHatasi("Kaldırılacak parça drone'da bulunamadı. Sayfayı yenileyin.")
