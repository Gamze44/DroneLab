"""Elektronik API uçları, servis ve drone–parça deposu için uçtan uca testler."""

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
import pytest

from arayuz.sunucu import sunucu_olustur
from elektronik.parcalar.alan_tanimlari import alan_tanimlari
from elektronik.parcalar.cekirdek_parcalar import Motor, Pil, UcusKarti


@pytest.fixture
def istemci(tmp_path: Path) -> TestClient:
    return TestClient(sunucu_olustur(tmp_path / "veri"))


@pytest.fixture
def drone(istemci: TestClient) -> int:
    yanit = istemci.post(
        "/api/dronelar", json={"ad": "Q", "baslangic_turu": "sifirdan", "drone_turu": "quadcopter", "amac": "FPV yarış"}
    )
    return yanit.json()["kimlik"]


MOTOR = {"tur": "motor", "uretici": "T-Motor", "model": "F60 Pro V 1950KV", "agirlik_g": 33.5,
         "teknik": {"kv": 1950, "min_s": 4, "maks_s": 6}}


def _ekle(istemci: TestClient, drone: int, parca: dict | None = None, **ek: Any):
    govde = {"parca": parca, **ek} if parca is not None else ek
    return istemci.post(f"/api/dronelar/{drone}/parcalar", json=govde)


def _ozet(istemci: TestClient, drone: int) -> dict:
    return istemci.get(f"/api/dronelar/{drone}/elektronik").json()


# ---------- Form tanımları ----------


def test_alan_tanimlari() -> None:
    motor = {a["ad"]: a for a in alan_tanimlari(Motor)}
    assert motor["kv"]["cins"] == "sayi" and motor["min_s"]["cins"] == "tamsayi"
    assert "itki_tablosu" not in motor  # ayrı ekranda girilecek
    pil = {a["ad"]: a for a in alan_tanimlari(Pil)}
    assert pil["kimya"]["cins"] == "secim"
    assert {s["deger"] for s in pil["kimya"]["secenekler"]} == {"lipo", "lihv", "liion"}
    fc = {a["ad"]: a["cins"] for a in alan_tanimlari(UcusKarti)}
    assert fc["dahili_pdb"] == "mantiksal" and fc["bec_cikislari_v"] == "sayi_listesi" and fc["esc_protokolleri"] == "metin_listesi"


def test_parca_turleri_ucu(istemci: TestClient) -> None:
    v = istemci.get("/api/parca-turleri").json()
    assert [t["deger"] for t in v["turler"]][:2] == ["motor", "pervane"]
    assert {d["deger"] for d in v["durumlar"]} == {"elimde", "onerilen", "planlanan"}


# ---------- Ekleme ve özet ----------


def test_yeni_parca_ekle_ozet_ve_agirlik(istemci: TestClient, drone: int) -> None:
    istemci.put(f"/api/dronelar/{drone}/sasi/agirlik", json={"agirlik_g": 100})
    yanit = _ekle(istemci, drone, MOTOR, adet=4, durum="elimde")
    assert yanit.status_code == 200, yanit.text
    assert yanit.json()["durum_adi"] == "Elimde"

    ozet = _ozet(istemci, drone)
    kalem = ozet["kalemler"][0]
    assert kalem["bag"]["adet"] == 4
    assert kalem["parca"]["dogrulandi"] is True  # elle girilen parça doğrulanmış sayılır
    assert kalem["parca"]["teknik"]["maks_akim_a"] is None  # girilmeyen değer uydurulmadı
    assert "maks_akim_a" in kalem["parca"]["eksik_alanlar"]
    assert ozet["agirlik"]["parcalar_g"] == pytest.approx(134)
    assert ozet["agirlik"]["sasi_g"] == 100
    motor = next(z for z in ozet["zorunluluklar"] if z["etiket"] == "Motor")
    assert motor["durum"] == "tamam"

    # Uyum kontrolleri ve uçuş hesabı da özette gelir; pil olmadığı için tahmin yapılmaz.
    uyum = {u["kod"]: u for u in ozet["uyum"]}
    assert len(uyum) == 13 and uyum["K1"]["durum"] == "bilinmiyor" and uyum["K11"]["durum"] == "uygun"
    assert uyum["K5"]["tahmini"] is True
    assert ozet["ucus"]["toplam_itki_g"]["deger"] is None
    assert "Pil eklenmedi" in ozet["ucus"]["toplam_itki_g"]["aciklama"]
    assert ozet["ucus"]["hedef_itki_agirlik"] == 7


def test_ayni_parca_katalogda_varsa_409_ve_katalogdan_ekle(istemci: TestClient, drone: int, tmp_path: Path) -> None:
    _ekle(istemci, drone, MOTOR, adet=4)
    ikinci = istemci.post(
        "/api/dronelar", json={"ad": "Q2", "baslangic_turu": "elimdeki", "drone_turu": "quadcopter", "amac": "FPV yarış"}
    ).json()["kimlik"]

    yanit = _ekle(istemci, ikinci, {**MOTOR, "uretici": "tmotor", "model": "F60PRO V 1950 kv"}, adet=4)
    assert yanit.status_code == 409
    mevcut = yanit.json()["mevcut_kimlik"]

    yanit = _ekle(istemci, ikinci, parca_kimlik=mevcut, adet=4, durum="planlanan")
    assert yanit.status_code == 200
    assert _ozet(istemci, ikinci)["kalemler"][0]["parca"]["model"] == "F60 Pro V 1950KV"

    # Aynı drone'a aynı parça ikinci kez bağlanamaz.
    assert _ekle(istemci, ikinci, parca_kimlik=mevcut, adet=1).status_code == 409


def test_katalog_arama(istemci: TestClient, drone: int) -> None:
    _ekle(istemci, drone, MOTOR, adet=4)
    _ekle(istemci, drone, {"tur": "pil", "uretici": "CNHL", "model": "1300 6S", "teknik": {"kimya": "lipo"}})
    assert [p["model"] for p in istemci.get("/api/katalog", params={"metin": "t-motor"}).json()] == ["F60 Pro V 1950KV"]
    assert [p["tur"] for p in istemci.get("/api/katalog", params={"tur": "pil"}).json()] == ["pil"]


def test_diger_parca_alt_tur_zorunlu(istemci: TestClient, drone: int) -> None:
    yanit = _ekle(istemci, drone, {"tur": "diger", "uretici": "Matek", "model": "M10Q"})
    assert yanit.status_code == 400 and "alt tür" in yanit.json()["hata"]
    yanit = _ekle(istemci, drone, {"tur": "diger", "alt_tur": "gps", "uretici": "Matek", "model": "M10Q"})
    assert yanit.status_code == 200
    assert _ozet(istemci, drone)["kalemler"][0]["parca"]["alt_tur_adi"] == "GPS"


@pytest.mark.parametrize(
    ("parca", "parcasi"),
    [
        ({**MOTOR, "teknik": {"kv": -5}}, "sıfırdan büyük"),
        ({**MOTOR, "teknik": {"min_s": 6, "maks_s": 4}}, "büyük olamaz"),
        ({**MOTOR, "uretici": " "}, "boş olamaz"),
        ({**MOTOR, "kaynak_url": "javascript:alert(1)"}, "http"),
    ],
)
def test_gecersiz_parca_turkce_hata_ve_katalogda_kalmaz(istemci: TestClient, drone: int, parca: dict, parcasi: str) -> None:
    yanit = _ekle(istemci, drone, parca)
    assert yanit.status_code == 400
    assert parcasi in yanit.json()["hata"]
    assert istemci.get("/api/katalog").json() == []


def test_gecersiz_adet_katalogda_yetim_kayit_birakmaz(istemci: TestClient, drone: int) -> None:
    """Adet geçersizse parça kataloğa da yazılmamalı."""
    yanit = _ekle(istemci, drone, MOTOR, adet=0)
    assert yanit.status_code == 400 and "Adet" in yanit.json()["hata"]
    assert istemci.get("/api/katalog").json() == []


def test_hem_parca_hem_kimlik_verilemez(istemci: TestClient, drone: int) -> None:
    assert _ekle(istemci, drone, MOTOR, parca_kimlik=1).status_code == 400
    assert _ekle(istemci, drone, None).status_code == 400


# ---------- Adet / durum / kaldırma ----------


def test_bag_guncelle_ve_kaldir(istemci: TestClient, drone: int) -> None:
    bag = _ekle(istemci, drone, MOTOR, adet=2).json()
    yanit = istemci.patch(f"/api/dronelar/{drone}/parcalar/{bag['kimlik']}", json={"adet": 4})
    assert yanit.json()["adet"] == 4 and yanit.json()["durum"] == "planlanan"
    yanit = istemci.patch(f"/api/dronelar/{drone}/parcalar/{bag['kimlik']}", json={"durum": "elimde"})
    assert yanit.json()["adet"] == 4 and yanit.json()["durum"] == "elimde"
    assert istemci.patch(f"/api/dronelar/{drone}/parcalar/{bag['kimlik']}", json={"adet": 0}).status_code == 400

    assert istemci.delete(f"/api/dronelar/{drone}/parcalar/{bag['kimlik']}").status_code == 200
    assert _ozet(istemci, drone)["kalemler"] == []
    assert len(istemci.get("/api/katalog").json()) == 1  # parça katalogda kalır
    assert istemci.delete(f"/api/dronelar/{drone}/parcalar/{bag['kimlik']}").status_code == 404


def test_baska_dronun_bagi_degistirilemez(istemci: TestClient, drone: int) -> None:
    bag = _ekle(istemci, drone, MOTOR).json()
    baska = istemci.post(
        "/api/dronelar", json={"ad": "X", "baslangic_turu": "sifirdan", "drone_turu": "quadcopter", "amac": "FPV yarış"}
    ).json()["kimlik"]
    assert istemci.patch(f"/api/dronelar/{baska}/parcalar/{bag['kimlik']}", json={"adet": 9}).status_code == 404
    assert istemci.delete(f"/api/dronelar/{baska}/parcalar/{bag['kimlik']}").status_code == 404


def test_drone_silinince_baglar_silinir_parca_kalir(istemci: TestClient, drone: int) -> None:
    _ekle(istemci, drone, MOTOR, adet=4)
    assert istemci.delete(f"/api/dronelar/{drone}").status_code == 200
    assert len(istemci.get("/api/katalog").json()) == 1


def test_olmayan_drone_404(istemci: TestClient) -> None:
    assert istemci.get("/api/dronelar/999/elektronik").status_code == 404
    assert _ekle(istemci, 999, MOTOR).status_code == 404
    assert istemci.get("/api/katalog").json() == []


# ---------- Katalog parçasını düzenleme ----------


def test_katalog_parcasi_duzenle_formda_olmayan_alani_korur(istemci: TestClient, drone: int) -> None:
    _ekle(istemci, drone, MOTOR, adet=4)
    parca = _ozet(istemci, drone)["kalemler"][0]["parca"]
    # İstekte min_s/maks_s yok; mevcut değerleri silinmemeli (itki tablosu gibi formda olmayan alanlar için de aynı kural).
    yanit = istemci.put(
        f"/api/katalog/{parca['kimlik']}",
        json={**MOTOR, "agirlik_g": 34.0, "teknik": {"kv": 1950, "maks_akim_a": 45}},
    )
    assert yanit.status_code == 200, yanit.text
    v = yanit.json()
    assert v["agirlik_g"] == 34.0
    assert v["teknik"]["maks_akim_a"] == 45
    assert v["teknik"]["min_s"] == 4  # istekte olmayan alan korunur
    assert _ozet(istemci, drone)["agirlik"]["parcalar_g"] == pytest.approx(136)


def test_katalog_duzenleme_cakisma_409(istemci: TestClient, drone: int) -> None:
    _ekle(istemci, drone, MOTOR)
    ikinci = _ekle(istemci, drone, {**MOTOR, "model": "F40"}).json()
    yanit = istemci.put(f"/api/katalog/{ikinci['parca_kimlik']}", json=MOTOR)
    assert yanit.status_code == 409
