"""
Dronelara bağlı şasi kayıtlarının ('sasiler' ve parçalı şasi için 'sasi_parcalari'
tabloları) saklanması.
"""

import sqlite3

from depolama.serilestirme import SasiSerilestirici
from depolama.veritabani import Veritabani
from sasi.modeller import KayitliSasi, ParcaRolu, SasiGeometrisi, SasiOlculeri, SasiParcasi


class SasiKayitDeposu:
    """
    Her drone için en fazla bir şasi kaydı tutar.

    Parametreler:
        veritabani: Bağlantı sağlayan Veritabani nesnesi.
    """

    def __init__(self, veritabani: Veritabani) -> None:
        self._vt = veritabani
        self._serilestirici = SasiSerilestirici()

    def kaydet(
        self,
        drone_kimlik: int,
        saklanan_dosya: str,
        geometri: SasiGeometrisi,
        parcalar: list[SasiParcasi] | None = None,
    ) -> None:
        """
        Drone'un şasisini kaydeder; önceki şasi ve parçaları varsa yerine geçer.

        Yeni dosya yüklendiğinde önceki birim onayı geçersizdir, bu yüzden
        ölçüler (olculer_json) sıfırlanır.

        Parametreler:
            drone_kimlik: Drone kimliği.
            saklanan_dosya: Dosya kopyasının veri klasörüne göre yolu.
            geometri: Okunan geometri (parçalı şaside parçaların özeti).
            parcalar: Parçalı şasinin parçaları; tek dosyada None veya boş.
        """
        with self._vt.baglanti() as bag:
            bag.execute(
                "INSERT OR REPLACE INTO sasiler (drone_kimlik, saklanan_dosya, geometri_json, olculer_json) "
                "VALUES (?, ?, ?, NULL)",
                (drone_kimlik, saklanan_dosya, self._serilestirici.geometriyi_yaz(geometri)),
            )
            # Eski şasinin parçaları aynı işlemde silinir; yarıda kalırsa eski hali korunur.
            bag.execute("DELETE FROM sasi_parcalari WHERE drone_kimlik = ?", (drone_kimlik,))
            self._parcalari_yaz(bag, drone_kimlik, parcalar or [])

    def parcalari_guncelle(self, drone_kimlik: int, geometri: SasiGeometrisi, parcalar: list[SasiParcasi]) -> None:
        """
        Parçaların rol ve adedini ve buna bağlı özet geometriyi kaydeder (ölçüler ayrıca kaydedilir).

        Parametreler:
            drone_kimlik: Drone kimliği.
            geometri: Yenilenmiş özet geometri.
            parcalar: Güncel parçalar.
        """
        with self._vt.baglanti() as bag:
            bag.execute(
                "UPDATE sasiler SET geometri_json = ? WHERE drone_kimlik = ?",
                (self._serilestirici.geometriyi_yaz(geometri), drone_kimlik),
            )
            for p in parcalar:
                bag.execute(
                    "UPDATE sasi_parcalari SET rol = ?, adet = ? WHERE drone_kimlik = ? AND sira = ?",
                    (p.rol.value, p.adet, drone_kimlik, p.sira),
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
        Drone'un şasi kaydını parçalarıyla birlikte döndürür.

        Dönüş:
            KayitliSasi veya şasi yüklenmemişse None.
        """
        with self._vt.baglanti() as bag:
            satir = bag.execute("SELECT * FROM sasiler WHERE drone_kimlik = ?", (drone_kimlik,)).fetchone()
            parca_satirlari = bag.execute(
                "SELECT * FROM sasi_parcalari WHERE drone_kimlik = ? ORDER BY sira", (drone_kimlik,)
            ).fetchall()
        if satir is None:
            return None
        olculer = self._serilestirici.olculeri_oku(satir["olculer_json"]) if satir["olculer_json"] else None
        return KayitliSasi(
            saklanan_dosya=satir["saklanan_dosya"],
            geometri=self._serilestirici.geometriyi_oku(satir["geometri_json"]),
            olculer=olculer,
            parcalar=[
                SasiParcasi(
                    sira=p["sira"],
                    geometri=self._serilestirici.geometriyi_oku(p["geometri_json"]),
                    rol=ParcaRolu(p["rol"]),
                    adet=p["adet"],
                )
                for p in parca_satirlari
            ],
        )

    def _parcalari_yaz(self, bag: sqlite3.Connection, drone_kimlik: int, parcalar: list[SasiParcasi]) -> None:
        """Parça satırlarını açık bağlantı üzerinden ekler."""
        bag.executemany(
            "INSERT INTO sasi_parcalari (drone_kimlik, sira, rol, adet, geometri_json) VALUES (?, ?, ?, ?, ?)",
            [
                (drone_kimlik, p.sira, p.rol.value, p.adet, self._serilestirici.geometriyi_yaz(p.geometri))
                for p in parcalar
            ],
        )
