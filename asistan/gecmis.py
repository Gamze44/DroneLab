"""
Asistan sohbet geçmişinin saklanması (veritabanı şema sürümü 7).

Sohbet drone'a bağlıdır ve drone silinince silinir; drone_kimlik None ise ana sayfa ve
ayarlar ekranının "genel sohbet"idir. Mesajlara API anahtarı hiçbir zaman yazılmaz
(yalnızca kullanıcının yazdığı metin ve asistanın yanıtı saklanır).
"""

from dataclasses import dataclass
from enum import Enum
import sqlite3

from cekirdek.zaman import simdi_iso
from depolama.veritabani import Veritabani


class MesajRolu(str, Enum):
    """Mesajı kimin yazdığı. Değerler veritabanında saklanır; değiştirilmemeli."""

    KULLANICI = "kullanici"
    ASISTAN = "asistan"


@dataclass(frozen=True)
class SohbetMesaji:
    """
    Alanlar:
        kimlik: Mesaj numarası.
        drone_kimlik: Bağlı drone; genel sohbette None.
        rol: Kullanıcı veya asistan.
        metin: Mesaj metni.
        model: Asistan yanıtını veren model (kullanıcı mesajında None).
        zaman: ISO zaman.
    """

    kimlik: int
    drone_kimlik: int | None
    rol: MesajRolu
    metin: str
    model: str | None
    zaman: str


def _mesaj(satir: sqlite3.Row) -> SohbetMesaji:
    return SohbetMesaji(
        kimlik=int(satir["kimlik"]), drone_kimlik=satir["drone_kimlik"], rol=MesajRolu(satir["rol"]),
        metin=satir["metin"], model=satir["model"], zaman=satir["zaman"],
    )


class SohbetGecmisi:
    """
    Sohbet mesajlarını ekler, listeler ve siler.

    Parametreler:
        veritabani: Ortak Veritabani.
    """

    def __init__(self, veritabani: Veritabani) -> None:
        self._vt = veritabani

    def ekle(self, drone_kimlik: int | None, rol: MesajRolu, metin: str, model: str | None = None) -> SohbetMesaji:
        """
        Mesajı kaydeder.

        Parametreler:
            drone_kimlik: Bağlı drone; genel sohbette None.
            rol: Kullanıcı veya asistan.
            metin: Mesaj metni.
            model: Asistan yanıtını veren model.
        Dönüş:
            Kaydedilen mesaj.
        """
        with self._vt.baglanti() as bag:
            imlec = bag.execute(
                "INSERT INTO asistan_mesajlari (drone_kimlik, rol, metin, model, zaman) VALUES (?, ?, ?, ?, ?)",
                (drone_kimlik, rol.value, metin, model, simdi_iso()),
            )
            satir = bag.execute("SELECT * FROM asistan_mesajlari WHERE kimlik = ?", (imlec.lastrowid,)).fetchone()
        return _mesaj(satir)

    def listele(self, drone_kimlik: int | None) -> list[SohbetMesaji]:
        """Sohbetin bütün mesajları, eskiden yeniye."""
        with self._vt.baglanti() as bag:
            # "IS" eşitliği NULL ile de çalışır (genel sohbet).
            satirlar = bag.execute(
                "SELECT * FROM asistan_mesajlari WHERE drone_kimlik IS ? ORDER BY kimlik", (drone_kimlik,)
            ).fetchall()
        return [_mesaj(s) for s in satirlar]

    def temizle(self, drone_kimlik: int | None) -> None:
        """Sohbetin bütün mesajlarını siler (bağlı öneriler de silinir)."""
        with self._vt.baglanti() as bag:
            bag.execute("DELETE FROM asistan_mesajlari WHERE drone_kimlik IS ?", (drone_kimlik,))
