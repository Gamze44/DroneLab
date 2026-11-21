"""elektronik/zorunlu_parcalar.py ve elektronik/hesap/agirlik.py için testler."""

import pytest

from drone.modeller import KULLANIM_AMACLARI
from elektronik.hesap.agirlik import AgirlikHesaplayici
from elektronik.parcalar.cekirdek_parcalar import Alici, Esc, GucDagitim, Motor, Pervane, Pil, UcusKarti
from elektronik.parcalar.diger_parca import DigerParca
from elektronik.parcalar.turler import DigerAltTur
from elektronik.zorunlu_parcalar import GPS_ONERILEN_AMACLAR, ZorunluParcaDenetleyici, ZorunlulukDurumu as Z

YARIS = "FPV yarış"


def _durumlar(kalemler, motor_sayisi=4, amac=YARIS) -> dict[str, Z]:
    return {z.etiket: z.durum for z in ZorunluParcaDenetleyici().denetle(kalemler, motor_sayisi, amac)}


def _tam_quad(esc_kanal: int | None = 4) -> list:
    return [
        (Motor(uretici="M", model="1"), 4),
        (Pervane(uretici="P", model="1"), 4),
        (Esc(uretici="E", model="1", kanal_sayisi=esc_kanal), 1),
        (Pil(uretici="B", model="1"), 1),
        (UcusKarti(uretici="F", model="1"), 1),
        (Alici(uretici="R", model="1"), 1),
    ]


def test_bos_drone_her_sey_eksik() -> None:
    d = _durumlar([])
    assert d["Motor"] is Z.EKSIK and d["Pil"] is Z.EKSIK and d["ESC (hız kontrolcüsü)"] is Z.EKSIK
    assert d["Güç dağıtım kartı (PDB)"] is Z.BILINMIYOR  # ESC belli değil
    assert "GPS" not in d  # yarış dronunda GPS önerilmez


def test_tam_quad_4u1_arada_esc_ile() -> None:
    d = _durumlar(_tam_quad())
    assert all(v is Z.TAMAM for k, v in d.items() if k != "Güç dağıtım kartı (PDB)")
    assert d["Güç dağıtım kartı (PDB)"] is Z.ISTEGE_BAGLI


def test_motor_sayisi_drone_turune_gore() -> None:
    """Hexacopter için 4 motor yetmez."""
    sonuc = {z.etiket: z for z in ZorunluParcaDenetleyici().denetle(_tam_quad(), 6, YARIS)}
    assert sonuc["Motor"].durum is Z.EKSIK and "2 eksik" in sonuc["Motor"].aciklama
    assert sonuc["ESC (hız kontrolcüsü)"].durum is Z.EKSIK  # 4 kanal < 6


def test_esc_kanal_bilinmiyorsa_tahmin_edilmez() -> None:
    d = _durumlar(_tam_quad(esc_kanal=None))
    assert d["ESC (hız kontrolcüsü)"] is Z.BILINMIYOR
    assert d["Güç dağıtım kartı (PDB)"] is Z.BILINMIYOR


def test_tekli_esc_pdb_ister_dahili_pdb_istemez() -> None:
    kalemler = [k for k in _tam_quad() if not isinstance(k[0], Esc)] + [(Esc(uretici="E", model="tek", kanal_sayisi=1), 4)]
    d = _durumlar(kalemler)
    assert d["ESC (hız kontrolcüsü)"] is Z.TAMAM
    assert d["Güç dağıtım kartı (PDB)"] is Z.EKSIK

    d = _durumlar(kalemler + [(GucDagitim(uretici="G", model="1"), 1)])
    assert d["Güç dağıtım kartı (PDB)"] is Z.TAMAM

    pdbli_fc = [k for k in kalemler if not isinstance(k[0], UcusKarti)] + [(UcusKarti(uretici="F", model="2", dahili_pdb=True), 1)]
    assert _durumlar(pdbli_fc)["Güç dağıtım kartı (PDB)"] is Z.ISTEGE_BAGLI


def test_gps_amaca_gore_onerilir() -> None:
    assert GPS_ONERILEN_AMACLAR <= set(KULLANIM_AMACLARI)  # adlar drone modeliyle aynı olmalı
    assert _durumlar(_tam_quad(), amac="Yük taşıma")["GPS"] is Z.ONERILEN
    gps = (DigerParca(uretici="Matek", model="M10Q", alt_tur=DigerAltTur.GPS), 1)
    assert _durumlar(_tam_quad() + [gps], amac="Yük taşıma")["GPS"] is Z.TAMAM


# ---------- Ağırlık ----------


def test_agirlik_toplami_adetle_ve_payla() -> None:
    kalemler = [(Motor(uretici="M", model="1", agirlik_g=33.5), 4), (Pil(uretici="B", model="1", agirlik_g=200), 1)]
    o = AgirlikHesaplayici(kablo_payi_orani=0.05).hesapla(sasi_g=100, kalemler=kalemler, yuk_g=50)
    assert o.parcalar_g == pytest.approx(334)
    assert o.kablo_payi_g == pytest.approx((334 + 100) * 0.05)
    assert o.toplam_g == pytest.approx(100 + 334 + 50 + 21.7)
    assert o.eksiksiz_mi and o.tahmini


def test_agirligi_bilinmeyen_parca_toplama_katilmaz_ve_listelenir() -> None:
    kalemler = [(Motor(uretici="M", model="1", agirlik_g=30), 4), (Esc(uretici="E", model="X"), 1)]
    o = AgirlikHesaplayici(kablo_payi_orani=0).hesapla(sasi_g=None, kalemler=kalemler)
    assert o.toplam_g == pytest.approx(120)
    assert o.agirligi_eksik_parcalar == ["E X"]
    assert not o.eksiksiz_mi and not o.tahmini
