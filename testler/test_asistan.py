"""
DroneLab Asistan testleri. Gerçek Gemini'ye istek atılmaz: sahte sağlayıcı, sırayla verilen
"turları" (araç çağrısı veya metin parçaları) üretir.
"""

from collections.abc import Iterator
import json
import logging
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
import pytest

from arastirma.gemini import GeminiSaglayicisi, SseOkuyucu
from arastirma.istemci import YapayZekaIstemcisi
from arastirma.model_secici import HEPSI_DOLU_MESAJI, OTOMATIK_MODEL, OTOMATIK_SIRA, ModelSecici
from arastirma.saglayici import ArastirmaSaglayicisi
from arastirma.sohbet import (
    ARAC_SERBEST,
    ARAC_YASAK,
    OLAY_ARAC_CAGRISI,
    OLAY_BITTI,
    OLAY_METIN,
    AracCagrisi,
    AracTanimi,
    SohbetOlayi,
)
from arayuz.sunucu import _asistan_servisi_olustur, sunucu_olustur
from asistan.ayarlar import EN_FAZLA_ARAC_TURU
from cekirdek.hatalar import YapayZekaHatasi
from depolama.veritabani import Veritabani
from drone.servis import DroneServisi
from elektronik.servis import ElektronikServisi
from maliyet.servis import MaliyetServisi
from sartname.servis import SartnameServisi

SAHTE_ANAHTAR = "AIzaSahteTestAnahtari_1234567890abcdef"
YENI_DRONE = {"ad": "Asistan", "baslangic_turu": "sifirdan", "drone_turu": "quadcopter", "amac": "FPV yarış"}
MOTOR = {"tur": "motor", "uretici": "T-Motor", "model": "F60", "agirlik_g": 33.5,
         "teknik": {"kv": 1950, "maks_akim_a": 35, "min_s": 4, "maks_s": 6}}
PIL = {"tur": "pil", "uretici": "CNHL", "model": "1500 6S", "agirlik_g": 240,
       "teknik": {"hucre_sayisi_s": 6, "kapasite_mah": 1500, "desarj_c": 120, "kimya": "lipo"}}


@pytest.fixture(autouse=True)
def ortam_anahtarini_kaldir(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bilgisayardaki gerçek anahtar testlere karışmasın."""
    for ad in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(ad, raising=False)


# ---------- Sahte model ----------


def metin_turu(*parcalar: str) -> list[SohbetOlayi]:
    adim = {"type": "model_output", "content": [{"type": "text", "text": "".join(parcalar)}]}
    return [SohbetOlayi(OLAY_METIN, metin=p) for p in parcalar] + [
        SohbetOlayi(OLAY_BITTI, adimlar=[adim], durum="completed", kullanim={"total_tokens": 10})
    ]


def arac_turu(ad: str, argumanlar: dict[str, Any] | None = None, kimlik: str = "c1") -> list[SohbetOlayi]:
    adim = {"type": "function_call", "id": kimlik, "name": ad, "arguments": argumanlar or {}}
    return [
        SohbetOlayi(OLAY_ARAC_CAGRISI, cagri=AracCagrisi(kimlik, ad, argumanlar or {})),
        SohbetOlayi(OLAY_BITTI, adimlar=[adim], durum="requires_action"),
    ]


class SahteSohbet(ArastirmaSaglayicisi):
    """Her çağrıda sıradaki turu verir; gelen girdileri saklar."""

    def __init__(self, turlar: list[Any]) -> None:
        self.turlar = list(turlar)
        self.cagrilar: list[dict[str, Any]] = []

    def json_uret(self, sistem_talimati: str, istem: str, sema: dict) -> dict:
        raise AssertionError("bu testte kullanılmaz")

    def sohbet_et(self, sistem_talimati, girdiler, araclar, akis=True, arac_kullanimi=ARAC_SERBEST) -> Iterator[SohbetOlayi]:
        self.cagrilar.append({
            "sistem": sistem_talimati, "girdiler": json.loads(json.dumps(girdiler)),
            "araclar": [a.ad for a in araclar], "akis": akis, "arac_kullanimi": arac_kullanimi,
        })
        tur = self.turlar.pop(0)
        if callable(tur):
            tur = tur(akis)
        if isinstance(tur, Exception):
            raise tur
        return iter(tur)


def sse_coz(govde: str) -> list[dict[str, Any]]:
    """Akış yanıtını olay listesine çevirir."""
    olaylar = []
    for blok in govde.strip().split("\n\n"):
        veri = [s[len("data: "):] for s in blok.splitlines() if s.startswith("data: ")]
        if veri:
            olaylar.append(json.loads("\n".join(veri)))
    return olaylar


@pytest.fixture
def kurulum(tmp_path: Path):
    """(istemci, sahte model, drone kimliği): anahtarı girilmiş, motor ve pili olan bir quad."""
    sahte = SahteSohbet([])
    istemci = TestClient(sunucu_olustur(tmp_path / "veri", saglayici_uretici=lambda a, m: sahte, kur_getirici=lambda: b""))
    istemci.put("/api/ayarlar/yapay-zeka", json={"anahtar": SAHTE_ANAHTAR})
    drone = istemci.post("/api/dronelar", json=YENI_DRONE).json()["kimlik"]
    istemci.put(f"/api/dronelar/{drone}/sasi/agirlik", json={"agirlik_g": 120})
    istemci.post(f"/api/dronelar/{drone}/parcalar", json={"parca": MOTOR, "adet": 4})
    istemci.post(f"/api/dronelar/{drone}/parcalar", json={"parca": PIL, "adet": 1})
    return istemci, sahte, drone


def _sor(istemci: TestClient, drone: int | None, mesaj: str = "Toplam ağırlık ne?", ekran: str = "elektronik"):
    return istemci.post("/api/asistan/sohbet", json={"mesaj": mesaj, "drone_kimlik": drone, "ekran": ekran})


def _motor_bagi(istemci: TestClient, drone: int) -> dict:
    return next(k["bag"] for k in istemci.get(f"/api/dronelar/{drone}/elektronik").json()["kalemler"]
                if k["parca"]["tur"] == "motor")


# ---------- Araç sonuçları ve akış ----------


def test_toplam_agirlik_arac_sonucundan_gelir(kurulum) -> None:
    istemci, sahte, drone = kurulum
    sahte.turlar = [arac_turu("proje_ozeti_getir"), metin_turu("Toplam ağırlık ", "394 g (tahmini).")]
    yanit = _sor(istemci, drone)
    assert yanit.status_code == 200 and yanit.headers["content-type"].startswith("text/event-stream")
    olaylar = sse_coz(yanit.text)
    assert [o["tur"] for o in olaylar] == ["arac", "metin", "metin", "bitti"]
    assert olaylar[-1]["model"] == OTOMATIK_SIRA[0]

    ikinci = sahte.cagrilar[1]["girdiler"]
    sonuc = json.loads(ikinci[-1]["result"][0]["text"])
    assert ikinci[-1]["type"] == "function_result" and ikinci[-1]["call_id"] == "c1"
    ekrandaki = istemci.get(f"/api/dronelar/{drone}/elektronik").json()["agirlik"]["toplam_g"]
    assert sonuc["agirlik"]["toplam_g"] == pytest.approx(ekrandaki)
    assert "Ekran: Elektronik" in sahte.cagrilar[0]["sistem"] and "Asistan" in sahte.cagrilar[0]["sistem"]


def test_degisiklik_uygula_basilana_kadar_yapilmaz(kurulum) -> None:
    istemci, sahte, drone = kurulum
    bag = _motor_bagi(istemci, drone)
    oneri = {"degisiklikler": [{"islem": "adet_degistir", "bag_kimlik": bag["kimlik"], "adet": 6}], "gerekce": "Hexa denemesi."}
    sahte.turlar = [arac_turu("degisiklik_oner", oneri), metin_turu("Kartı inceleyin.")]
    olaylar = sse_coz(_sor(istemci, drone, "Motor sayısını artır").text)
    kart = next(o["oneri"] for o in olaylar if o["tur"] == "oneri")
    assert kart["durum"] == "bekliyor" and kart["aciklamalar"] == ["Adet: T-Motor F60 ×4 → ×6"]
    assert kart["sonra"]["toplam_agirlik_g"]["deger"] > kart["once"]["toplam_agirlik_g"]["deger"]
    sonuc = json.loads(sahte.cagrilar[1]["girdiler"][-1]["result"][0]["text"])
    assert "UYGULANMADI" in sonuc["durum"]
    assert _motor_bagi(istemci, drone)["adet"] == 4  # henüz değişmedi

    assert istemci.post(f"/api/asistan/oneriler/{kart['kimlik']}/uygula").json()["oneri"]["durum"] == "uygulandi"
    assert _motor_bagi(istemci, drone)["adet"] == 6
    ikinci = istemci.post(f"/api/asistan/oneriler/{kart['kimlik']}/uygula")
    assert ikinci.status_code == 400 and "zaten" in ikinci.json()["hata"]


def test_vazgecilen_oneri_drone_u_degistirmez(kurulum) -> None:
    istemci, sahte, drone = kurulum
    bag = _motor_bagi(istemci, drone)
    oneri = {"degisiklikler": [{"islem": "parca_cikar", "bag_kimlik": bag["kimlik"]}], "gerekce": "Deneme."}
    sahte.turlar = [arac_turu("degisiklik_oner", oneri), metin_turu("Tamam.")]
    kart = next(o["oneri"] for o in sse_coz(_sor(istemci, drone).text) if o["tur"] == "oneri")
    assert istemci.post(f"/api/asistan/oneriler/{kart['kimlik']}/vazgec").json()["oneri"]["durum"] == "vazgecildi"
    assert _motor_bagi(istemci, drone)["adet"] == 4
    assert istemci.post(f"/api/asistan/oneriler/{kart['kimlik']}/uygula").status_code == 400


def test_gecersizlesmis_oneri_turkce_hata_ve_degisiklik_yok(kurulum) -> None:
    istemci, sahte, drone = kurulum
    bag = _motor_bagi(istemci, drone)
    oneri = {"degisiklikler": [{"islem": "adet_degistir", "bag_kimlik": bag["kimlik"], "adet": 8}], "gerekce": "x"}
    sahte.turlar = [arac_turu("degisiklik_oner", oneri), metin_turu("Tamam.")]
    kart = next(o["oneri"] for o in sse_coz(_sor(istemci, drone).text) if o["tur"] == "oneri")
    istemci.delete(f"/api/dronelar/{drone}/parcalar/{bag['kimlik']}")  # kullanıcı parçayı elle sildi
    yanit = istemci.post(f"/api/asistan/oneriler/{kart['kimlik']}/uygula")
    assert yanit.status_code == 400 and "artık uygulanamıyor" in yanit.json()["hata"]


def test_senaryo_kaydetmez_ve_gecersiz_degisiklik_modele_hata_doner(kurulum) -> None:
    istemci, sahte, drone = kurulum
    bag = _motor_bagi(istemci, drone)
    senaryo = {"degisiklikler": [{"islem": "adet_degistir", "bag_kimlik": bag["kimlik"], "adet": 6}]}
    hatali = {"degisiklikler": [{"islem": "parca_cikar", "bag_kimlik": 99999}]}
    sahte.turlar = [arac_turu("senaryo_hesapla", senaryo), arac_turu("senaryo_hesapla", hatali, "c2"), metin_turu("Bitti.")]
    _sor(istemci, drone, "6 motor olursa?")
    birinci = json.loads(sahte.cagrilar[1]["girdiler"][-1]["result"][0]["text"])
    ekrandaki = istemci.get(f"/api/dronelar/{drone}/elektronik").json()["agirlik"]["toplam_g"]
    assert birinci["once"]["toplam_agirlik_g"]["deger"] == pytest.approx(ekrandaki)
    assert birinci["sonra"]["toplam_agirlik_g"]["deger"] == pytest.approx(ekrandaki + 2 * 33.5 * 1.05, rel=1e-3)
    ikinci = sahte.cagrilar[2]["girdiler"][-1]
    assert ikinci["is_error"] is True and "99999" in ikinci["result"][0]["text"]
    assert _motor_bagi(istemci, drone)["adet"] == 4


def test_arac_turu_sinirli_son_turda_arac_kapali(kurulum) -> None:
    istemci, sahte, drone = kurulum
    sahte.turlar = [arac_turu("parca_listesi_getir", kimlik=f"c{i}") for i in range(EN_FAZLA_ARAC_TURU)]
    sahte.turlar.append(metin_turu("Özet."))
    olaylar = sse_coz(_sor(istemci, drone).text)
    assert len(sahte.cagrilar) == EN_FAZLA_ARAC_TURU + 1
    assert sahte.cagrilar[-1]["arac_kullanimi"] == ARAC_YASAK
    assert olaylar[-1]["tur"] == "bitti" and olaylar[-1]["bugun_kullanilan"] == EN_FAZLA_ARAC_TURU + 1


def test_genel_sohbette_yalnizca_katalog_araci(kurulum) -> None:
    istemci, sahte, _ = kurulum
    sahte.turlar = [metin_turu("Merhaba.")]
    yanit = _sor(istemci, None, "Neler yapabilirim?", ekran="ana_sayfa")
    assert sse_coz(yanit.text)[-1]["tur"] == "bitti"
    assert sahte.cagrilar[0]["araclar"] == ["katalogda_ara"]
    assert "Ekran: Ana sayfa" in sahte.cagrilar[0]["sistem"] and "Kayıtlı dronelar (1)" in sahte.cagrilar[0]["sistem"]


# ---------- Ön denetimler ve güvenlik ----------


def test_akis_baslamadan_hatalar_json(tmp_path: Path) -> None:
    sahte = SahteSohbet([])
    istemci = TestClient(sunucu_olustur(tmp_path / "veri", saglayici_uretici=lambda a, m: sahte, kur_getirici=lambda: b""))
    drone = istemci.post("/api/dronelar", json=YENI_DRONE).json()["kimlik"]
    yok = _sor(istemci, drone)
    assert yok.status_code == 401 and "anahtar" in yok.json()["hata"]
    istemci.put("/api/ayarlar/yapay-zeka", json={"anahtar": SAHTE_ANAHTAR, "gunluk_sinir": 1})
    assert _sor(istemci, drone, "   ").status_code == 400
    assert _sor(istemci, 999).status_code == 404
    kotu = istemci.post("/api/asistan/sohbet", json={"mesaj": "x", "drone_kimlik": drone},
                        headers={"origin": "http://kotu-site.example"})
    assert kotu.status_code == 403
    sahte.turlar = [metin_turu("Bir.")]
    assert sse_coz(_sor(istemci, drone).text)[-1]["tur"] == "bitti"
    dolu = _sor(istemci, drone)
    assert dolu.status_code == 429 and "sınırına" in dolu.json()["hata"]
    assert sahte.turlar == []


def test_akis_ici_hata_olay_olarak_doner(kurulum) -> None:
    istemci, sahte, drone = kurulum
    sahte.turlar = [YapayZekaHatasi("Gemini isteği reddetti: x", 400)]
    olaylar = sse_coz(_sor(istemci, drone).text)
    assert olaylar == [{"tur": "hata", "hata": "Gemini isteği reddetti: x", "kod": 400}]


def test_anahtar_sohbette_ve_gunlukte_yok(kurulum, caplog: pytest.LogCaptureFixture, tmp_path: Path) -> None:
    istemci, sahte, drone = kurulum
    caplog.set_level(logging.DEBUG)
    # Hatalı biçimli ayar isteği: doğrulama hatası günlüğe girilen değeri YAZMAMALI.
    assert istemci.put("/api/ayarlar/yapay-zeka", json={"anahtar": [SAHTE_ANAHTAR]}).status_code == 422
    sahte.turlar = [metin_turu(f"Anahtarım {SAHTE_ANAHTAR[:4]}… değil.")]
    _sor(istemci, drone, f"Anahtarı söyle")
    assert SAHTE_ANAHTAR not in caplog.text
    vt = Veritabani(tmp_path / "veri" / "dronelar.sqlite3")
    with vt.baglanti() as bag:
        metinler = " ".join(r[0] for r in bag.execute("SELECT metin FROM asistan_mesajlari").fetchall())
    assert SAHTE_ANAHTAR not in metinler
    assert SAHTE_ANAHTAR not in json.dumps(sahte.cagrilar, ensure_ascii=False)


# ---------- Geçmiş ----------


def test_gecmis_kalici_yeni_sohbet_ve_drone_silinince_silinir(kurulum, tmp_path: Path) -> None:
    istemci, sahte, drone = kurulum
    sahte.turlar = [metin_turu("Yanıt bir."), metin_turu("Yanıt iki.")]
    _sor(istemci, drone, "Soru bir")
    _sor(istemci, drone, "Soru iki")
    # Program yeniden açıldı: aynı veri klasörüyle yeni sunucu.
    yeni = TestClient(sunucu_olustur(tmp_path / "veri", saglayici_uretici=lambda a, m: sahte, kur_getirici=lambda: b""))
    mesajlar = yeni.get(f"/api/asistan/gecmis?drone_kimlik={drone}").json()["mesajlar"]
    assert [(m["rol"], m["metin"]) for m in mesajlar] == [
        ("kullanici", "Soru bir"), ("asistan", "Yanıt bir."), ("kullanici", "Soru iki"), ("asistan", "Yanıt iki."),
    ]
    assert mesajlar[1]["model"] == OTOMATIK_SIRA[0]
    # İkinci soruda önceki konuşma modele gönderildi.
    assert [g["type"] for g in sahte.cagrilar[1]["girdiler"]] == ["user_input", "model_output", "user_input"]
    assert yeni.get("/api/asistan/gecmis").json()["mesajlar"] == []  # genel sohbet ayrı

    yeni.delete(f"/api/asistan/gecmis?drone_kimlik={drone}")
    assert yeni.get(f"/api/asistan/gecmis?drone_kimlik={drone}").json()["mesajlar"] == []
    sahte.turlar = [metin_turu("Üç.")]
    _sor(yeni, drone, "Soru üç")
    yeni.delete(f"/api/dronelar/{drone}")
    with Veritabani(tmp_path / "veri" / "dronelar.sqlite3").baglanti() as bag:
        assert bag.execute("SELECT count(*) FROM asistan_mesajlari").fetchone()[0] == 0


def test_durdurulan_yanit_kaydedilir(tmp_path: Path) -> None:
    sahte = SahteSohbet([metin_turu("Yarım ", "kalan ", "yanıt")])
    vt = Veritabani(tmp_path / "vt.sqlite3")
    elektronik = ElektronikServisi(tmp_path, vt)
    yz = YapayZekaIstemcisi(tmp_path, lambda a, m: sahte, vt)
    yz.anahtar.kaydet(SAHTE_ANAHTAR)
    maliyet = MaliyetServisi(elektronik, tmp_path, lambda: b"", vt)
    dronelar = DroneServisi(tmp_path, vt)
    servis = _asistan_servisi_olustur(vt, yz, elektronik, SartnameServisi(tmp_path, elektronik, maliyet, yz, vt), dronelar)
    akis = servis.baslat(None, "ana_sayfa", "Uzun anlat")
    assert next(akis)["metin"] == "Yarım "
    akis.close()  # kullanıcı "Durdur"a bastı
    son = servis.gecmis(None)[-1]
    assert son["rol"] == "asistan" and son["metin"] == "Yarım (yanıt durduruldu)"


def test_akisli_gecmis_reddedilirse_akissiz_moda_gecer(kurulum) -> None:
    istemci, sahte, drone = kurulum

    def ikinci_tur(akis: bool):
        return YapayZekaHatasi("Gemini isteği reddetti: signature", 400) if akis else metin_turu("Akışsız yanıt.")

    sahte.turlar = [arac_turu("proje_ozeti_getir"), ikinci_tur, arac_turu("proje_ozeti_getir"), ikinci_tur]
    olaylar = sse_coz(_sor(istemci, drone).text)
    assert [o["tur"] for o in olaylar] == ["arac", "sifirla", "arac", "metin", "bitti"]
    assert [c["akis"] for c in sahte.cagrilar] == [True, True, False, False]
    sahte.turlar = [metin_turu("Sonraki.")]
    _sor(istemci, drone)
    assert sahte.cagrilar[-1]["akis"] is False  # tercih hatırlanır


# ---------- Otomatik model seçimi ----------


class ModeleGoreSahte(ArastirmaSaglayicisi):
    """Model adına göre hata ya da yanıt verir."""

    def __init__(self, hatalar: dict[str, YapayZekaHatasi]) -> None:
        self.hatalar = hatalar
        self.denenen: list[str] = []
        self.model = ""

    def json_uret(self, sistem_talimati: str, istem: str, sema: dict) -> dict:
        self.denenen.append(self.model)
        if self.model in self.hatalar:
            raise self.hatalar[self.model]
        return {"model": self.model}


def _yz(tmp_path: Path, sahte: ModeleGoreSahte, secici: ModelSecici | None = None) -> YapayZekaIstemcisi:
    def uret(anahtar: str, model: str) -> ArastirmaSaglayicisi:
        sahte.model = model
        return sahte

    yz = YapayZekaIstemcisi(tmp_path, uret, Veritabani(tmp_path / "vt.sqlite3"), secici)
    yz.anahtar.kaydet(SAHTE_ANAHTAR)
    return yz


def test_kota_dolunca_siradaki_model_ve_gun_boyu_dinlenme(tmp_path: Path) -> None:
    ilk, ikinci, ucuncu = OTOMATIK_SIRA
    gunluk_kota = YapayZekaHatasi("sınır", 429, "Quota exceeded for metric: generate_requests_per_model_per_day")
    sahte = ModeleGoreSahte({ilk: gunluk_kota})
    yz = _yz(tmp_path, sahte)
    assert yz.ayarlar.oku().model == OTOMATIK_MODEL
    assert yz.istek("s", "i", {}).model == ikinci
    assert yz.istek("s", "i", {}).model == ikinci  # ilk model bugün bir daha denenmez
    assert sahte.denenen == [ilk, ikinci, ikinci]
    assert yz.sayac.bugun() == 3  # başarısız deneme de sayılır


def test_dakikalik_sinir_kisa_dinlenme_ve_yogunlukta_dinlenme_yok(tmp_path: Path) -> None:
    ilk, ikinci, _ = OTOMATIK_SIRA
    saat = [0.0]
    secici = ModelSecici(saat=lambda: saat[0])
    secici.basarisiz(ilk, YapayZekaHatasi("sınır", 429, "Requests per minute exceeded"))
    assert ilk not in secici.adaylar(OTOMATIK_MODEL)
    saat[0] = 120.0
    assert secici.adaylar(OTOMATIK_MODEL)[0] == ilk
    assert secici.basarisiz(ikinci, YapayZekaHatasi("yoğun", 503)) is True
    assert ikinci in secici.adaylar(OTOMATIK_MODEL)
    assert secici.basarisiz(ikinci, YapayZekaHatasi("ulaşılamadı", 504)) is False  # internet yok: model değişmez
    assert secici.basarisiz(ikinci, YapayZekaHatasi("bulunamadı", 404)) is True
    assert ikinci not in secici.adaylar(OTOMATIK_MODEL)


def test_elle_secilen_model_degismez_ve_hepsi_doluysa_turkce_hata(tmp_path: Path) -> None:
    ilk, ikinci, ucuncu = OTOMATIK_SIRA
    kota = YapayZekaHatasi("sınır", 429, "per day")
    sahte = ModeleGoreSahte({ilk: kota, ikinci: kota, ucuncu: kota})
    yz = _yz(tmp_path, sahte)
    with pytest.raises(YapayZekaHatasi):
        yz.istek("s", "i", {})
    assert sahte.denenen == [ilk, ikinci, ucuncu]
    with pytest.raises(YapayZekaHatasi, match="bütün Gemini modellerinin"):
        yz.istek("s", "i", {})
    assert HEPSI_DOLU_MESAJI.startswith("Bugün")

    istemci = TestClient(sunucu_olustur(tmp_path / "veri2", kur_getirici=lambda: b""))
    assert istemci.put("/api/ayarlar/yapay-zeka", json={"model": OTOMATIK_MODEL}).status_code == 200
    assert istemci.get("/api/ayarlar/yapay-zeka").json()["modeller"][0] == OTOMATIK_MODEL
    elle = ModeleGoreSahte({ucuncu: kota})
    yz2 = _yz(tmp_path / "elle", elle)
    yz2.ayarlar.kaydet(type(yz2.ayarlar.oku())(model=ucuncu))
    with pytest.raises(YapayZekaHatasi):
        yz2.istek("s", "i", {})
    assert elle.denenen == [ucuncu]


# ---------- Gemini akış (SSE) çözümü ----------


def _sse(*olaylar: dict | str) -> list[bytes]:
    satirlar: list[bytes] = [b": yorum\n"]
    for o in olaylar:
        veri = o if isinstance(o, str) else json.dumps(o)
        satirlar += [f"event: x\n".encode(), f"data: {veri}\n".encode(), b"\n"]
    return satirlar


def test_sse_okuyucu_bitis_ve_bozuk_veriyi_atlar() -> None:
    olaylar = list(SseOkuyucu.olaylar(_sse({"event_type": "a"}, "{bozuk", "[DONE]")))
    assert olaylar == [{"event_type": "a"}]


def test_gemini_akisi_arac_cagrisi_ve_dusunce_imzasi() -> None:
    gonderilen: list[dict] = []
    olaylar = [
        {"event_type": "interaction.created", "interaction": {"id": "v1"}},
        {"event_type": "step.start", "index": 0, "step": {"type": "thought"}},
        {"event_type": "step.delta", "index": 0, "delta": {"type": "thought_signature", "signature": "imza"}},
        {"event_type": "step.stop", "index": 0},
        {"event_type": "step.start", "index": 1, "step": {"type": "function_call", "id": "f1", "name": "katalogda_ara", "arguments": {}}},
        {"event_type": "step.delta", "index": 1, "delta": {"type": "arguments_delta", "arguments": "{\"metin\": "}},
        {"event_type": "step.delta", "index": 1, "delta": {"type": "arguments_delta", "arguments": "\"F60\"}"}},
        {"event_type": "step.stop", "index": 1},
        {"event_type": "bilinmeyen.olay"},
        {"event_type": "interaction.completed", "interaction": {"status": "requires_action", "usage": {"total_tokens": 5}}},
    ]

    def akis_gonder(govde: dict):
        gonderilen.append(govde)
        return iter(olaylar)

    g = GeminiSaglayicisi(SAHTE_ANAHTAR, akis_gonder=akis_gonder)
    sonuc = list(g.sohbet_et("sistem", [{"type": "user_input", "content": []}], [AracTanimi("katalogda_ara", "ara")]))
    assert [o.tur for o in sonuc] == [OLAY_ARAC_CAGRISI, OLAY_BITTI]
    assert sonuc[0].cagri == AracCagrisi("f1", "katalogda_ara", {"metin": "F60"})
    assert sonuc[1].adimlar[0] == {"type": "thought", "signature": "imza"}
    assert sonuc[1].adimlar[1]["arguments"] == {"metin": "F60"}
    assert sonuc[1].durum == "requires_action" and sonuc[1].kullanim == {"total_tokens": 5}
    govde = gonderilen[0]
    assert govde["stream"] is True and govde["store"] is False
    assert govde["tools"][0]["type"] == "function" and govde["generation_config"]["tool_choice"] == ARAC_SERBEST
    assert SAHTE_ANAHTAR not in json.dumps(govde)


def test_gemini_akisi_metin_ve_akis_ici_kota_hatasi() -> None:
    metin = [
        {"event_type": "step.start", "index": 0, "step": {"type": "model_output"}},
        {"event_type": "step.delta", "index": 0, "delta": {"type": "text", "text": "Mer"}},
        {"event_type": "step.delta", "index": 0, "delta": {"type": "text", "text": "haba"}},
        {"event_type": "step.stop", "index": 0},
    ]
    g = GeminiSaglayicisi(SAHTE_ANAHTAR, akis_gonder=lambda govde: iter(metin))
    sonuc = list(g.sohbet_et("s", [], []))
    assert [o.metin for o in sonuc if o.tur == OLAY_METIN] == ["Mer", "haba"]
    assert sonuc[-1].adimlar == [{"type": "model_output", "content": [{"type": "text", "text": "Merhaba"}]}]

    hatali = [{"event_type": "error", "error": {"code": "resource_exhausted", "message": "per day"}}]
    g2 = GeminiSaglayicisi(SAHTE_ANAHTAR, akis_gonder=lambda govde: iter(hatali))
    with pytest.raises(YapayZekaHatasi) as hata:
        list(g2.sohbet_et("s", [], []))
    assert hata.value.http_kodu == 429 and hata.value.ayrinti == "per day"


def test_gemini_akissiz_sohbet_adimlari_oldugu_gibi() -> None:
    adimlar = [{"type": "thought", "signature": "s"}, {"type": "function_call", "id": "f", "name": "a", "arguments": {"x": 1}}]
    g = GeminiSaglayicisi(SAHTE_ANAHTAR, gonder=lambda govde: {"status": "requires_action", "steps": adimlar})
    sonuc = list(g.sohbet_et("s", [], [AracTanimi("a", "b")], akis=False, arac_kullanimi=ARAC_YASAK))
    assert sonuc[0].cagri == AracCagrisi("f", "a", {"x": 1}) and sonuc[-1].adimlar == adimlar
