"""sasi/okuyucular/dxf_okuyucu.py için testler."""

import math
from pathlib import Path

import ezdxf
import pytest

from cekirdek.hatalar import DosyaOkumaHatasi
from sasi.modeller import GeometriTuru
from sasi.okuyucular.dxf_okuyucu import DxfOkuyucu

# Eğriler düz parçalara bölündüğü için alan çok az sapar; %0,1 yeterli.
ALAN_TOLERANSI = 1e-3


def test_levha_alani_delikler_cikarilarak_hesaplanir(levha_dxf: Path) -> None:
    """Dikdörtgen eksi iki dairesel delik."""
    g = DxfOkuyucu().oku(levha_dxf)
    beklenen = 200 * 100 - 2 * math.pi * 10**2
    assert g.tur is GeometriTuru.LEVHA
    assert g.alan == pytest.approx(beklenen, rel=ALAN_TOLERANSI)
    assert g.olculer == pytest.approx((200, 100, 0))
    assert g.dis_kontur_sayisi == 1
    assert g.delik_sayisi == 2
    assert g.dosya_birimi == "mm"


def test_yazi_ogeleri_uyariyla_yok_sayilir(levha_dxf: Path) -> None:
    """TEXT öğesi alana katılmamalı ve kullanıcıya bildirilmeli."""
    g = DxfOkuyucu().oku(levha_dxf)
    assert any("TEXT" in u for u in g.uyarilar)


def test_line_ve_arc_parcalari_birlestirilir(parcali_dxf: Path) -> None:
    """Karışık sırada ve yönde çizilmiş LINE/ARC parçaları tek kontur olmalı."""
    g = DxfOkuyucu().oku(parcali_dxf)
    beklenen = 100 * 50 + math.pi * 25**2 / 2
    assert g.alan == pytest.approx(beklenen, rel=ALAN_TOLERANSI)
    assert g.dis_kontur_sayisi == 1
    assert g.delik_sayisi == 0
    assert g.dosya_birimi is None
    assert g.olculer == pytest.approx((125, 50, 0))


def test_kapali_sekil_yoksa_hata_verir(tmp_path: Path) -> None:
    """Yalnızca açık bir çizgi varsa anlaşılır hata vermeli."""
    belge = ezdxf.new()
    belge.modelspace().add_line((0, 0), (100, 0))
    yol = tmp_path / "acik.dxf"
    belge.saveas(yol)
    with pytest.raises(DosyaOkumaHatasi, match="kapalı"):
        DxfOkuyucu().oku(yol)


def test_bos_cizim_hata_verir(tmp_path: Path) -> None:
    """Hiç geometrisi olmayan DXF hata vermeli."""
    yol = tmp_path / "bos.dxf"
    ezdxf.new().saveas(yol)
    with pytest.raises(DosyaOkumaHatasi, match="bulunamadı"):
        DxfOkuyucu().oku(yol)


def test_bozuk_dxf_hata_verir(tmp_path: Path) -> None:
    """DXF olmayan içerik DosyaOkumaHatasi vermeli."""
    yol = tmp_path / "bozuk.dxf"
    yol.write_text("bu bir dxf degil", encoding="utf-8")
    with pytest.raises(DosyaOkumaHatasi):
        DxfOkuyucu().oku(yol)


def test_blok_icindeki_cizim_okunur(tmp_path: Path) -> None:
    """INSERT ile yerleştirilmiş blok içindeki kontur da hesaba katılmalı."""
    belge = ezdxf.new()
    blok = belge.blocks.new(name="SASI")
    blok.add_lwpolyline([(0, 0), (80, 0), (80, 80), (0, 80)], close=True)
    belge.modelspace().add_blockref("SASI", (10, 10))
    yol = tmp_path / "blok.dxf"
    belge.saveas(yol)
    assert DxfOkuyucu().oku(yol).alan == pytest.approx(6400)
