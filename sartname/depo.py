"""
Şartnamelerin, maddelerinin ve drone–şartname bağlarının saklanması.
"""

import sqlite3

from cekirdek.hatalar import GecersizDegerHatasi, KayitBulunamadiHatasi
from cekirdek.zaman import simdi_iso
from depolama.veritabani import Veritabani
from sartname.modeller import Madde, Sartname

_LISTE_SORGUSU = """
SELECT s.kimlik, s.ad, s.dosya_adi, s.saklanan_dosya, s.yuklenme_zamani, length(s.metin) AS metin_uzunlugu,
       (SELECT count(*) FROM sartname_maddeleri m WHERE m.sartname_kimlik = s.kimlik) AS madde_sayisi,
       (SELECT count(*) FROM sartname_maddeleri m WHERE m.sartname_kimlik = s.kimlik AND m.onaylandi = 1)
           AS onayli_madde_sayisi,
       (SELECT count(*) FROM drone_sartnamesi d WHERE d.sartname_kimlik = s.kimlik) AS kullanan_drone_sayisi
FROM sartnameler s
"""


def _sartname(satir: sqlite3.Row) -> Sartname:
    return Sartname(**{k: satir[k] for k in satir.keys()})


def _madde(satir: sqlite3.Row) -> Madde:
    return Madde(
        kimlik=satir["kimlik"], aciklama=satir["aciklama"], buyukluk=satir["buyukluk"], sinir_turu=satir["sinir_turu"],
        deger=satir["deger"], sinif=satir["sinif"], madde_no=satir["madde_no"], sayfa=satir["sayfa"],
        onaylandi=bool(satir["onaylandi"]),
    )


class SartnameDeposu:
    """
    Şartname kütüphanesi.

    Parametreler:
        veritabani: Veritabani nesnesi.
    """

    def __init__(self, veritabani: Veritabani) -> None:
        self._vt = veritabani

    # ---------- Şartnameler ----------

    def ekle(self, ad: str, dosya_adi: str, saklanan_dosya: str, metin: str) -> Sartname:
        """Yeni şartnameyi kaydeder."""
        ad = ad.strip()
        if not ad:
            raise GecersizDegerHatasi("Şartnameye bir ad verin (ör. yarışmanın adı ve yılı).")
        with self._vt.baglanti() as bag:
            imlec = bag.execute(
                "INSERT INTO sartnameler (ad, dosya_adi, saklanan_dosya, metin, yuklenme_zamani) VALUES (?, ?, ?, ?, ?)",
                (ad, dosya_adi, saklanan_dosya, metin, simdi_iso()),
            )
            kimlik = imlec.lastrowid
        return self.getir(kimlik)

    def getir(self, kimlik: int) -> Sartname:
        """Hatalar: KayitBulunamadiHatasi."""
        with self._vt.baglanti() as bag:
            satir = bag.execute(_LISTE_SORGUSU + " WHERE s.kimlik = ?", (kimlik,)).fetchone()
        if satir is None:
            raise KayitBulunamadiHatasi("Şartname bulunamadı; silinmiş olabilir.")
        return _sartname(satir)

    def listele(self) -> list[Sartname]:
        """Bütün şartnameler, en yeni önce."""
        with self._vt.baglanti() as bag:
            satirlar = bag.execute(_LISTE_SORGUSU + " ORDER BY s.yuklenme_zamani DESC, s.kimlik DESC").fetchall()
        return [_sartname(s) for s in satirlar]

    def metin(self, kimlik: int) -> str:
        """Belgeden çıkarılmış metin."""
        with self._vt.baglanti() as bag:
            satir = bag.execute("SELECT metin FROM sartnameler WHERE kimlik = ?", (kimlik,)).fetchone()
        if satir is None:
            raise KayitBulunamadiHatasi("Şartname bulunamadı; silinmiş olabilir.")
        return satir["metin"]

    def sil(self, kimlik: int) -> Sartname:
        """
        Kullanılmayan şartnameyi maddeleriyle siler.

        Dönüş:
            Silinen şartname (belge dosyasını silmek için).
        Hatalar:
            KayitBulunamadiHatasi; GecersizDegerHatasi: bir drone kullanıyorsa.
        """
        sartname = self.getir(kimlik)
        if sartname.kullanan_drone_sayisi:
            raise GecersizDegerHatasi(
                f"Bu şartnameyi {sartname.kullanan_drone_sayisi} drone kullanıyor. Önce dronelardan kaldırın."
            )
        with self._vt.baglanti() as bag:
            bag.execute("DELETE FROM sartnameler WHERE kimlik = ?", (kimlik,))
        return sartname

    # ---------- Maddeler ----------

    def maddeler(self, sartname_kimlik: int) -> list[Madde]:
        """Şartnamenin maddeleri, sırasıyla."""
        with self._vt.baglanti() as bag:
            satirlar = bag.execute(
                "SELECT * FROM sartname_maddeleri WHERE sartname_kimlik = ? ORDER BY sira, kimlik", (sartname_kimlik,)
            ).fetchall()
        return [_madde(s) for s in satirlar]

    def maddeleri_degistir(self, sartname_kimlik: int, maddeler: list[Madde]) -> list[Madde]:
        """
        Şartnamenin bütün maddelerini verilen listeyle değiştirir (tablo düzenlemesi tek seferde kaydedilir).

        Hatalar:
            KayitBulunamadiHatasi: Şartname yoksa.
        """
        self.getir(sartname_kimlik)
        with self._vt.baglanti() as bag:
            bag.execute("DELETE FROM sartname_maddeleri WHERE sartname_kimlik = ?", (sartname_kimlik,))
            bag.executemany(
                "INSERT INTO sartname_maddeleri (sartname_kimlik, sira, madde_no, sayfa, aciklama, buyukluk, sinir_turu, "
                "deger, sinif, onaylandi) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (sartname_kimlik, sira, m.madde_no, m.sayfa, m.aciklama, m.buyukluk.value, m.sinir_turu.value,
                     m.deger, m.sinif.value, int(m.onaylandi))
                    for sira, m in enumerate(maddeler)
                ],
            )
        return self.maddeler(sartname_kimlik)

    # ---------- Drone bağı ----------

    def drone_sartnamesi(self, drone_kimlik: int) -> Sartname | None:
        """Drone'a bağlı şartname; yoksa None."""
        with self._vt.baglanti() as bag:
            satir = bag.execute(
                "SELECT sartname_kimlik FROM drone_sartnamesi WHERE drone_kimlik = ?", (drone_kimlik,)
            ).fetchone()
        return self.getir(satir["sartname_kimlik"]) if satir else None

    def bagla(self, drone_kimlik: int, sartname_kimlik: int) -> None:
        """Drone'a şartname bağlar (önceki şartnamenin yerine geçer)."""
        self.getir(sartname_kimlik)
        with self._vt.baglanti() as bag:
            bag.execute(
                "INSERT OR REPLACE INTO drone_sartnamesi (drone_kimlik, sartname_kimlik) VALUES (?, ?)",
                (drone_kimlik, sartname_kimlik),
            )

    def bagi_kaldir(self, drone_kimlik: int) -> None:
        """Drone'un şartnamesini kaldırır (şartname kütüphanede kalır)."""
        with self._vt.baglanti() as bag:
            bag.execute("DELETE FROM drone_sartnamesi WHERE drone_kimlik = ?", (drone_kimlik,))
