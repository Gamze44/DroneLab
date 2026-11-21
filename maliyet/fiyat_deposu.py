"""
Fiyatların saklanması: katalog parçalarının birim fiyatları ve dronelara özel şasi fiyatı.
"""

from dataclasses import dataclass

from cekirdek.zaman import simdi_iso
from depolama.veritabani import Veritabani
from maliyet.para import Fiyat


class ParcaFiyatDeposu:
    """
    Katalog parçalarının 1 adet fiyatını tutar ('parca_fiyatlari' tablosu).

    Parametreler:
        veritabani: Veritabani nesnesi.
    """

    def __init__(self, veritabani: Veritabani) -> None:
        self._vt = veritabani

    def kaydet(self, parca_kimlik: int, fiyat: Fiyat | None) -> None:
        """Parçanın fiyatını yazar; None verilirse fiyatı siler."""
        with self._vt.baglanti() as bag:
            if fiyat is None:
                bag.execute("DELETE FROM parca_fiyatlari WHERE parca_kimlik = ?", (parca_kimlik,))
            else:
                bag.execute(
                    "INSERT OR REPLACE INTO parca_fiyatlari (parca_kimlik, tutar, para_birimi, guncelleme_zamani) "
                    "VALUES (?, ?, ?, ?)",
                    (parca_kimlik, fiyat.tutar, fiyat.para_birimi, simdi_iso()),
                )

    def getir_hepsi(self, parca_kimlikleri: list[int]) -> dict[int, Fiyat]:
        """Verilen parçaların fiyatları: kimlik → Fiyat (fiyatı olmayanlar yer almaz)."""
        if not parca_kimlikleri:
            return {}
        yer_tutucular = ", ".join("?" for _ in parca_kimlikleri)
        with self._vt.baglanti() as bag:
            satirlar = bag.execute(
                f"SELECT parca_kimlik, tutar, para_birimi FROM parca_fiyatlari WHERE parca_kimlik IN ({yer_tutucular})",
                parca_kimlikleri,
            ).fetchall()
        return {s["parca_kimlik"]: Fiyat(s["tutar"], s["para_birimi"]) for s in satirlar}


@dataclass
class SasiMaliyeti:
    """
    Alanlar:
        fiyat: Şasi fiyatı; girilmediyse None.
        elimde: Şasi zaten elde mi (alınacaklar toplamına katılmaz).
    """

    fiyat: Fiyat | None = None
    elimde: bool = False


class SasiFiyatDeposu:
    """
    Dronelara özel şasi fiyatını tutar ('drone_maliyetleri' tablosu).

    Parametreler:
        veritabani: Veritabani nesnesi.
    """

    def __init__(self, veritabani: Veritabani) -> None:
        self._vt = veritabani

    def getir(self, drone_kimlik: int) -> SasiMaliyeti:
        """Drone'un şasi maliyeti; kayıt yoksa boş SasiMaliyeti."""
        with self._vt.baglanti() as bag:
            s = bag.execute("SELECT * FROM drone_maliyetleri WHERE drone_kimlik = ?", (drone_kimlik,)).fetchone()
        if s is None:
            return SasiMaliyeti()
        fiyat = Fiyat(s["sasi_tutari"], s["sasi_para_birimi"]) if s["sasi_tutari"] is not None else None
        return SasiMaliyeti(fiyat=fiyat, elimde=bool(s["sasi_elimde"]))

    def kaydet(self, drone_kimlik: int, maliyet: SasiMaliyeti) -> None:
        """Drone'un şasi maliyetini yazar."""
        f = maliyet.fiyat
        with self._vt.baglanti() as bag:
            bag.execute(
                "INSERT OR REPLACE INTO drone_maliyetleri (drone_kimlik, sasi_tutari, sasi_para_birimi, sasi_elimde) "
                "VALUES (?, ?, ?, ?)",
                (drone_kimlik, f.tutar if f else None, f.para_birimi if f else None, int(maliyet.elimde)),
            )
