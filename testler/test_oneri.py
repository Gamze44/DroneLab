"""Yapay zeka önerisi: Gemini istemcisi, anahtar, ayarlar, sayaç, aday dönüştürme ve API uçları.

Hiçbir testte gerçek Gemini isteği yapılmaz; sahte sağlayıcı ve sahte gönderici kullanılır.
"""

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
import pytest

from arastirma.anahtar import AnahtarDeposu
from arastirma.ayarlar import YapayZekaAyarDeposu, YapayZekaAyarlari
from arastirma.gemini import GeminiSaglayicisi, hata_cevir
from arastirma.kullanim import GunlukKullanimSayaci
from arastirma.saglayici import ArastirmaSaglayicisi
from arayuz.sunucu import sunucu_olustur
from cekirdek.ayarlar import ANAHTAR_DOSYA_ADI, ANAHTAR_ORTAM_DEGISKENLERI
from cekirdek.hatalar import GecersizDegerHatasi, YapayZekaHatasi
from depolama.veritabani import Veritabani
from elektronik.oneri.aday import AdayDonusturucu
from elektronik.oneri.sema import OneriSemasiOlusturucu
from elektronik.parcalar.cekirdek_parcalar import Motor, Pil
from elektronik.parcalar.turler import DigerAltTur, ParcaTuru

SAHTE_ANAHTAR = "AIzaSahteTestAnahtari_1234567890abcdef"


@pytest.fixture(autouse=True)
def ortam_anahtari_yok(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bilgisayarda gerçek anahtar ortam değişkeni varsa testlere karışmasın."""
    for ad in ANAHTAR_ORTAM_DEGISKENLERI:
        monkeypatch.delenv(ad, raising=False)


# ---------- Gemini istemcisi (sahte gönderici) ----------


def _yanit(veri: Any) -> dict:
    return {"status": "completed", "steps": [{"type": "model_output", "content": [{"type": "text", "text": json.dumps(veri)}]}]}


def test_gemini_istek_govdesi_aramasiz_ve_json_cozumu() -> None:
    gonderilen: list[dict] = []

    def gonder(govde: dict) -> dict:
        gonderilen.append(govde)
        return _yanit({"adaylar": []})

    g = GeminiSaglayicisi(SAHTE_ANAHTAR, gonder=gonder)
    assert g.json_uret("sistem", "istem", {"type": "object"}) == {"adaylar": []}
    govde = gonderilen[0]
    assert "tools" not in govde  # Google Arama (ücretli) kullanılmıyor
    assert govde["store"] is False
    assert govde["response_format"]["schema"] == {"type": "object"}
    assert SAHTE_ANAHTAR not in json.dumps(govde)  # anahtar gövdede değil, yalnızca başlıkta
    assert SAHTE_ANAHTAR not in repr(g)


@pytest.mark.parametrize(
    "yanit",
    [
        {"status": "failed", "errors": [{"message": "x"}]},
        {"status": "completed", "steps": []},
        {"status": "completed", "steps": [{"type": "model_output", "content": [{"type": "text", "text": "json değil"}]}]},
    ],
)
def test_gemini_bozuk_yanit_turkce_hata(yanit: dict) -> None:
    with pytest.raises(YapayZekaHatasi):
        GeminiSaglayicisi(SAHTE_ANAHTAR, gonder=lambda _: yanit).json_uret("s", "i", {})


def test_gemini_hata_kodlari() -> None:
    assert hata_cevir(429).http_kodu == 429 and "sınır" in hata_cevir(429).mesaj
    assert hata_cevir(403).http_kodu == 401
    assert "anahtar" in hata_cevir(400, "API key not valid").mesaj
    with pytest.raises(YapayZekaHatasi):
        GeminiSaglayicisi(SAHTE_ANAHTAR, model="olmayan-model")


# ---------- Anahtar, ayarlar, sayaç ----------


def test_anahtar_deposu(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    depo = AnahtarDeposu(tmp_path)
    assert depo.oku() is None and depo.kaynak() is None
    depo.kaydet(f"  {SAHTE_ANAHTAR}\n")
    assert depo.oku() == SAHTE_ANAHTAR and depo.kaynak() == "dosya"
    monkeypatch.setenv("GEMINI_API_KEY", "OrtamdakiAnahtar_abcdefghijklmnop")
    assert depo.oku() == "OrtamdakiAnahtar_abcdefghijklmnop" and depo.kaynak() == "ortam_degiskeni"
    monkeypatch.delenv("GEMINI_API_KEY")
    depo.sil()
    assert depo.oku() is None
    with pytest.raises(GecersizDegerHatasi):
        depo.kaydet("kısa")
    with pytest.raises(GecersizDegerHatasi):
        depo.kaydet("boşluk içeren uzun bir metin buraya yapıştırıldı")


def test_ayarlar_varsayilan_kayit_ve_bozuk_dosya(tmp_path: Path) -> None:
    depo = YapayZekaAyarDeposu(tmp_path)
    assert depo.oku() == YapayZekaAyarlari()
    depo.kaydet(YapayZekaAyarlari(model="gemini-3.8-flash", gunluk_sinir=5))
    assert depo.oku().gunluk_sinir == 5 and depo.oku().model == "gemini-3.8-flash"
    with pytest.raises(GecersizDegerHatasi):
        depo.kaydet(YapayZekaAyarlari(gunluk_sinir=0))
    (tmp_path / "ayarlar_yerel.json").write_text("{bozuk", encoding="utf-8")
    assert depo.oku() == YapayZekaAyarlari()


def test_gunluk_sinir(tmp_path: Path) -> None:
    sayac = GunlukKullanimSayaci(Veritabani(tmp_path / "vt.sqlite3"))
    assert sayac.harca(2) == 1 and sayac.harca(2) == 2
    with pytest.raises(YapayZekaHatasi) as hata:
        sayac.harca(2)
    assert hata.value.http_kodu == 429 and sayac.bugun() == 2


# ---------- Şema ve aday dönüştürme ----------


def test_sema_alan_turleri() -> None:
    motor = OneriSemasiOlusturucu().teknik_sema(Motor)["properties"]
    assert motor["kv"]["type"] == "number" and motor["min_s"]["type"] == "integer"
    assert "itki_tablosu" not in motor
    pil = OneriSemasiOlusturucu().teknik_sema(Pil)["properties"]
    assert set(pil["kimya"]["enum"]) == {"lipo", "lihv", "liion"}
    tam = OneriSemasiOlusturucu().olustur(Motor)
    assert tam["properties"]["adaylar"]["items"]["required"] == ["uretici", "model", "gerekce"]


def test_aday_gecersiz_degerler_silinir_aday_kalir() -> None:
    ham = {
        "uretici": "T-Motor", "model": "F60 Pro V", "agirlik_g": -3, "gerekce": "Hafif ve güçlü.",
        "teknik": {"kv": 1950, "min_s": 4.0, "maks_s": 3, "maks_akim_a": "45A", "boyut": "2207", "uydurma_alan": 1},
    }
    a = AdayDonusturucu().donustur(ParcaTuru.MOTOR, None, ham)
    assert a is not None and a.parca.dogrulandi is False
    assert a.parca.kv == 1950 and a.parca.min_s == 4 and isinstance(a.parca.min_s, int)
    assert a.parca.maks_s is None  # en az 4 > en çok 3: çelişkili değer silindi
    assert a.parca.maks_akim_a is None and a.parca.agirlik_g is None
    assert set(a.silinen_alanlar) >= {"Ağırlık (g)", "En çok hücre (S)", "En büyük akım (A)"}
    assert "Gerekçe: Hafif ve güçlü." in a.parca.notlar


def test_aday_adi_yoksa_atlanir_ve_secim_denetlenir() -> None:
    d = AdayDonusturucu()
    assert d.donustur(ParcaTuru.MOTOR, None, {"uretici": "X", "model": " "}) is None
    assert d.donustur(ParcaTuru.MOTOR, None, "metin") is None
    pil = d.donustur(ParcaTuru.PIL, None, {"uretici": "CNHL", "model": "1500", "teknik": {"kimya": "nimh"}})
    assert pil.parca.kimya is None and "Kimya" in pil.silinen_alanlar
    gps = d.donustur(ParcaTuru.DIGER, DigerAltTur.GPS, {"uretici": "Matek", "model": "M10Q"})
    assert gps.parca.alt_tur is DigerAltTur.GPS


# ---------- API uçları (sahte sağlayıcı) ----------


class SahteSaglayici(ArastirmaSaglayicisi):
    """Sabit yanıt döndürür ve gelen istemi kaydeder."""

    def __init__(self, yanit: dict) -> None:
        self.yanit = yanit
        self.istemler: list[str] = []

    def json_uret(self, sistem_talimati: str, istem: str, sema: dict) -> dict:
        self.istemler.append(istem)
        return self.yanit


PIL_YANITI = {
    "adaylar": [
        {"uretici": "Yanlis", "model": "8S Pil", "agirlik_g": 300, "gerekce": "Çok güçlü.",
         "teknik": {"hucre_sayisi_s": 8, "kapasite_mah": 1500, "desarj_c": 120}},
        {"uretici": "CNHL", "model": "Black 1500 6S", "agirlik_g": 240, "gerekce": "Dengeli.",
         "teknik": {"hucre_sayisi_s": 6, "kapasite_mah": 1500, "desarj_c": 120, "konnektor": "XT60", "kimya": "lipo"}},
        {"uretici": "", "model": "adsız"},
    ]
}
MOTOR = {"tur": "motor", "uretici": "T-Motor", "model": "F60", "agirlik_g": 33.5,
         "teknik": {"kv": 1950, "min_s": 4, "maks_s": 6, "maks_akim_a": 35}}


@pytest.fixture
def ortam(tmp_path: Path):
    sahte = SahteSaglayici(PIL_YANITI)
    istemci = TestClient(sunucu_olustur(tmp_path / "veri", saglayici_uretici=lambda anahtar, model: sahte))
    drone = istemci.post(
        "/api/dronelar", json={"ad": "GizliAd", "baslangic_turu": "sifirdan", "drone_turu": "quadcopter", "amac": "FPV yarış"}
    ).json()["kimlik"]
    istemci.post(f"/api/dronelar/{drone}/parcalar", json={"parca": MOTOR, "adet": 4})
    return istemci, drone, sahte, tmp_path / "veri"


def test_anahtar_yoksa_istek_yapilmaz(ortam) -> None:
    istemci, drone, sahte, _ = ortam
    yanit = istemci.post(f"/api/dronelar/{drone}/oneriler", json={"tur": "pil"})
    assert yanit.status_code == 401 and "anahtar" in yanit.json()["hata"]
    assert sahte.istemler == []


def test_oneri_uyumsuz_sona_gelir_ve_istem_icerigi(ortam) -> None:
    istemci, drone, sahte, veri = ortam
    assert istemci.put("/api/ayarlar/yapay-zeka", json={"anahtar": SAHTE_ANAHTAR}).status_code == 200
    yanit = istemci.post(f"/api/dronelar/{drone}/oneriler", json={"tur": "pil"})
    assert yanit.status_code == 200, yanit.text
    v = yanit.json()
    assert [a["parca"]["model"] for a in v["adaylar"]] == ["Black 1500 6S", "8S Pil"]  # 8S motorla uyumsuz → sonda
    assert v["atlanan"] == 1 and v["bugun_kullanilan"] == 1
    sekiz = v["adaylar"][1]
    assert any(u["kod"] == "K1" and u["durum"] == "uygunsuz" for u in sekiz["uyum"])
    assert v["adaylar"][0]["parca"]["dogrulandi"] is False and v["adaylar"][0]["adet"] == 1
    istem = sahte.istemler[0]
    assert "FPV yarış" in istem and "T-Motor F60 ×4" in istem and "KV" in istem
    assert "GizliAd" not in istem  # drone adı gönderilmez


def test_secilen_oneri_onerilen_ve_dogrulanmamis_eklenir(ortam) -> None:
    istemci, drone, _, _ = ortam
    istemci.put("/api/ayarlar/yapay-zeka", json={"anahtar": SAHTE_ANAHTAR})
    aday = istemci.post(f"/api/dronelar/{drone}/oneriler", json={"tur": "pil"}).json()["adaylar"][0]
    p = aday["parca"]
    govde = {"adet": aday["adet"], "parca": {k: p[k] for k in ("tur", "alt_tur", "uretici", "model", "agirlik_g", "notlar", "teknik")}}
    yanit = istemci.post(f"/api/dronelar/{drone}/oneriler/sec", json=govde)
    assert yanit.status_code == 200, yanit.text
    assert yanit.json()["durum"] == "onerilen"
    kalem = next(k for k in istemci.get(f"/api/dronelar/{drone}/elektronik").json()["kalemler"] if k["parca"]["tur"] == "pil")
    assert kalem["parca"]["dogrulandi"] is False and "Gemini önerisi" in kalem["parca"]["notlar"]

    # İkinci öneride aynı pil artık drone'da olduğu için atlanır.
    v = istemci.post(f"/api/dronelar/{drone}/oneriler", json={"tur": "pil"}).json()
    assert [a["parca"]["model"] for a in v["adaylar"]] == ["8S Pil"]


def test_katalogdaki_parca_onerilirse_katalog_kaydi_kullanilir(ortam) -> None:
    istemci, drone, _, _ = ortam
    istemci.put("/api/ayarlar/yapay-zeka", json={"anahtar": SAHTE_ANAHTAR})
    ikinci = istemci.post(
        "/api/dronelar", json={"ad": "B", "baslangic_turu": "sifirdan", "drone_turu": "quadcopter", "amac": "FPV yarış"}
    ).json()["kimlik"]
    elle = {"tur": "pil", "uretici": "CNHL", "model": "Black 1500 6S", "agirlik_g": 245, "teknik": {"hucre_sayisi_s": 6}}
    istemci.post(f"/api/dronelar/{ikinci}/parcalar", json={"parca": elle})
    aday = next(a for a in istemci.post(f"/api/dronelar/{drone}/oneriler", json={"tur": "pil"}).json()["adaylar"]
                if a["parca"]["model"] == "Black 1500 6S")
    assert aday["katalog_kimlik"] is not None
    assert aday["parca"]["agirlik_g"] == 245 and aday["parca"]["dogrulandi"] is True  # kullanıcının değeri


def test_gunluk_sinir_api(ortam) -> None:
    istemci, drone, sahte, _ = ortam
    istemci.put("/api/ayarlar/yapay-zeka", json={"anahtar": SAHTE_ANAHTAR, "gunluk_sinir": 1})
    assert istemci.post(f"/api/dronelar/{drone}/oneriler", json={"tur": "pil"}).status_code == 200
    yanit = istemci.post(f"/api/dronelar/{drone}/oneriler", json={"tur": "pil"})
    assert yanit.status_code == 429 and "sınır" in yanit.json()["hata"]
    assert len(sahte.istemler) == 1


def test_diger_turunde_alt_tur_zorunlu(ortam) -> None:
    istemci, drone, _, _ = ortam
    istemci.put("/api/ayarlar/yapay-zeka", json={"anahtar": SAHTE_ANAHTAR})
    yanit = istemci.post(f"/api/dronelar/{drone}/oneriler", json={"tur": "diger"})
    assert yanit.status_code == 400 and "alt tür" in yanit.json()["hata"]


def test_ayarlar_api_anahtari_asla_dondurmez(ortam) -> None:
    istemci, _, _, veri = ortam
    assert istemci.get("/api/ayarlar/yapay-zeka").json()["anahtar_var"] is False
    yanit = istemci.put("/api/ayarlar/yapay-zeka", json={"anahtar": SAHTE_ANAHTAR, "model": "gemini-3.8-flash"})
    assert SAHTE_ANAHTAR not in yanit.text
    v = istemci.get("/api/ayarlar/yapay-zeka")
    assert SAHTE_ANAHTAR not in v.text
    assert v.json()["anahtar_var"] is True and v.json()["model"] == "gemini-3.8-flash"
    assert (veri / ANAHTAR_DOSYA_ADI).read_text(encoding="utf-8") == SAHTE_ANAHTAR
    assert istemci.put("/api/ayarlar/yapay-zeka", json={"gunluk_sinir": 0}).status_code == 400
    assert istemci.delete("/api/ayarlar/yapay-zeka/anahtar").json()["anahtar_var"] is False
    assert istemci.get("/ayarlar").status_code == 200
