"""elektronik/hesap uyum kontrolleri (K1–K13) ve şasiden pervane tahmini için testler."""

from dataclasses import replace

import pytest

from elektronik.hesap.sasi_pervane import EnBuyukPervaneTahmincisi
from elektronik.hesap.uyum import UyumDurumu as D, aralik_durumu
from elektronik.hesap.uyumluluk import VARSAYILAN_KONTROLLER, UyumlulukKontrolcusu
from elektronik.parcalar.cekirdek_parcalar import Alici, Esc, GucDagitim, Motor, Pervane, Pil, UcusKarti
from elektronik.parcalar.diger_parca import DigerParca
from elektronik.parcalar.turler import DigerAltTur, PilKimyasi
from sasi.modeller import SasiOlculeri

# Bilinen, uyumlu bir 5 inç yarış quad'ı.
MOTOR = Motor(uretici="T-Motor", model="F60", agirlik_g=33.5, kv=1950, maks_akim_a=35, min_s=4, maks_s=6,
              onerilen_pervane_min_inc=4.5, onerilen_pervane_maks_inc=5.5)
PERVANE = Pervane(uretici="HQ", model="5.1x4.3x3", agirlik_g=4.5, cap_inc=5.1, hatve_inc=4.3, kanat_sayisi=3)
ESC = Esc(uretici="Tekko", model="F4 4in1 50A", agirlik_g=15, surekli_akim_a=50, tepe_akim_a=60, min_s=3, maks_s=6,
          protokoller=["DShot600", "DShot300"], montaj_olcusu_mm=30.5, kanal_sayisi=4, konnektor="XT60")
PIL = Pil(uretici="CNHL", model="1500 6S", agirlik_g=240, hucre_sayisi_s=6, kapasite_mah=1500, desarj_c=120,
          konnektor="XT60", kimya=PilKimyasi.LIPO)
FC = UcusKarti(uretici="Matek", model="F405", agirlik_g=8, montaj_olcusu_mm=30.5, giris_gerilimi_min_v=7,
               giris_gerilimi_maks_v=36, esc_protokolleri=["dshot-600", "Oneshot125"], alici_protokolleri=["CRSF", "SBUS"],
               uart_sayisi=5, bec_cikislari_v=[5.0, 9.0])
ALICI = Alici(uretici="BetaFPV", model="ELRS Nano", agirlik_g=2, protokol="CRSF", besleme_gerilimi_v=5, baglanti="UART")


def _quad(**degisen) -> list:
    """Tam quad; anahtar verilen parça (motor=, pil=…) yerine geçer, None verilirse çıkarılır."""
    parcalar = {"motor": (MOTOR, 4), "pervane": (PERVANE, 4), "esc": (ESC, 1), "pil": (PIL, 1), "fc": (FC, 1), "alici": (ALICI, 1)}
    for ad, deger in degisen.items():
        parcalar[ad] = deger if deger is None or isinstance(deger, tuple) else (deger, parcalar[ad][1])
    return [k for k in parcalar.values() if k is not None]


def _sonuclar(kalemler, motor_sayisi=4, sasi=None) -> dict:
    return {s.kod: s for s in UyumlulukKontrolcusu().kontrol_et(kalemler, motor_sayisi, sasi)}


def _durum(kod: str, kalemler, **ek) -> D:
    return _sonuclar(kalemler, **ek)[kod].durum


# ---------- Genel ----------


def test_bilinen_quad_tum_kontroller_uygun_sasisiz_k5_bilinmiyor() -> None:
    s = _sonuclar(_quad())
    assert len(s) == len(VARSAYILAN_KONTROLLER) == 13
    assert {k: v.durum for k, v in s.items() if v.durum is not D.UYGUN} == {"K5": D.BILINMIYOR}
    assert s["K5"].tahmini and "Şasi" in s["K5"].aciklama


def test_bos_drone_cokmez_ve_uygun_demez() -> None:
    s = _sonuclar([])
    assert s["K11"].durum is D.UYGUNSUZ
    assert all(v.durum is D.BILINMIYOR for k, v in s.items() if k not in ("K11", "K13"))


def test_eksik_veri_hicbir_zaman_uygun_sayilmaz() -> None:
    """Teknik değerleri boş parçalarla, sayıma dayanmayan hiçbir kontrol 'uygun' olamaz."""
    bos = [(Motor(uretici="M", model="1"), 4), (Pervane(uretici="P", model="1"), 4), (Esc(uretici="E", model="1"), 1),
           (Pil(uretici="B", model="1"), 1), (UcusKarti(uretici="F", model="1"), 1), (Alici(uretici="R", model="1"), 1)]
    s = _sonuclar(bos, sasi=SasiOlculeri(birim="mm", en_mm=200, boy_mm=200, yukseklik_mm=30))
    uygunlar = {k for k, v in s.items() if v.durum is D.UYGUN}
    assert uygunlar <= {"K11", "K13"}  # motor sayısı ve "ikinci grup parça yok" veriye dayanmaz


def test_aralik_durumu() -> None:
    assert aralik_durumu(6, 4, 6) is D.UYGUN
    assert aralik_durumu(3, 4, None) is D.UYGUNSUZ  # bilinen alt sınırın altında: kesin uyumsuz
    assert aralik_durumu(5, 4, None) is D.BILINMIYOR
    assert aralik_durumu(None, 4, 6) is D.BILINMIYOR


# ---------- K1–K4 ----------


def test_k1_k2_hucre_sayisi() -> None:
    sekiz_s = replace(PIL, hucre_sayisi_s=8)
    sonuc = _sonuclar(_quad(pil=sekiz_s))
    assert sonuc["K1"].durum is D.UYGUNSUZ and "4–6S" in sonuc["K1"].aciklama
    assert sonuc["K2"].durum is D.UYGUNSUZ
    assert _durum("K1", _quad(motor=replace(MOTOR, maks_s=None))) is D.BILINMIYOR


def test_k3_kimya_bilinmiyorsa_tahmin_edilmez() -> None:
    fc = replace(FC, giris_gerilimi_maks_v=25.5)  # 6S LiPo 25,2 V geçer, LiHV 26,1 V geçmez
    assert _durum("K3", _quad(fc=fc)) is D.UYGUN
    sonuc = _sonuclar(_quad(fc=fc, pil=replace(PIL, kimya=None)))["K3"]
    assert sonuc.durum is D.BILINMIYOR and "kimyası" in sonuc.aciklama
    assert _durum("K3", _quad(fc=fc, pil=replace(PIL, kimya=PilKimyasi.LIHV))) is D.UYGUNSUZ
    # Kimya bilinmese de iki uçta da sığıyorsa sonuç kesindir.
    assert _durum("K3", _quad(pil=replace(PIL, kimya=None))) is D.UYGUN


def test_k3_pdb_giris_gerilimi() -> None:
    pdb = GucDagitim(uretici="Matek", model="PDB", giris_gerilimi_maks_v=18, konnektor="XT60")
    assert _durum("K3", _quad() + [(pdb, 1)]) is D.UYGUNSUZ


def test_k4_motor_pervane_stator_tahmini_yok() -> None:
    assert _durum("K4", _quad(pervane=replace(PERVANE, cap_inc=7))) is D.UYGUNSUZ
    motor = replace(MOTOR, boyut="2207", onerilen_pervane_min_inc=None, onerilen_pervane_maks_inc=None)
    assert _durum("K4", _quad(motor=motor)) is D.BILINMIYOR


# ---------- K5: şasiden pervane tahmini ----------


def test_en_buyuk_pervane_tahmini() -> None:
    olculer = SasiOlculeri(birim="mm", en_mm=200, boy_mm=200, yukseklik_mm=30)
    # köşegen 282,8 × 0,9 = 254,6; quad komşu = 254,6 × sin 45° = 180,0; − 6 = 174 mm = 6,85 inç → 6,8
    assert EnBuyukPervaneTahmincisi().tahmin_et(olculer, 4) == pytest.approx(6.8)
    # hexa: komşu = 254,6 / 2 = 127,3; − 6 = 121,3 mm = 4,78 inç → 4,7
    assert EnBuyukPervaneTahmincisi().tahmin_et(olculer, 6) == pytest.approx(4.7)
    assert EnBuyukPervaneTahmincisi().tahmin_et(SasiOlculeri(birim="mm", en_mm=5, boy_mm=5, yukseklik_mm=1), 4) is None


@pytest.mark.parametrize(("cap", "beklenen"), [(5.1, D.UYGUN), (7.0, D.UYARI), (8.0, D.UYGUNSUZ)])
def test_k5_sinira_yakin_uyari(cap: float, beklenen: D) -> None:
    sasi = SasiOlculeri(birim="mm", en_mm=200, boy_mm=200, yukseklik_mm=30)  # sınır ≈ 6,8 inç
    sonuc = _sonuclar(_quad(pervane=replace(PERVANE, cap_inc=cap)), sasi=sasi)["K5"]
    assert sonuc.durum is beklenen and sonuc.tahmini


# ---------- K6, K7: akım ----------


@pytest.mark.parametrize(("esc_akim", "beklenen"), [(50, D.UYGUN), (40, D.UYARI), (30, D.UYGUNSUZ)])
def test_k6_esc_akimi_guvenlik_payi(esc_akim: float, beklenen: D) -> None:
    # Motor 35 A → %20 payla 42 A gerekir.
    assert _durum("K6", _quad(esc=replace(ESC, surekli_akim_a=esc_akim))) is beklenen


def test_k7_pil_desarji() -> None:
    # 4 × 35 = 140 A, payla 168 A. 1,5 Ah × 120C = 180 A uygun; 1,5 × 100 = 150 A dikkat; × 80 = 120 A uyumsuz.
    assert _durum("K7", _quad()) is D.UYGUN
    assert _durum("K7", _quad(pil=replace(PIL, desarj_c=100))) is D.UYARI
    assert _durum("K7", _quad(pil=replace(PIL, desarj_c=80))) is D.UYGUNSUZ
    sonuc = _sonuclar(_quad(motor=(MOTOR, 3)))["K7"]
    assert sonuc.durum is D.BILINMIYOR and "4 motor gerekiyor" in sonuc.aciklama


# ---------- K8–K10 ----------


def test_k8_montaj() -> None:
    assert _durum("K8", _quad(esc=replace(ESC, montaj_olcusu_mm=20))) is D.UYGUNSUZ
    assert _durum("K8", _quad(esc=(replace(ESC, montaj_olcusu_mm=None, kanal_sayisi=1), 4))) is D.UYGUN  # tekli ESC
    assert _durum("K8", _quad(esc=replace(ESC, montaj_olcusu_mm=20, kanal_sayisi=None))) is D.BILINMIYOR


def test_k9_protokol_buyuk_kucuk_harf_ve_tire_farki_onemsiz() -> None:
    sonuc = _sonuclar(_quad())["K9"]
    assert sonuc.durum is D.UYGUN and "DShot600" in sonuc.aciklama  # kartta "dshot-600" yazıyor
    assert _durum("K9", _quad(esc=replace(ESC, protokoller=["PWM"]))) is D.UYGUNSUZ


def test_k10_alici() -> None:
    assert _durum("K10", _quad(alici=replace(ALICI, protokol="IBUS", baglanti=None))) is D.UYGUNSUZ
    assert _durum("K10", _quad(alici=replace(ALICI, besleme_gerilimi_v=9.0))) is D.UYGUN
    assert _durum("K10", _quad(fc=replace(FC, bec_cikislari_v=[5.0]), alici=replace(ALICI, besleme_gerilimi_v=9.0))) is D.UYGUNSUZ
    assert _durum("K10", _quad(fc=replace(FC, bec_cikislari_v=None))) is D.BILINMIYOR


def test_k10_gps_de_uart_kullanir() -> None:
    gps = DigerParca(uretici="Matek", model="M10Q", alt_tur=DigerAltTur.GPS, besleme_gerilimi_v=5)
    assert _durum("K10", _quad(fc=replace(FC, uart_sayisi=1)) + [(gps, 1)]) is D.UYGUNSUZ
    assert _durum("K10", _quad(fc=replace(FC, uart_sayisi=2)) + [(gps, 1)]) is D.UYGUN


# ---------- K11–K13 ----------


def test_k11_motor_sayisi() -> None:
    assert _durum("K11", _quad(motor=(MOTOR, 3))) is D.UYGUNSUZ
    assert _durum("K11", _quad(motor=(MOTOR, 5))) is D.UYARI
    karisik = _quad(motor=(MOTOR, 2)) + [(replace(MOTOR, model="F40"), 2)]
    assert _durum("K11", karisik) is D.UYARI
    assert _durum("K11", _quad(), motor_sayisi=6) is D.UYGUNSUZ


def test_k12_konnektor_farkliysa_yalnizca_uyari() -> None:
    assert _durum("K12", _quad(pil=replace(PIL, konnektor="XT30"))) is D.UYARI
    assert _durum("K12", _quad(pil=replace(PIL, konnektor="xt-60"))) is D.UYGUN
    # PDB varsa pil PDB'ye takılır.
    pdb = GucDagitim(uretici="Matek", model="PDB", konnektor="XT90")
    assert _durum("K12", _quad() + [(pdb, 1)]) is D.UYARI


def test_k13_ikinci_grup_gerilim() -> None:
    vtx = DigerParca(uretici="TBS", model="Unify", alt_tur=DigerAltTur.VTX, besleme_gerilimi_v=9)
    assert _durum("K13", _quad() + [(vtx, 1)]) is D.UYGUN
    assert _durum("K13", _quad() + [(replace(vtx, besleme_gerilimi_v=12), 1)]) is D.UYGUNSUZ
    assert _durum("K13", _quad() + [(replace(vtx, besleme_gerilimi_v=None), 1)]) is D.BILINMIYOR
    pdb = GucDagitim(uretici="M", model="PDB", cikis_gerilimleri_v=[12.0])
    assert _durum("K13", _quad() + [(replace(vtx, besleme_gerilimi_v=12), 1), (pdb, 1)]) is D.UYGUN


def test_birden_cok_pilde_en_kotu_sonuc_ve_ilgili_parca() -> None:
    ikinci = replace(PIL, model="1300 8S", hucre_sayisi_s=8)
    sonuc = _sonuclar(_quad() + [(ikinci, 1)])["K1"]
    assert sonuc.durum is D.UYGUNSUZ
    assert ikinci.gorunen_ad in sonuc.ilgili_parcalar and PIL.gorunen_ad not in sonuc.ilgili_parcalar
