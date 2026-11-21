"""Drone ve şasi API uçları için uçtan uca testler (FastAPI TestClient ile)."""

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
import pytest

from arayuz.sunucu import sunucu_olustur


@pytest.fixture
def veri_klasoru(tmp_path: Path) -> Path:
    return tmp_path / "veri"


@pytest.fixture
def istemci(veri_klasoru: Path) -> TestClient:
    """Her test için boş veri klasörlü bir test istemcisi."""
    return TestClient(sunucu_olustur(veri_klasoru))


def _drone(istemci: TestClient, ad: str = "Test", baslangic: str = "sifirdan") -> dict[str, Any]:
    yanit = istemci.post(
        "/api/dronelar",
        json={"ad": ad, "baslangic_turu": baslangic, "drone_turu": "quadcopter", "amac": "FPV yarış"},
    )
    assert yanit.status_code == 200, yanit.text
    return yanit.json()


def _yukle(istemci: TestClient, kimlik: int, yol: Path, ad: str | None = None):
    with yol.open("rb") as f:
        return istemci.post(f"/api/dronelar/{kimlik}/sasi", files={"dosya": (ad or yol.name, f)})


# ---------- Drone ----------


def test_secenekler(istemci: TestClient) -> None:
    s = istemci.get("/api/secenekler").json()
    assert {t["deger"] for t in s["drone_turleri"]} == {"quadcopter", "hexacopter", "oktokopter"}
    assert "FPV yarış" in s["amaclar"]


def test_drone_olustur_listele_sil(istemci: TestClient) -> None:
    d = _drone(istemci, "Benim drone'um", "elimdeki")
    assert d["baslangic_turu_adi"] == "Elimdeki drone"
    assert d["motor_sayisi"] == 4
    assert [x["ad"] for x in istemci.get("/api/dronelar").json()] == ["Benim drone'um"]

    assert istemci.delete(f"/api/dronelar/{d['kimlik']}").status_code == 200
    assert istemci.get("/api/dronelar").json() == []
    assert istemci.get(f"/api/dronelar/{d['kimlik']}").status_code == 404


def test_bos_ad_turkce_hata(istemci: TestClient) -> None:
    yanit = istemci.post(
        "/api/dronelar", json={"ad": "  ", "baslangic_turu": "sifirdan", "drone_turu": "quadcopter", "amac": "FPV yarış"}
    )
    assert yanit.status_code == 400
    assert yanit.json()["hata"] == "Drone adı boş olamaz."


def test_gecersiz_tur_turkce_422(istemci: TestClient) -> None:
    """Pydantic doğrulama hataları İngilizce değil Türkçe mesajla dönmeli."""
    yanit = istemci.post(
        "/api/dronelar", json={"ad": "A", "baslangic_turu": "sifirdan", "drone_turu": "ucak", "amac": "FPV yarış"}
    )
    assert yanit.status_code == 422
    assert "eksik veya hatalı" in yanit.json()["hata"]


def test_kayitlar_sunucu_yeniden_acilinca_kalir(veri_klasoru: Path) -> None:
    """Program kapatılıp açılınca dronelar kaybolmamalı."""
    _drone(TestClient(sunucu_olustur(veri_klasoru)), "Kalıcı")
    assert [d["ad"] for d in TestClient(sunucu_olustur(veri_klasoru)).get("/api/dronelar").json()] == ["Kalıcı"]


# ---------- Şasi ----------


def test_sasi_yukle_onayla_ve_tekrar_ac(istemci: TestClient, stl_dosyasi: Path, veri_klasoru: Path) -> None:
    """Yükle -> birim onayla -> drone tekrar açılınca her şey kayıtlı olmalı."""
    k = _drone(istemci)["kimlik"]
    yanit = _yukle(istemci, k, stl_dosyasi, ad="Şasim.stl").json()
    assert yanit["yukleme"]["oneri"]["birim"] == "mm"
    assert yanit["drone"]["sasi_var"]
    assert (veri_klasoru / "sasi_dosyalari" / str(k) / "sasi.stl").is_file()

    olculer = istemci.post(f"/api/dronelar/{k}/sasi/birim", json={"birim": "mm"}).json()["olculer"]
    assert olculer["hacim_mm3"] == pytest.approx(2_500_000)

    ayrinti = istemci.get(f"/api/dronelar/{k}").json()
    assert ayrinti["sasi"]["yukleme"]["dosya_adi"] == "Şasim.stl"
    assert ayrinti["sasi"]["olculer"]["birim"] == "mm"


def test_dxf_yukle(istemci: TestClient, levha_dxf: Path) -> None:
    k = _drone(istemci)["kimlik"]
    y = _yukle(istemci, k, levha_dxf).json()["yukleme"]
    assert y["tur"] == "levha" and y["delik_sayisi"] == 2
    assert y["oneri"]["kaynak"] == "dosya"


def test_agirlik_dosyasiz_girilebilir_ve_silinebilir(istemci: TestClient) -> None:
    k = _drone(istemci)["kimlik"]
    d = istemci.put(f"/api/dronelar/{k}/sasi/agirlik", json={"agirlik_g": 112.5}).json()["drone"]
    assert d["sasi_agirlik_g"] == 112.5
    assert istemci.get("/api/dronelar").json()[0]["sasi_agirlik_g"] == 112.5

    d = istemci.put(f"/api/dronelar/{k}/sasi/agirlik", json={"agirlik_g": None}).json()["drone"]
    assert d["sasi_agirlik_g"] is None

    yanit = istemci.put(f"/api/dronelar/{k}/sasi/agirlik", json={"agirlik_g": -3})
    assert yanit.status_code == 400


def test_ilk_yukleme_agirligi_korur_degistirme_siler(istemci: TestClient, stl_dosyasi: Path, levha_dxf: Path) -> None:
    """Önce ağırlık girilip sonra ilk dosya yüklenirse ağırlık kalmalı; şasi değiştirilirse silinmeli."""
    k = _drone(istemci)["kimlik"]
    istemci.put(f"/api/dronelar/{k}/sasi/agirlik", json={"agirlik_g": 90})
    assert _yukle(istemci, k, stl_dosyasi).json()["drone"]["sasi_agirlik_g"] == 90

    istemci.put(f"/api/dronelar/{k}/sasi/agirlik", json={"agirlik_g": 95})
    assert _yukle(istemci, k, levha_dxf).json()["drone"]["sasi_agirlik_g"] is None


def test_drone_silinince_sasi_dosyasi_silinir(istemci: TestClient, stl_dosyasi: Path, veri_klasoru: Path) -> None:
    k = _drone(istemci)["kimlik"]
    _yukle(istemci, k, stl_dosyasi)
    istemci.delete(f"/api/dronelar/{k}")
    assert not (veri_klasoru / "sasi_dosyalari" / str(k)).exists()


def test_sasisiz_birim_onayi_404(istemci: TestClient) -> None:
    k = _drone(istemci)["kimlik"]
    yanit = istemci.post(f"/api/dronelar/{k}/sasi/birim", json={"birim": "mm"})
    assert yanit.status_code == 404
    assert "şasi dosyası yüklenmedi" in yanit.json()["hata"]


def test_olmayan_drone_a_yukleme_404(istemci: TestClient, stl_dosyasi: Path) -> None:
    assert _yukle(istemci, 999, stl_dosyasi).status_code == 404


def test_desteklenmeyen_dosya_415_ve_rehber(istemci: TestClient, tmp_path: Path) -> None:
    k = _drone(istemci)["kimlik"]
    yol = tmp_path / "parca.sldprt"
    yol.write_bytes(b"x")
    yanit = _yukle(istemci, k, yol)
    assert yanit.status_code == 415
    assert "SolidWorks" in yanit.json()["hata"] and yanit.json()["rehber"]


def test_bos_dosya_400(istemci: TestClient, tmp_path: Path) -> None:
    k = _drone(istemci)["kimlik"]
    yol = tmp_path / "bos.stl"
    yol.write_bytes(b"")
    yanit = _yukle(istemci, k, yol)
    assert yanit.status_code == 400
    assert yanit.json()["hata"] == "Yüklenen dosya boş."


def test_dosya_adindaki_klasor_yolu_yok_sayilir(istemci: TestClient, stl_dosyasi: Path) -> None:
    k = _drone(istemci)["kimlik"]
    y = _yukle(istemci, k, stl_dosyasi, ad="..\\..\\kotu.stl").json()["yukleme"]
    assert y["dosya_adi"] == "kotu.stl"


def test_gecersiz_birim_400(istemci: TestClient, stl_dosyasi: Path) -> None:
    k = _drone(istemci)["kimlik"]
    _yukle(istemci, k, stl_dosyasi)
    yanit = istemci.post(f"/api/dronelar/{k}/sasi/birim", json={"birim": "ayak"})
    assert yanit.status_code == 400
    assert "tanınmıyor" in yanit.json()["hata"]
