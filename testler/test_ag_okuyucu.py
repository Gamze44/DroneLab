"""sasi/okuyucular/ag_okuyucu.py için testler."""

from pathlib import Path

import pytest
import trimesh

from cekirdek.hatalar import DosyaOkumaHatasi
from sasi.modeller import GeometriTuru
from sasi.okuyucular.ag_okuyucu import AgOkuyucu

BEKLENEN_HACIM = 250.0 * 250.0 * 40.0


@pytest.mark.parametrize("dosya_fiksturu", ["stl_dosyasi", "obj_dosyasi", "uc_mf_dosyasi"])
def test_kutu_olculeri_ve_hacmi_okunur(dosya_fiksturu: str, request: pytest.FixtureRequest) -> None:
    """STL, OBJ ve 3MF'den ölçüler ve hacim doğru okunmalı."""
    yol: Path = request.getfixturevalue(dosya_fiksturu)
    g = AgOkuyucu().oku(yol)
    assert g.tur is GeometriTuru.KATI
    assert g.olculer == pytest.approx((250, 250, 40))
    assert g.hacim == pytest.approx(BEKLENEN_HACIM)
    assert g.kapali_mi
    assert g.govde_sayisi == 1
    assert g.ucgen_sayisi == 12
    assert g.uyarilar == []


def test_stl_birim_tasimaz(stl_dosyasi: Path) -> None:
    """STL'de birim bilgisi yoktur; None dönmeli."""
    assert AgOkuyucu().oku(stl_dosyasi).dosya_birimi is None


def test_3mf_birimi_okunur(uc_mf_dosyasi: Path) -> None:
    """3MF birim taşır; milimetre 'mm' olarak gelmeli."""
    assert AgOkuyucu().oku(uc_mf_dosyasi).dosya_birimi == "mm"


def test_acik_model_uyari_verir(tmp_path: Path, kutu_agi: trimesh.Trimesh) -> None:
    """Bir yüzü eksik (kapalı olmayan) model için hacim uyarısı üretilmeli."""
    acik = kutu_agi.copy()
    acik.update_faces([i != 0 for i in range(len(acik.faces))])
    yol = tmp_path / "acik.stl"
    acik.export(yol)
    g = AgOkuyucu().oku(yol)
    assert not g.kapali_mi
    assert any("kapalı" in u for u in g.uyarilar)


def test_birden_fazla_govde_sayilir(tmp_path: Path, kutu_agi: trimesh.Trimesh) -> None:
    """Birbirine değmeyen iki kutu iki gövde olarak sayılmalı ve uyarı vermeli."""
    ikinci = trimesh.creation.box(extents=(10, 10, 10))
    ikinci.apply_translation((400, 0, 0))
    yol = tmp_path / "iki.stl"
    trimesh.util.concatenate([kutu_agi, ikinci]).export(yol)
    g = AgOkuyucu().oku(yol)
    assert g.govde_sayisi == 2
    assert any("2 ayrı parça" in u for u in g.uyarilar)


def test_bozuk_dosya_turkce_hata_verir(tmp_path: Path) -> None:
    """Geçersiz içerikli dosya DosyaOkumaHatasi vermeli."""
    yol = tmp_path / "bozuk.3mf"
    yol.write_bytes(b"bu bir 3mf dosyasi degil")
    with pytest.raises(DosyaOkumaHatasi):
        AgOkuyucu().oku(yol)
