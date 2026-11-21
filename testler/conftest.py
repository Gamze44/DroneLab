"""
Testlerde ortak kullanılan örnek şasi dosyası üreticileri.

Örnek dosyalar depoda tutulmaz; her test çalışırken geçici klasörde üretilir.
"""

from pathlib import Path

import ezdxf
import pytest
import trimesh

KUTU_OLCULERI = (250.0, 250.0, 40.0)


@pytest.fixture
def kutu_agi() -> trimesh.Trimesh:
    """250 × 250 × 40 boyutlu kapalı bir kutu ağı (hacim 2.500.000)."""
    return trimesh.creation.box(extents=KUTU_OLCULERI)


@pytest.fixture
def stl_dosyasi(tmp_path: Path, kutu_agi: trimesh.Trimesh) -> Path:
    """Birim bilgisi olmayan STL dosyası."""
    yol = tmp_path / "sasi.stl"
    kutu_agi.export(yol)
    return yol


@pytest.fixture
def obj_dosyasi(tmp_path: Path, kutu_agi: trimesh.Trimesh) -> Path:
    """Birim bilgisi olmayan OBJ dosyası."""
    yol = tmp_path / "sasi.obj"
    kutu_agi.export(yol)
    return yol


@pytest.fixture
def uc_mf_dosyasi(tmp_path: Path, kutu_agi: trimesh.Trimesh) -> Path:
    """Birimi milimetre olarak yazılmış 3MF dosyası."""
    yol = tmp_path / "sasi.3mf"
    kutu_agi.export(yol)
    return yol


@pytest.fixture
def levha_dxf(tmp_path: Path) -> Path:
    """
    200 × 100 mm dikdörtgen levha, içinde yarıçapı 10 olan 2 delik.

    Net alan = 20000 - 2·π·100. Birim mm ($INSUNITS = 4).
    """
    belge = ezdxf.new()
    belge.header["$INSUNITS"] = 4
    msp = belge.modelspace()
    msp.add_lwpolyline([(0, 0), (200, 0), (200, 100), (0, 100)], close=True)
    msp.add_circle((50, 50), radius=10)
    msp.add_circle((150, 50), radius=10)
    msp.add_text("ETIKET", dxfattribs={"insert": (5, 5)})
    yol = tmp_path / "levha.dxf"
    belge.saveas(yol)
    return yol


@pytest.fixture
def parcali_dxf(tmp_path: Path) -> Path:
    """
    Fusion tarzı, LINE ve ARC parçalarından oluşan, birimsiz levha çizimi.

    Şekil: 100 × 50 dikdörtgenin sağ kenarı yerine yarım daire (yarıçap 25).
    Alan = 100·50 + π·25²/2. Parçalar karışık sırada ve yönde çizilmiştir.
    """
    belge = ezdxf.new()
    belge.header["$INSUNITS"] = 0
    msp = belge.modelspace()
    msp.add_line((0, 50), (0, 0))
    msp.add_arc(center=(100, 25), radius=25, start_angle=-90, end_angle=90)
    msp.add_line((0, 0), (100, 0))
    msp.add_line((0, 50), (100, 50))  # ters yönde çizilmiş üst kenar
    yol = tmp_path / "parcali.dxf"
    belge.saveas(yol)
    return yol
