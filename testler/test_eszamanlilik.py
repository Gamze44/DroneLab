"""
Eşzamanlılık ve verimlilik testleri: aynı anda gelen yazma istekleri, günlük yapay
zeka sınırının yarış durumu, elektronik özetindeki tek sorgu ve TCMB'nin günlük denemesi.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient
import pytest

from arastirma.kullanim import GunlukKullanimSayaci
from arayuz.sunucu import sunucu_olustur
from cekirdek.hatalar import YapayZekaHatasi
from depolama.veritabani import GUNLUK_KIPI, Veritabani
from elektronik.katalog import ParcaKatalogu
from elektronik.servis import ElektronikServisi
from maliyet.kur import KurDeposu, KurServisi

YENI_DRONE = {"ad": "Eş", "baslangic_turu": "sifirdan", "drone_turu": "quadcopter", "amac": "FPV yarış"}
ES_ZAMANLI = 30
ISTEK_SAYISI = 300


def test_veritabani_wal_kipinde(tmp_path: Path) -> None:
    vt = Veritabani(tmp_path / "vt.sqlite3")
    with vt.baglanti() as bag:
        assert bag.execute("PRAGMA journal_mode").fetchone()[0].upper() == GUNLUK_KIPI


def test_eszamanli_yazmada_kilit_hatasi_yok(tmp_path: Path) -> None:
    istemci = TestClient(sunucu_olustur(tmp_path / "veri", kur_getirici=lambda: b""), raise_server_exceptions=False)
    kimlik = istemci.post("/api/dronelar", json=YENI_DRONE).json()["kimlik"]

    def yaz(i: int) -> int:
        if i % 3 == 0:
            return istemci.post("/api/dronelar", json={**YENI_DRONE, "ad": f"D{i}"}).status_code
        if i % 3 == 1:
            parca = {"tur": "pervane", "uretici": "P", "model": f"S{i}"}
            return istemci.post(f"/api/dronelar/{kimlik}/parcalar", json={"parca": parca, "adet": 4}).status_code
        return istemci.put(f"/api/dronelar/{kimlik}/hedefler", json={"yuk_g": i}).status_code

    with ThreadPoolExecutor(ES_ZAMANLI) as havuz:
        kodlar = list(havuz.map(yaz, range(ISTEK_SAYISI)))
    assert kodlar.count(200) == ISTEK_SAYISI, {k: kodlar.count(k) for k in set(kodlar)}
    ozet = istemci.get(f"/api/dronelar/{kimlik}/elektronik").json()
    assert len(ozet["kalemler"]) == ISTEK_SAYISI // 3


def test_gunluk_sinir_eszamanli_isteklerde_asilmaz(tmp_path: Path) -> None:
    sayac = GunlukKullanimSayaci(Veritabani(tmp_path / "vt.sqlite3"))
    sinir = 20

    def harca(_: int) -> bool:
        try:
            sayac.harca(sinir)
            return True
        except YapayZekaHatasi:
            return False

    with ThreadPoolExecutor(ES_ZAMANLI) as havuz:
        basarili = sum(havuz.map(harca, range(100)))
    assert basarili == sinir
    assert sayac.bugun() == sinir


def test_gunluk_sinir_mesaji_ve_kodu(tmp_path: Path) -> None:
    sayac = GunlukKullanimSayaci(Veritabani(tmp_path / "vt.sqlite3"))
    assert [sayac.harca(2), sayac.harca(2)] == [1, 2]
    with pytest.raises(YapayZekaHatasi, match="sınırına") as hata:
        sayac.harca(2)
    assert hata.value.http_kodu == 429


def test_elektronik_ozeti_parcalari_tek_sorguda_ceker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    istemci = TestClient(sunucu_olustur(tmp_path / "veri", kur_getirici=lambda: b""))
    kimlik = istemci.post("/api/dronelar", json=YENI_DRONE).json()["kimlik"]
    for i in range(25):
        parca = {"tur": "pervane", "uretici": "P", "model": f"S{i}"}
        istemci.post(f"/api/dronelar/{kimlik}/parcalar", json={"parca": parca, "adet": 4})

    tekil: list[int] = []
    asil = ParcaKatalogu.getir
    monkeypatch.setattr(ParcaKatalogu, "getir", lambda self, k: tekil.append(k) or asil(self, k))
    ozet = ElektronikServisi(tmp_path / "veri").ozet(kimlik)
    assert len(ozet.kalemler) == 25
    assert tekil == []  # parça başına sorgu yok


def test_katalog_getir_hepsi(tmp_path: Path) -> None:
    istemci = TestClient(sunucu_olustur(tmp_path / "veri", kur_getirici=lambda: b""))
    kimlik = istemci.post("/api/dronelar", json=YENI_DRONE).json()["kimlik"]
    eklenen = [
        istemci.post(f"/api/dronelar/{kimlik}/parcalar", json={"parca": {"tur": "pervane", "uretici": "P", "model": f"S{i}"}})
        .json()["parca_kimlik"]
        for i in range(3)
    ]
    katalog = ParcaKatalogu(Veritabani(tmp_path / "veri" / "dronelar.sqlite3"))
    sonuc = katalog.getir_hepsi([*eklenen, eklenen[0], 999_999])
    assert sorted(sonuc) == sorted(eklenen)
    assert katalog.getir_hepsi([]) == {}


class SahteTcmb:
    """Çağrı sayısını tutar; istenirse bağlantı hatası verir."""

    def __init__(self, hata: bool) -> None:
        self.hata, self.cagri = hata, 0

    def __call__(self) -> bytes:
        self.cagri += 1
        if self.hata:
            raise OSError("bağlantı yok")
        return (
            b'<Tarih_Date Tarih="14.11.2026"><Currency CurrencyCode="USD"><Unit>1</Unit>'
            b"<ForexSelling>40.0</ForexSelling></Currency></Tarih_Date>"
        )


def test_tcmb_alinamazsa_ayni_gun_tekrar_denenmez(tmp_path: Path) -> None:
    sahte = SahteTcmb(hata=True)
    gun = [date(2026, 11, 21)]
    servis = KurServisi(KurDeposu(Veritabani(tmp_path / "vt.sqlite3")), sahte, bugun=lambda: gun[0])
    for _ in range(3):
        durum = servis.kurlar()
        assert not durum.guncel_mi and "alınamadı" in durum.hata
    assert sahte.cagri == 1

    sahte.hata = False
    assert servis.kurlar(zorla=True).guncel_mi  # "Kurları yenile" düğmesi her zaman dener
    assert sahte.cagri == 2

    gun[0] = date(2026, 11, 22)
    sahte.hata = True
    servis.kurlar()
    servis.kurlar()
    assert sahte.cagri == 3  # yeni günde bir kez daha denenir


def test_tcmb_eksik_para_birimi_her_istekte_denetilmez(tmp_path: Path) -> None:
    depo = KurDeposu(Veritabani(tmp_path / "vt.sqlite3"))
    from maliyet.kur import Kur

    depo.kaydet({"EUR": Kur("EUR", 45.0, "10.11.2026", "2026-11-10")})
    sahte = SahteTcmb(hata=False)  # yalnızca USD yayımlıyor
    servis = KurServisi(depo, sahte, bugun=lambda: date(2026, 11, 21))
    servis.kurlar()
    servis.kurlar()
    assert sahte.cagri == 1


def test_eski_veritabani_wal_kipine_gecer(tmp_path: Path) -> None:
    yol = tmp_path / "eski.sqlite3"
    sqlite3.connect(yol).close()  # rollback günlüklü boş dosya
    Veritabani(yol)
    bag = sqlite3.connect(yol)
    try:
        assert bag.execute("PRAGMA journal_mode").fetchone()[0].upper() == GUNLUK_KIPI
    finally:
        bag.close()
