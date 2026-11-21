"""elektronik/parcalar paketi için testler (modeller, denetim, serileştirme)."""

import json

import pytest

from cekirdek.hatalar import GecersizDegerHatasi
from elektronik.parcalar.cekirdek_parcalar import Alici, Esc, GucDagitim, ItkiNoktasi, Motor, Pervane, Pil, UcusKarti
from elektronik.parcalar.diger_parca import DigerParca
from elektronik.parcalar.drone_parcasi import DroneParcasi
from elektronik.parcalar.kayit import PARCA_SINIFLARI, parca_sinifi
from elektronik.parcalar.parca import Parca, metni_sadelestir
from elektronik.parcalar.serilestirme import ParcaSerilestirici
from elektronik.parcalar.turler import ALAN_ETIKETLERI, DigerAltTur, ParcaDurumu, ParcaTuru, PilKimyasi


def _motor(**ek) -> Motor:
    return Motor(uretici="T-Motor", model="F60 Pro V 1950KV", **ek)


# ---------- Temel davranış ----------


def test_parca_dogrudan_kullanilamaz() -> None:
    with pytest.raises(TypeError):
        Parca(uretici="A", model="B")


def test_eksik_teknik_degerler_none_kalir() -> None:
    """Hiçbir teknik değer uydurulmamalı: girilmeyen her alan None."""
    m = _motor()
    assert all(v is None for v in m.teknik_degerler().values())
    assert set(m.eksik_teknik_alanlar()) == set(Motor.teknik_alan_adlari())
    assert m.dogrulandi is False


def test_metinler_kirpilir_ve_bos_ad_none_olur() -> None:
    m = Motor(uretici="  T-Motor ", model=" F60 ", ad="   ", notlar="")
    assert (m.uretici, m.model, m.ad, m.notlar) == ("T-Motor", "F60", None, None)
    assert m.gorunen_ad == "T-Motor F60"


@pytest.mark.parametrize("alan", ["uretici", "model"])
def test_uretici_ve_model_zorunlu(alan: str) -> None:
    degerler = {"uretici": "A", "model": "B", alan: "  "}
    with pytest.raises(GecersizDegerHatasi, match="boş olamaz"):
        Motor(**degerler)


def test_tum_turler_kayitli_ve_etiketli() -> None:
    """Her tür bir sınıfa eşlenmeli; her teknik alanın Türkçe etiketi olmalı."""
    assert set(PARCA_SINIFLARI) == set(ParcaTuru)
    assert parca_sinifi("esc") is Esc
    for sinif in PARCA_SINIFLARI.values():
        for alan in sinif.teknik_alan_adlari():
            assert alan in ALAN_ETIKETLERI, f"{sinif.__name__}.{alan} etiketsiz"


# ---------- Arama anahtarı ----------


def test_arama_anahtari_yazim_farklarini_yok_sayar() -> None:
    a = Motor(uretici="T-Motor", model="F60 Pro V")
    b = Motor(uretici="tmotor", model="f60pro-v")
    assert a.arama_anahtari == b.arama_anahtari == "motor:tmotor:f60prov"


def test_turkce_harfler_sadelesir() -> None:
    assert metni_sadelestir("Işık İnce Çağrı Öğe Şüphe") == "isikincecagrioges" + "uphe"


def test_farkli_tur_farkli_anahtar() -> None:
    assert Motor(uretici="X", model="1").arama_anahtari != Esc(uretici="X", model="1").arama_anahtari
    kamera = DigerParca(uretici="X", model="1", alt_tur=DigerAltTur.KAMERA)
    gps = DigerParca(uretici="X", model="1", alt_tur="gps")
    assert kamera.arama_anahtari == "diger/kamera:x:1"
    assert kamera.arama_anahtari != gps.arama_anahtari


# ---------- Denetim ----------


@pytest.mark.parametrize(
    ("sinif", "alanlar"),
    [
        (Motor, {"kv": -1950}),
        (Motor, {"agirlik_g": 0}),
        (Pervane, {"cap_inc": float("nan")}),
        (Pil, {"kapasite_mah": float("inf")}),
        (Esc, {"surekli_akim_a": "45"}),
    ],
)
def test_gecersiz_sayilar_reddedilir(sinif: type[Parca], alanlar: dict) -> None:
    with pytest.raises(GecersizDegerHatasi):
        sinif(uretici="A", model="B", **alanlar)


def test_tamsayi_alanlari_kesirli_kabul_etmez() -> None:
    with pytest.raises(GecersizDegerHatasi, match="tam sayı"):
        Pervane(uretici="A", model="B", kanat_sayisi=2.5)
    with pytest.raises(GecersizDegerHatasi, match="tam sayı"):
        Pil(uretici="A", model="B", hucre_sayisi_s=6.0)


@pytest.mark.parametrize(
    ("sinif", "alanlar"),
    [
        (Motor, {"min_s": 6, "maks_s": 4}),
        (Esc, {"surekli_akim_a": 60, "tepe_akim_a": 45}),
        (UcusKarti, {"giris_gerilimi_min_v": 26, "giris_gerilimi_maks_v": 9}),
        (Motor, {"onerilen_pervane_min_inc": 6, "onerilen_pervane_maks_inc": 5}),
    ],
)
def test_ters_araliklar_reddedilir(sinif: type[Parca], alanlar: dict) -> None:
    with pytest.raises(GecersizDegerHatasi, match="büyük olamaz"):
        sinif(uretici="A", model="B", **alanlar)


def test_metin_listesi_temizlenir() -> None:
    esc = Esc(uretici="A", model="B", protokoller=[" DShot600 ", "DShot600", "", "DShot300"])
    assert esc.protokoller == ["DShot600", "DShot300"]
    assert Esc(uretici="A", model="B", protokoller=[]).protokoller is None


def test_karisik_liste_reddedilir() -> None:
    with pytest.raises(GecersizDegerHatasi, match="sayı olmayan"):
        UcusKarti(uretici="A", model="B", bec_cikislari_v=[5.0, "9V"])
    with pytest.raises(GecersizDegerHatasi, match="metinlerden"):
        Esc(uretici="A", model="B", protokoller=["DShot600", 600])


@pytest.mark.parametrize(
    ("sinif", "alanlar", "beklenen"),
    [
        (Motor, {"boyut": 2207}, "metin olmalı"),
        (UcusKarti, {"dahili_pdb": "evet"}, "evet/hayır"),
        (Esc, {"protokoller": "DShot600"}, "liste"),
        (Esc, {"min_s": True}, "sayı"),
    ],
)
def test_yanlis_turdeki_degerler_reddedilir(sinif: type[Parca], alanlar: dict, beklenen: str) -> None:
    """Alan türüne uymayan değer (metin alanına sayı, mantıksal alana metin…) kabul edilmemeli."""
    with pytest.raises(GecersizDegerHatasi, match=beklenen):
        sinif(uretici="A", model="B", **alanlar)


def test_bos_sayi_listesi_none_olur() -> None:
    assert UcusKarti(uretici="A", model="B", bec_cikislari_v=[]).bec_cikislari_v is None


def test_negatif_bec_reddedilir() -> None:
    with pytest.raises(GecersizDegerHatasi):
        GucDagitim(uretici="A", model="B", cikis_gerilimleri_v=[5.0, -12.0])


@pytest.mark.parametrize("url", ["javascript:alert(1)", "ftp://x", "www.ornek.com"])
def test_tehlikeli_veya_gecersiz_baglanti_reddedilir(url: str) -> None:
    with pytest.raises(GecersizDegerHatasi, match="http"):
        _motor(kaynak_url=url)


def test_pil_kimyasi_metinden_cevrilir_ve_denetlenir() -> None:
    assert Pil(uretici="A", model="B", kimya="lihv").kimya is PilKimyasi.LIHV
    with pytest.raises(GecersizDegerHatasi, match="kimyası"):
        Pil(uretici="A", model="B", kimya="kursun")


def test_diger_alt_tur_zorunlu_ve_denetlenir() -> None:
    assert DigerParca(uretici="A", model="B", alt_tur="vtx").alt_tur is DigerAltTur.VTX
    with pytest.raises(GecersizDegerHatasi, match="Alt tür"):
        DigerParca(uretici="A", model="B", alt_tur="radar")
    with pytest.raises(TypeError):
        DigerParca(uretici="A", model="B")  # alt_tur verilmedi


def test_itki_noktasi_denetimi() -> None:
    ItkiNoktasi(gerilim_v=25.2, gaz_yuzde=100, itki_g=1450, akim_a=42)
    with pytest.raises(GecersizDegerHatasi, match="en çok 100"):
        ItkiNoktasi(gerilim_v=25.2, gaz_yuzde=120, itki_g=1450)
    with pytest.raises(GecersizDegerHatasi):
        ItkiNoktasi(gerilim_v=25.2, gaz_yuzde=50, itki_g=-1)
    with pytest.raises(GecersizDegerHatasi, match="itki satırlarından"):
        _motor(itki_tablosu=[{"gerilim_v": 25.2}])


def test_drone_parcasi() -> None:
    bag = DroneParcasi(drone_kimlik=1, parca_kimlik=2, adet=4, durum="elimde")
    assert bag.durum is ParcaDurumu.ELIMDE
    for adet in (0, -1, 1.5, True):
        with pytest.raises(GecersizDegerHatasi, match="Adet"):
            DroneParcasi(drone_kimlik=1, parca_kimlik=2, adet=adet)
    with pytest.raises(GecersizDegerHatasi, match="durumu"):
        DroneParcasi(drone_kimlik=1, parca_kimlik=2, durum="kayip")


# ---------- Serileştirme ----------


def _ortak(p: Parca) -> dict:
    return {a: getattr(p, a) for a in Parca.ORTAK_ALANLAR}


@pytest.mark.parametrize(
    "parca",
    [
        _motor(kv=1950, maks_akim_a=42.5, boyut="2207", min_s=4, maks_s=6, montaj_deseni_mm=16,
               itki_tablosu=[ItkiNoktasi(gerilim_v=25.2, gaz_yuzde=100, itki_g=1450, pervane="5x4.3x3", akim_a=42)]),
        Pervane(uretici="Gemfan", model="51433", cap_inc=5.1, hatve_inc=4.33, kanat_sayisi=3),
        Esc(uretici="Holybro", model="Tekko32 F4 4in1 50A", surekli_akim_a=50, tepe_akim_a=60,
            protokoller=["DShot600"], montaj_olcusu_mm=30.5, kanal_sayisi=4, konnektor="XT60"),
        Pil(uretici="CNHL", model="1300 6S", hucre_sayisi_s=6, kapasite_mah=1300, desarj_c=100, kimya=PilKimyasi.LIPO),
        UcusKarti(uretici="SpeedyBee", model="F405 V4", bec_cikislari_v=[5.0, 9.0], dahili_pdb=False, uart_sayisi=6),
        Alici(uretici="RadioMaster", model="RP1", protokol="CRSF", besleme_gerilimi_v=5.0, baglanti="UART"),
        GucDagitim(uretici="Matek", model="PDB-XT60", maks_akim_a=184, cikis_gerilimleri_v=[5.0, 12.0]),
        DigerParca(uretici="DJI", model="O3 Air Unit", alt_tur=DigerAltTur.VTX, besleme_gerilimi_v=12.0, agirlik_g=36.4),
    ],
    ids=lambda p: p.tur.value,
)
def test_serilestirme_gidis_donus(parca: Parca) -> None:
    """JSON'a yazılıp okunan parça birebir aynı olmalı (None alanlar dahil)."""
    s = ParcaSerilestirici()
    metin = s.teknik_json(parca)
    assert set(json.loads(metin)) == set(type(parca).teknik_alan_adlari())
    assert s.parca_olustur(parca.tur, _ortak(parca), metin) == parca


def test_bilinmeyen_teknik_alan_yok_sayilir() -> None:
    """Programın başka sürümünden kalan fazladan alan okumayı bozmamalı."""
    p = ParcaSerilestirici().parca_olustur("pervane", {"uretici": "A", "model": "B"}, '{"cap_inc": 5, "eski_alan": 1}')
    assert isinstance(p, Pervane) and p.cap_inc == 5
