"""Maliyet: fiyat, TCMB kur okuma, günde bir kez kur alma, hesap ve API uçları.

Hiçbir testte internete çıkılmaz; TCMB dosyası sahte göndericiden gelir.
"""

from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from arayuz.sunucu import sunucu_olustur
from cekirdek.hatalar import GecersizDegerHatasi
from depolama.veritabani import Veritabani
from maliyet.hesap import MaliyetGirdisi, MaliyetHesaplayici
from maliyet.kur import Kur, KurDeposu, KurServisi, TcmbKurOkuyucu
from maliyet.para import Fiyat

ORNEK_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Tarih_Date Tarih="14.11.2026" Date="11/14/2026" Bulten_No="2026/220">
  <Currency CrossOrder="0" Kod="USD" CurrencyCode="USD">
    <Unit>1</Unit><Isim>ABD DOLARI</Isim><ForexBuying>40.10</ForexBuying><ForexSelling>40.00</ForexSelling>
  </Currency>
  <Currency CrossOrder="1" Kod="JPY" CurrencyCode="JPY">
    <Unit>100</Unit><Isim>JAPON YENI</Isim><ForexBuying>26.0</ForexBuying><ForexSelling>26.5</ForexSelling>
  </Currency>
  <Currency CrossOrder="2" Kod="CNY" CurrencyCode="CNY">
    <Unit>1</Unit><Isim>CIN YUANI</Isim><ForexBuying>5.50</ForexBuying><ForexSelling>5.60</ForexSelling>
  </Currency>
</Tarih_Date>""".encode("utf-8")


class SahteTcmb:
    """Kaç kez çağrıldığını sayar; istenirse hata fırlatır."""

    def __init__(self, xml: bytes = ORNEK_XML, hata: bool = False) -> None:
        self.xml, self.hata, self.cagri = xml, hata, 0

    def __call__(self) -> bytes:
        self.cagri += 1
        if self.hata:
            raise OSError("bağlantı yok")
        return self.xml


# ---------- Fiyat ve kur okuma ----------


def test_fiyat_denetimi() -> None:
    assert Fiyat(0).tutar == 0  # bedava/hediye parça olabilir
    for kotu in (-1, float("nan"), True, "100"):
        with pytest.raises(GecersizDegerHatasi):
            Fiyat(kotu)
    with pytest.raises(GecersizDegerHatasi):
        Fiyat(10, "XYZ")
    with pytest.raises(GecersizDegerHatasi):
        Fiyat(1e9)


def test_tcmb_okuma_doviz_satis_ve_birim() -> None:
    kurlar = TcmbKurOkuyucu.oku(ORNEK_XML, "2026-11-15")
    assert set(kurlar) == {"USD", "CNY"}  # JPY listede yok, alınmaz
    assert kurlar["USD"].tl_karsiligi == 40.00 and kurlar["USD"].kur_tarihi == "14.11.2026"


def test_kur_gunde_bir_kez_alinir_ve_yenilenebilir(tmp_path: Path) -> None:
    sahte = SahteTcmb()
    servis = KurServisi(KurDeposu(Veritabani(tmp_path / "vt.sqlite3")), sahte, bugun=lambda: date(2026, 11, 15))
    assert servis.kurlar().kurlar["USD"].tl_karsiligi == 40.0
    servis.kurlar()
    assert sahte.cagri == 1
    servis.kurlar(zorla=True)
    assert sahte.cagri == 2


def test_kur_alinamazsa_son_kayitli_kullanilir(tmp_path: Path) -> None:
    depo = KurDeposu(Veritabani(tmp_path / "vt.sqlite3"))
    bos = KurServisi(depo, SahteTcmb(hata=True)).kurlar()
    assert bos.kurlar == {} and "alınamadı" in bos.hata
    depo.kaydet({"USD": Kur("USD", 39.0, "10.11.2026", "2026-11-10")})
    durum = KurServisi(depo, SahteTcmb(hata=True)).kurlar()
    assert durum.kurlar["USD"].tl_karsiligi == 39.0 and not durum.guncel_mi and "Son kayıtlı" in durum.hata


# ---------- Hesap ----------


def test_maliyet_gruplari_ve_eksikler() -> None:
    kurlar = {"USD": Kur("USD", 40.0, "14.11.2026", "2026-11-15")}
    girdiler = [
        MaliyetGirdisi("Şasi", 1, True, Fiyat(800)),
        MaliyetGirdisi("Motor", 4, False, Fiyat(25, "USD")),
        MaliyetGirdisi("Pil", 1, False, None),
        MaliyetGirdisi("ESC", 1, True, Fiyat(50, "EUR")),  # EUR kuru yok
    ]
    o = MaliyetHesaplayici().hesapla(girdiler, kurlar)
    assert o.kalemler[1].tl_tutar == pytest.approx(4 * 25 * 40) and o.kalemler[1].tahmini
    assert o.kalemler[2].eksik == "fiyat girilmemiş" and "EUR" in o.kalemler[3].eksik
    t = o.toplamlar
    assert t["alinacak"].tl == pytest.approx(4000) and t["alinacak"].tahmini and t["alinacak"].eksik_kalem_sayisi == 1
    assert t["elimde"].tl == pytest.approx(800) and not t["elimde"].tahmini and t["elimde"].eksik_kalem_sayisi == 1
    assert t["toplam"].tl == pytest.approx(4800) and t["toplam"].eksik_kalem_sayisi == 2
    assert [k.para_birimi for k in o.kullanilan_kurlar] == ["USD"]


# ---------- API ----------

MOTOR = {"tur": "motor", "uretici": "T-Motor", "model": "F60", "agirlik_g": 33.5}
PIL = {"tur": "pil", "uretici": "CNHL", "model": "1500 6S"}


@pytest.fixture
def ortam(tmp_path: Path):
    tcmb = SahteTcmb()
    istemci = TestClient(sunucu_olustur(tmp_path / "veri", kur_getirici=tcmb))
    drone = istemci.post(
        "/api/dronelar", json={"ad": "Q", "baslangic_turu": "sifirdan", "drone_turu": "quadcopter", "amac": "FPV yarış"}
    ).json()["kimlik"]
    motor = istemci.post(f"/api/dronelar/{drone}/parcalar", json={"parca": MOTOR, "adet": 4, "durum": "elimde"}).json()
    pil = istemci.post(f"/api/dronelar/{drone}/parcalar", json={"parca": PIL, "adet": 1}).json()
    return istemci, drone, tcmb, motor["parca_kimlik"], pil["parca_kimlik"]


def _maliyet(istemci: TestClient, drone: int) -> dict:
    yanit = istemci.get(f"/api/dronelar/{drone}/maliyet")
    assert yanit.status_code == 200, yanit.text
    return yanit.json()


def test_fiyatsiz_drone_ve_tl_fiyatlarda_internete_cikilmaz(ortam) -> None:
    istemci, drone, tcmb, motor, pil = ortam
    m = _maliyet(istemci, drone)
    assert [k["tip"] for k in m["kalemler"]] == ["sasi", "parca", "parca"]
    assert m["toplamlar"]["toplam"]["eksik_kalem_sayisi"] == 3
    istemci.put(f"/api/katalog/{motor}/fiyat", json={"tutar": 1000, "para_birimi": "TRY"})
    istemci.put(f"/api/dronelar/{drone}/sasi/fiyat", json={"tutar": 750, "para_birimi": "TRY", "elimde": False})
    m = _maliyet(istemci, drone)
    assert m["toplamlar"]["elimde"]["tl"] == 4000  # 4 motor elimde
    assert m["toplamlar"]["alinacak"]["tl"] == 750 and m["toplamlar"]["alinacak"]["eksik_kalem_sayisi"] == 1
    assert tcmb.cagri == 0 and m["kurlar"] == []


def test_yabanci_fiyat_kurla_cevrilir_tahmini(ortam) -> None:
    istemci, drone, tcmb, motor, pil = ortam
    istemci.put(f"/api/katalog/{pil}/fiyat", json={"tutar": 150, "para_birimi": "CNY"})
    m = _maliyet(istemci, drone)
    kalem = next(k for k in m["kalemler"] if k.get("parca_kimlik") == pil)
    assert kalem["tl_tutar"] == pytest.approx(150 * 5.6) and kalem["tahmini"] is True
    assert m["toplamlar"]["alinacak"]["tahmini"] is True
    assert m["kurlar"][0]["para_birimi"] == "CNY" and m["kurlar"][0]["kur_tarihi"] == "14.11.2026"
    _maliyet(istemci, drone)
    assert tcmb.cagri == 1  # aynı gün ikinci kez indirilmez
    istemci.get(f"/api/dronelar/{drone}/maliyet", params={"yenile": "true"})
    assert tcmb.cagri == 2


def test_sasi_elimde_ve_fiyat_silme(ortam) -> None:
    istemci, drone, _, motor, _ = ortam
    istemci.put(f"/api/dronelar/{drone}/sasi/fiyat", json={"tutar": 750, "elimde": True})
    m = _maliyet(istemci, drone)
    assert m["sasi_elimde"] is True and m["toplamlar"]["elimde"]["tl"] == 750
    istemci.put(f"/api/katalog/{motor}/fiyat", json={"tutar": 100})
    istemci.put(f"/api/katalog/{motor}/fiyat", json={"tutar": None})
    kalem = next(k for k in _maliyet(istemci, drone)["kalemler"] if k.get("parca_kimlik") == motor)
    assert kalem["tutar"] is None and kalem["eksik"] == "fiyat girilmemiş"


def test_parca_fiyati_tum_dronelarda_gecerli(ortam) -> None:
    istemci, drone, _, motor, _ = ortam
    ikinci = istemci.post(
        "/api/dronelar", json={"ad": "B", "baslangic_turu": "sifirdan", "drone_turu": "hexacopter", "amac": "FPV yarış"}
    ).json()["kimlik"]
    istemci.post(f"/api/dronelar/{ikinci}/parcalar", json={"parca_kimlik": motor, "adet": 6})
    istemci.put(f"/api/katalog/{motor}/fiyat", json={"tutar": 1000})
    kalem = next(k for k in _maliyet(istemci, ikinci)["kalemler"] if k.get("parca_kimlik") == motor)
    assert kalem["tl_tutar"] == 6000


def test_gecersiz_fiyat_ve_olmayan_kayit(ortam) -> None:
    istemci, drone, _, motor, _ = ortam
    yanit = istemci.put(f"/api/katalog/{motor}/fiyat", json={"tutar": -5})
    assert yanit.status_code == 400 and "Fiyat" in yanit.json()["hata"]
    assert istemci.put(f"/api/katalog/{motor}/fiyat", json={"tutar": 5, "para_birimi": "XYZ"}).status_code == 400
    assert istemci.put("/api/katalog/999/fiyat", json={"tutar": 5}).status_code == 404
    assert istemci.put("/api/dronelar/999/sasi/fiyat", json={"tutar": 5}).status_code == 404
    assert istemci.get("/api/dronelar/999/maliyet").status_code == 404
    assert [p["deger"] for p in istemci.get("/api/para-birimleri").json()][0] == "TRY"


def test_drone_silinince_maliyet_kaydi_silinir(ortam) -> None:
    istemci, drone, _, _, _ = ortam
    istemci.put(f"/api/dronelar/{drone}/sasi/fiyat", json={"tutar": 750})
    assert istemci.delete(f"/api/dronelar/{drone}").status_code == 200
