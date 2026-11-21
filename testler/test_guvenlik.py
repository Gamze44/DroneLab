"""
Sunucunun güvenlik katmanlarının testleri: Host denetimi (DNS rebinding), kaynak denetimi
(CSRF), istek boyutu sınırı, güvenlik başlıkları, kapalı API belgeleri, kimlik ve sayı sınırları.
"""

from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from arayuz.guvenlik import BAYT_BIR_MB, ICERIK_GUVENLIK_POLITIKASI, KaynakDenetimi
from arayuz.sunucu import sunucu_olustur
from cekirdek.ayarlar import EN_BUYUK_ISTEK_MB
from cekirdek.sayilar import gecerli_sayi_mi

YENI_DRONE = {"ad": "Deneme", "baslangic_turu": "sifirdan", "drone_turu": "quadcopter", "amac": "FPV yarış"}
KOTU_SITE = "http://kotu-site.example"


@pytest.fixture
def istemci(tmp_path: Path) -> TestClient:
    return TestClient(sunucu_olustur(tmp_path / "veri", kur_getirici=lambda: b""))


def _drone(istemci: TestClient) -> int:
    return istemci.post("/api/dronelar", json=YENI_DRONE).json()["kimlik"]


# ---------- Host denetimi (DNS rebinding) ----------


@pytest.mark.parametrize("host", ["127.0.0.1:8000", "localhost:51234", "LOCALHOST"])
def test_izinli_host_kabul_edilir(tmp_path: Path, host: str) -> None:
    istemci = TestClient(sunucu_olustur(tmp_path / "veri", izinli_hostlar=("127.0.0.1", "localhost")))
    assert istemci.get("/api/secenekler", headers={"host": host}).status_code == 200


@pytest.mark.parametrize("host", ["kotu-site.example", "127.0.0.1.kotu-site.example:8000", "testserver"])
def test_yabanci_host_reddedilir(tmp_path: Path, host: str) -> None:
    istemci = TestClient(sunucu_olustur(tmp_path / "veri", izinli_hostlar=("127.0.0.1", "localhost")))
    yanit = istemci.get("/api/dronelar", headers={"host": host})
    assert yanit.status_code == 400
    assert "127.0.0.1" in yanit.json()["hata"]


# ---------- Kaynak denetimi (CSRF) ----------


@pytest.mark.parametrize(
    ("basliklar", "beklenen"),
    [
        ({}, 200),  # tarayıcı dışı istemci (Origin yok)
        ({"sec-fetch-site": "same-origin"}, 200),
        ({"sec-fetch-site": "none"}, 200),
        ({"origin": "http://testserver"}, 200),
        ({"sec-fetch-site": "cross-site"}, 403),
        ({"sec-fetch-site": "same-site"}, 403),  # 127.0.0.1'in başka portu da "same-site"
        ({"origin": KOTU_SITE}, 403),
        ({"origin": "null"}, 403),
        ({"origin": "http://testserver.kotu-site.example"}, 403),
    ],
)
def test_yazma_istegi_kaynak_denetimi(istemci: TestClient, basliklar: dict, beklenen: int) -> None:
    yanit = istemci.post("/api/dronelar", json=YENI_DRONE, headers=basliklar)
    assert yanit.status_code == beklenen
    if beklenen == 403:
        assert "başka bir web sitesinden" in yanit.json()["hata"]


def test_baska_siteden_dosya_yukleme_ve_silme_reddedilir(istemci: TestClient) -> None:
    kimlik = _drone(istemci)
    kotu = {"origin": KOTU_SITE, "sec-fetch-site": "cross-site"}
    yukleme = istemci.post(f"/api/dronelar/{kimlik}/sasi", files={"dosya": ("a.stl", b"solid a")}, headers=kotu)
    assert yukleme.status_code == 403
    assert istemci.delete(f"/api/dronelar/{kimlik}", headers=kotu).status_code == 403
    assert istemci.post("/api/sartnameler/1/cikar", headers=kotu).status_code == 403
    assert istemci.get(f"/api/dronelar/{kimlik}").status_code == 200  # drone silinmedi


def test_okuma_istegi_kaynaktan_bagimsiz(istemci: TestClient) -> None:
    # GET hiçbir şeyi değiştirmez; tarayıcı yanıtı başka siteye zaten okutmaz (CORS yok).
    assert istemci.get("/api/dronelar", headers={"origin": KOTU_SITE}).status_code == 200


def test_kaynak_karari_birim() -> None:
    karar = KaynakDenetimi.kabul_edilir_mi
    assert karar("GET", "cross-site", KOTU_SITE, "127.0.0.1:8000")
    assert karar("PUT", None, "http://127.0.0.1:8000", "127.0.0.1:8000")
    assert not karar("PUT", None, "https://127.0.0.1:8000", "127.0.0.1:8000")  # şema farklı
    assert not karar("DELETE", None, "http://127.0.0.1:9000", "127.0.0.1:8000")  # port farklı
    assert not karar("PATCH", None, "http://127.0.0.1:8000", None)


# ---------- İstek boyutu ----------


def test_buyuk_json_govdesi_okunmadan_reddedilir(istemci: TestClient) -> None:
    govde = b'{"ad": "' + b"x" * ((EN_BUYUK_ISTEK_MB + 1) * BAYT_BIR_MB) + b'"}'
    yanit = istemci.post("/api/dronelar", content=govde, headers={"content-type": "application/json"})
    assert yanit.status_code == 413
    assert f"{EN_BUYUK_ISTEK_MB} MB" in yanit.json()["hata"]


def test_boyutu_bildirilmeyen_govde_sayilarak_kesilir(istemci: TestClient) -> None:
    def parcalar():
        for _ in range(EN_BUYUK_ISTEK_MB + 2):
            yield b" " * BAYT_BIR_MB

    yanit = istemci.post("/api/dronelar", content=parcalar(), headers={"content-type": "application/json"})
    assert yanit.status_code == 413


def test_gecersiz_content_length_reddedilir(istemci: TestClient) -> None:
    yanit = istemci.post("/api/dronelar", content=b"{}", headers={"content-type": "application/json", "content-length": "abc"})
    assert yanit.status_code == 400


def test_sartname_siniri_dosyaya_ozgu(istemci: TestClient) -> None:
    # Şartname sınırı (30 MB) genel yükleme sınırından (200 MB) küçüktür; 31 MB'lık
    # gövde yalnızca şartname adresinde reddedilir.
    buyuk = b"%PDF-1.4\n" + b"0" * (31 * BAYT_BIR_MB)
    yanit = istemci.post("/api/sartnameler", files={"dosya": ("b.pdf", buyuk)}, data={"ad": "x"})
    assert yanit.status_code == 413
    assert "30 MB" in yanit.json()["hata"]


# ---------- Başlıklar ve belgeler ----------


@pytest.mark.parametrize("adres", ["/", "/api/secenekler", "/statik/stil.css"])
def test_guvenlik_basliklari(istemci: TestClient, adres: str) -> None:
    b = istemci.get(adres).headers
    assert b["content-security-policy"] == ICERIK_GUVENLIK_POLITIKASI
    assert b["x-frame-options"] == "DENY"
    assert b["x-content-type-options"] == "nosniff"
    assert b["referrer-policy"] == "no-referrer"


def test_reddedilen_yanitta_da_guvenlik_basliklari(istemci: TestClient) -> None:
    yanit = istemci.post("/api/dronelar", json=YENI_DRONE, headers={"origin": KOTU_SITE})
    assert yanit.status_code == 403
    assert "content-security-policy" in yanit.headers


@pytest.mark.parametrize("adres", ["/docs", "/redoc", "/openapi.json"])
def test_api_belgeleri_kapali(istemci: TestClient, adres: str) -> None:
    assert istemci.get(adres).status_code == 404


# ---------- Kimlik ve sayı sınırları ----------


@pytest.mark.parametrize("adres", ["/api/dronelar/99999999999999999999999", "/api/dronelar/0", "/drone/-1"])
def test_sinir_disi_kimlik_422(istemci: TestClient, adres: str) -> None:
    yanit = istemci.get(adres)
    assert yanit.status_code == 422
    assert "hata" in yanit.json()


def test_govdedeki_asiri_buyuk_kimlik_422(istemci: TestClient) -> None:
    kimlik = _drone(istemci)
    yanit = istemci.put(f"/api/dronelar/{kimlik}/sartname", json={"sartname_kimlik": 10**20})
    assert yanit.status_code == 422


@pytest.mark.parametrize("agirlik", [1e308, 1.7e308, 1e10])
def test_asiri_buyuk_agirlik_reddedilir(istemci: TestClient, agirlik: float) -> None:
    kimlik = _drone(istemci)
    yanit = istemci.put(f"/api/dronelar/{kimlik}/sasi/agirlik", json={"agirlik_g": agirlik})
    assert yanit.status_code == 400
    assert istemci.get(f"/api/dronelar/{kimlik}/elektronik").status_code == 200


def test_asiri_parca_degeri_ve_adedi_reddedilir(istemci: TestClient) -> None:
    kimlik = _drone(istemci)
    adres = f"/api/dronelar/{kimlik}/parcalar"
    pil = {"tur": "pil", "uretici": "B", "model": "dev"}
    assert istemci.post(adres, json={"parca": {**pil, "agirlik_g": 1e308}, "adet": 1}).status_code == 400
    yanit = istemci.post(adres, json={"parca": {**pil, "agirlik_g": 100}, "adet": 999_999})
    assert yanit.status_code == 400
    assert "Adet" in yanit.json()["hata"]
    assert istemci.post(adres, json={"parca": {**pil, "agirlik_g": 100}, "adet": 10**30}).status_code in (400, 422)
    assert istemci.get(f"/api/dronelar/{kimlik}/elektronik").status_code == 200


@pytest.mark.parametrize(
    ("deger", "beklenen"),
    [(5, True), (2.5, True), (-3, True), (1e9, True), (1e10, False), (1e308, False), (10**400, False),
     (float("nan"), False), (float("inf"), False), (True, False), ("5", False), (None, False)],
)
def test_gecerli_sayi_mi(deger: object, beklenen: bool) -> None:
    assert gecerli_sayi_mi(deger) is beklenen


# ---------- Giriş noktaları ----------


def test_tarayici_sunucu_baslamazsa_acilmaz(monkeypatch: pytest.MonkeyPatch) -> None:
    import uygulama

    acilan: list[str] = []
    monkeypatch.setattr(uygulama.webbrowser, "open", acilan.append)
    # Port doluysa uvicorn başlamadan çıkar (should_exit); tarayıcı başka programı açmamalı.
    assert not uygulama.hazir_olunca_tarayiciyi_ac(SimpleNamespace(started=False, should_exit=True), "http://x", 1)
    assert uygulama.hazir_olunca_tarayiciyi_ac(SimpleNamespace(started=True, should_exit=False), "http://x", 1)
    assert acilan == ["http://x"]


@pytest.mark.skipif(sys.platform != "win32", reason="Kısayol aracı yalnızca Windows'ta çalışır")
def test_powershell_tam_yolla_cagrilir() -> None:
    from araclar.kisayol_olustur import powershell_yolu

    yol = powershell_yolu()
    assert yol.is_absolute() and yol.name.lower() == "powershell.exe"
