"""depolama paketi için testler (veritabanı, şasi kaydı, dosya deposu, serileştirme)."""

from pathlib import Path
import sqlite3

import pytest

from cekirdek.hatalar import DroneProgramHatasi, KayitBulunamadiHatasi
from depolama.dosya_deposu import SasiDosyaDeposu
from depolama.drone_deposu import DroneDeposu
from depolama.sasi_kayit_deposu import SasiKayitDeposu
from depolama.serilestirme import SasiSerilestirici
from depolama.veritabani import SEMA_SURUMU, Veritabani
from drone.modeller import BaslangicTuru, DroneTuru
from sasi.modeller import GeometriTuru, SasiGeometrisi, SasiOlculeri


@pytest.fixture
def vt(tmp_path: Path) -> Veritabani:
    return Veritabani(tmp_path / "test.sqlite3")


def _geometri() -> SasiGeometrisi:
    return SasiGeometrisi(
        dosya_adi="şasi.stl", tur=GeometriTuru.KATI, olculer=(250, 250, 40),
        hacim=2_500_000, ucgen_sayisi=12, govde_sayisi=1, uyarilar=["örnek uyarı"], ag=object(),
    )


def test_drone_olustur_getir_listele(vt: Veritabani) -> None:
    depo = DroneDeposu(vt)
    a = depo.olustur("A", BaslangicTuru.SIFIRDAN, DroneTuru.QUADCOPTER, "FPV yarış")
    b = depo.olustur("B", BaslangicTuru.ELIMDEKI, DroneTuru.HEXACOPTER, "Yük taşıma")
    assert depo.getir(a.kimlik).ad == "A"
    assert b.motor_sayisi == 6
    assert not b.sasi_var
    # Aynı saniyede oluşturulanlarda son oluşturulan üstte olmalı.
    assert [d.ad for d in depo.listele()] == ["B", "A"]


def test_drone_sil_ve_bulunamadi(vt: Veritabani) -> None:
    depo = DroneDeposu(vt)
    d = depo.olustur("A", BaslangicTuru.SIFIRDAN, DroneTuru.QUADCOPTER, "FPV yarış")
    depo.sil(d.kimlik)
    with pytest.raises(KayitBulunamadiHatasi):
        depo.getir(d.kimlik)
    with pytest.raises(KayitBulunamadiHatasi):
        depo.sil(d.kimlik)


def test_sasi_kaydi_ve_cascade_silme(vt: Veritabani) -> None:
    """Drone silinince şasi kaydı da silinmeli (yabancı anahtar CASCADE)."""
    dronelar, sasiler = DroneDeposu(vt), SasiKayitDeposu(vt)
    d = dronelar.olustur("A", BaslangicTuru.SIFIRDAN, DroneTuru.QUADCOPTER, "FPV yarış")
    sasiler.kaydet(d.kimlik, "sasi_dosyalari/1/sasi.stl", _geometri())
    assert dronelar.getir(d.kimlik).sasi_var

    kayit = sasiler.getir(d.kimlik)
    assert kayit is not None and kayit.olculer is None
    assert kayit.geometri.dosya_adi == "şasi.stl"
    assert kayit.geometri.ag is None  # ağ saklanmaz

    sasiler.olculeri_kaydet(d.kimlik, SasiOlculeri(birim="mm", en_mm=250, boy_mm=250, yukseklik_mm=40))
    assert sasiler.getir(d.kimlik).olculer.birim == "mm"

    # Yeni şasi kaydı eski birim onayını sıfırlamalı.
    sasiler.kaydet(d.kimlik, "sasi_dosyalari/1/sasi.stl", _geometri())
    assert sasiler.getir(d.kimlik).olculer is None

    dronelar.sil(d.kimlik)
    assert sasiler.getir(d.kimlik) is None


def test_yeni_surum_veritabani_reddedilir(tmp_path: Path) -> None:
    """Daha yeni şema sürümüyle oluşturulmuş dosya açılmamalı."""
    yol = tmp_path / "yeni.sqlite3"
    with sqlite3.connect(yol) as bag:
        bag.execute(f"PRAGMA user_version = {SEMA_SURUMU + 1}")
    with pytest.raises(DroneProgramHatasi, match="güncelleyin"):
        Veritabani(yol)


def test_surum_1_dosyasi_kayipsiz_yukseltilir(tmp_path: Path) -> None:
    """Eski (sürüm 1) dosya açılınca dronelar korunmalı ve parça tabloları eklenmeli."""
    from depolama.veritabani import SEMA_V1

    yol = tmp_path / "eski.sqlite3"
    with sqlite3.connect(yol) as bag:
        bag.executescript(SEMA_V1)
        bag.execute(
            "INSERT INTO dronelar (ad, baslangic_turu, drone_turu, amac, olusturma_zamani, guncelleme_zamani) "
            "VALUES ('Eski drone', 'sifirdan', 'quadcopter', 'FPV yarış', 't', 't')"
        )
        bag.execute("PRAGMA user_version = 1")
    bag.close()

    vt = Veritabani(yol)
    with vt.baglanti() as bag:
        assert bag.execute("PRAGMA user_version").fetchone()[0] == SEMA_SURUMU
        tablolar = {s[0] for s in bag.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"dronelar", "sasiler", "parcalar", "drone_parcalari"} <= tablolar
    assert [d.ad for d in DroneDeposu(vt).listele()] == ["Eski drone"]


def test_serilestirme_gidis_donus() -> None:
    s = SasiSerilestirici()
    g = s.geometriyi_oku(s.geometriyi_yaz(_geometri()))
    assert g.olculer == (250, 250, 40) and g.tur is GeometriTuru.KATI and g.uyarilar == ["örnek uyarı"]
    o = SasiOlculeri(birim="cm", en_mm=1, boy_mm=2, yukseklik_mm=3, hacim_mm3=4, uyarilar=["u"])
    assert s.olculeri_oku(s.olculeri_yaz(o)) == o


def test_dosya_deposu(tmp_path: Path) -> None:
    """Dosya sabit adla kopyalanmalı, yenisi eskisinin yerine geçmeli, silinebilmeli."""
    kaynak = tmp_path / "Benim Şasim.STL"
    kaynak.write_bytes(b"veri")
    depo = SasiDosyaDeposu(tmp_path / "veri" / "sasi_dosyalari")

    goreli = depo.kaydet(7, kaynak)
    assert goreli == "sasi_dosyalari/7/sasi.stl"
    assert depo.tam_yol(goreli).read_bytes() == b"veri"

    ikinci = tmp_path / "x.dxf"
    ikinci.write_bytes(b"dxf")
    depo.kaydet(7, ikinci)
    assert sorted(p.name for p in (tmp_path / "veri" / "sasi_dosyalari" / "7").iterdir()) == ["sasi.dxf"]

    depo.sil(7)
    assert not (tmp_path / "veri" / "sasi_dosyalari" / "7").exists()
