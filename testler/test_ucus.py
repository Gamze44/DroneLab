"""elektronik/hesap uçuş hesabı, tahmini itki ve itki tablosu için testler."""

import math
from dataclasses import replace

import pytest

from drone.modeller import KULLANIM_AMACLARI
from elektronik.hesap.agirlik import AgirlikHesaplayici, AgirlikOzeti
from elektronik.hesap.akim import EnBuyukAkimHesaplayici
from elektronik.hesap.katsayilar import HEDEF_ITKI_AGIRLIK, UCUS_TARZI_KATSAYILARI
from elektronik.hesap.tahmini_itki import TahminiItkiHesaplayici
from elektronik.hesap.ucus import UcusHesaplayici
from elektronik.parcalar.cekirdek_parcalar import ItkiNoktasi
from testler.test_uyum import MOTOR, PIL, _quad

YARIS = "FPV yarış"


def _agirlik(toplam_g: float) -> AgirlikOzeti:
    """Kablo payı olmadan, tam bilinen bir toplam ağırlık."""
    return AgirlikOzeti(sasi_g=toplam_g, parcalar_g=0, yuk_g=0, kablo_payi_g=0, toplam_g=toplam_g)


def test_katsayi_tablolari_amac_adlariyla_ayni() -> None:
    assert set(HEDEF_ITKI_AGIRLIK) <= set(KULLANIM_AMACLARI)
    assert set(UCUS_TARZI_KATSAYILARI) <= set(KULLANIM_AMACLARI)


# ---------- Tahmini itki (fizik formülü) ----------


def test_itki_katsayisi_ara_deger_ve_uclar() -> None:
    h = TahminiItkiHesaplayici()
    assert h.itki_katsayisi(10, 8) == pytest.approx(0.11)  # 0,8 → 0,10 ile 0,12 arası
    assert h.itki_katsayisi(10, 1) == pytest.approx(0.08)  # tablo altı → ilk değer
    assert h.itki_katsayisi(5, 10) == pytest.approx(0.15)  # tablo üstü → son değer


def test_tahmini_itki_elle_hesapla_ayni_ve_makul() -> None:
    """5,1x4,3 pervane, 1950 KV, 6S (22,2 V): formül elle hesapla aynı ve gerçek ölçümlere (~1,5 kg) yakın."""
    itki = TahminiItkiHesaplayici().en_buyuk_itki_g(kv=1950, gerilim_v=22.2, cap_inc=5.1, hatve_inc=4.3)
    devir = 1950 * 22.2 * 0.8 / 60
    c_t = 0.10 + 0.02 * ((4.3 / 5.1) - 0.7) / 0.2
    beklenen = c_t * 1.225 * devir**2 * (5.1 * 0.0254) ** 4 / 9.80665 * 1000
    assert itki == pytest.approx(beklenen, rel=1e-6)
    assert 1000 < itki < 2000


def test_asili_guc_momentum_teorisi() -> None:
    guc = TahminiItkiHesaplayici().asili_guc_w(itki_g=150, cap_inc=5)
    alan = math.pi * (5 * 0.0254 / 2) ** 2
    beklenen = (0.150 * 9.80665) ** 1.5 / math.sqrt(2 * 1.225 * alan) / (0.65 * 0.8)
    assert guc == pytest.approx(beklenen, rel=1e-6)


# ---------- Uçuş özeti ----------


def test_bilinen_quad_tahmini_degerler_makul() -> None:
    agirlik = AgirlikHesaplayici().hesapla(sasi_g=120, kalemler=_quad())
    u = UcusHesaplayici().hesapla(_quad(), 4, YARIS, agirlik)
    assert u.toplam_agirlik_g.deger == pytest.approx(agirlik.toplam_g)
    assert u.toplam_itki_g.tahmini and u.toplam_itki_g.deger > 4000
    assert 7 < u.itki_agirlik_orani.deger < 15 and u.hedef_itki_agirlik == 7 and u.hedefe_ulasiyor_mu
    assert 20 < u.asili_gaz_yuzde.deger < 45
    assert 2 < u.asili_akim_a.deger < 10
    assert u.toplam_maks_akim_a.deger == 140  # 4 × 35 A
    assert u.ucus_suresi_dk.tahmini and 3 < u.ucus_suresi_dk.deger < 15
    assert u.notlar == []


def test_itki_tablosu_varsa_tablodan_ve_dogru_gerilimden() -> None:
    tablo = [
        ItkiNoktasi(gerilim_v=14.8, gaz_yuzde=100, itki_g=900, akim_a=20),
        ItkiNoktasi(gerilim_v=22.2, gaz_yuzde=50, itki_g=600, akim_a=8),
        ItkiNoktasi(gerilim_v=22.2, gaz_yuzde=100, itki_g=1500, akim_a=35),
    ]
    kalemler = _quad(motor=replace(MOTOR, itki_tablosu=tablo))
    u = UcusHesaplayici().hesapla(kalemler, 4, YARIS, _agirlik(1500))
    assert u.toplam_itki_g.deger == 6000 and not u.toplam_itki_g.tahmini
    assert u.itki_agirlik_orani.deger == pytest.approx(4.0) and not u.itki_agirlik_orani.tahmini
    assert not u.hedefe_ulasiyor_mu  # yarış hedefi 7
    # Motor başına 375 g: (0,0)–(50 %, 600 g) arasında → 31,25 % gaz, 5 A.
    assert u.asili_gaz_yuzde.deger == pytest.approx(31.25)
    assert u.asili_akim_a.deger == pytest.approx(20.0) and not u.asili_akim_a.tahmini
    assert u.ucus_suresi_dk.tahmini  # uçuş süresi her zaman tahmini
    assert u.ucus_suresi_dk.deger == pytest.approx(1.5 * 0.8 / (20 * 3.0) * 60)


def test_eksik_degerler_uydurulmaz_nedeni_yazilir() -> None:
    u = UcusHesaplayici().hesapla(_quad(pil=None), 4, YARIS, _agirlik(600))
    assert u.toplam_itki_g.deger is None and "Pil eklenmedi" in u.toplam_itki_g.aciklama
    assert u.itki_agirlik_orani.deger is None and u.hedefe_ulasiyor_mu is None
    assert u.ucus_suresi_dk.deger is None

    u = UcusHesaplayici().hesapla(_quad(motor=replace(MOTOR, kv=None)), 4, YARIS, _agirlik(600))
    assert u.toplam_itki_g.deger is None and "KV" in u.toplam_itki_g.aciklama


def test_kimya_girilmezse_kabul_notu() -> None:
    u = UcusHesaplayici().hesapla(_quad(pil=replace(PIL, kimya=None)), 4, YARIS, _agirlik(600))
    assert u.toplam_itki_g.deger is not None
    assert any("kimyası" in n for n in u.notlar)


def test_itki_yetmezse_asili_kalma_hesaplanmaz() -> None:
    u = UcusHesaplayici().hesapla(_quad(), 4, YARIS, _agirlik(50_000))
    assert u.itki_agirlik_orani.deger < 1
    assert u.asili_gaz_yuzde.deger is None and "yetmiyor" in u.asili_gaz_yuzde.aciklama


def test_agirlik_yoksa_oran_hesaplanmaz() -> None:
    u = UcusHesaplayici().hesapla([], 4, YARIS, AgirlikHesaplayici().hesapla(None, []))
    assert u.toplam_agirlik_g.deger is None and u.itki_agirlik_orani.deger is None


# ---------- Toplam en büyük akım ----------


def test_toplam_akim() -> None:
    h = EnBuyukAkimHesaplayici()
    assert h.hesapla(_quad(), 4).toplam_a == 140
    assert h.hesapla(_quad(motor=(MOTOR, 5)), 4).toplam_a == 140  # yedek motor sayılmaz
    assert h.hesapla(_quad(motor=replace(MOTOR, maks_akim_a=None)), 4).toplam_a is None
    assert "motor eklenmedi" in h.hesapla([], 4).eksik
