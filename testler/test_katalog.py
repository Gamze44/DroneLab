"""elektronik/katalog.py için testler."""

from pathlib import Path
import sqlite3

import pytest

from cekirdek.hatalar import GecersizDegerHatasi, KayitBulunamadiHatasi, KayitZatenVarHatasi
from depolama.veritabani import Veritabani
from elektronik.katalog import ParcaKatalogu
from elektronik.parcalar.cekirdek_parcalar import Esc, ItkiNoktasi, Motor, Pil
from elektronik.parcalar.diger_parca import DigerParca
from elektronik.parcalar.turler import DigerAltTur, ParcaTuru


@pytest.fixture
def vt(tmp_path: Path) -> Veritabani:
    return Veritabani(tmp_path / "veri" / "dronelar.sqlite3")


@pytest.fixture
def katalog(vt: Veritabani) -> ParcaKatalogu:
    return ParcaKatalogu(vt)


def _motor(**ek) -> Motor:
    return Motor(uretici="T-Motor", model="F60 Pro V 1950KV", agirlik_g=33.5, kv=1950, **ek)


def test_ekle_ve_getir(katalog: ParcaKatalogu) -> None:
    itki = [ItkiNoktasi(gerilim_v=25.2, gaz_yuzde=100, itki_g=1450)]
    kayitli = katalog.ekle(_motor(itki_tablosu=itki, kaynak_url="https://ornek.com/f60"))
    assert kayitli.kimlik is not None
    geri = katalog.getir(kayitli.kimlik)
    assert isinstance(geri, Motor)
    assert geri == kayitli
    assert geri.itki_tablosu == itki
    assert geri.maks_akim_a is None  # girilmeyen değer uydurulmadı
    assert geri.dogrulandi is False


def test_ayni_parca_iki_kez_eklenemez(katalog: ParcaKatalogu) -> None:
    ilk = katalog.ekle(_motor())
    with pytest.raises(KayitZatenVarHatasi) as bilgi:
        katalog.ekle(Motor(uretici="tmotor", model="F60 PRO V 1950 KV"))
    assert bilgi.value.mevcut_kimlik == ilk.kimlik
    assert "zaten kayıtlı" in bilgi.value.mesaj


def test_ayni_marka_model_farkli_tur_eklenebilir(katalog: ParcaKatalogu) -> None:
    katalog.ekle(Motor(uretici="X", model="1"))
    katalog.ekle(Esc(uretici="X", model="1"))
    katalog.ekle(DigerParca(uretici="X", model="1", alt_tur=DigerAltTur.GPS))
    katalog.ekle(DigerParca(uretici="X", model="1", alt_tur=DigerAltTur.KAMERA))
    assert len(katalog.ara()) == 4


def test_kimlikli_parca_eklenemez(katalog: ParcaKatalogu) -> None:
    kayitli = katalog.ekle(_motor())
    with pytest.raises(GecersizDegerHatasi):
        katalog.ekle(kayitli)


def test_ayni_parcayi_bul(katalog: ParcaKatalogu) -> None:
    assert katalog.ayni_parcayi_bul(_motor()) is None
    kayitli = katalog.ekle(_motor())
    assert katalog.ayni_parcayi_bul(Motor(uretici="T MOTOR", model="f60-pro-v-1950kv")) == kayitli


def test_getir_olmayan(katalog: ParcaKatalogu) -> None:
    with pytest.raises(KayitBulunamadiHatasi):
        katalog.getir(999)


def test_ara_metin_ve_filtreler(katalog: ParcaKatalogu) -> None:
    katalog.ekle(_motor())
    katalog.ekle(Motor(uretici="iFlight", model="XING2 2207 1855KV"))
    esc = katalog.ekle(Esc(uretici="T-Motor", model="F55A Pro II"))
    katalog.ekle(Pil(uretici="CNHL", model="Black 1300 6S"))
    katalog.dogrula(esc.kimlik)

    assert {p.model for p in katalog.ara("t-motor")} == {"F60 Pro V 1950KV", "F55A Pro II"}
    assert [p.model for p in katalog.ara("tmotor f60")] == ["F60 Pro V 1950KV"]
    assert [p.model for p in katalog.ara("2207")] == ["XING2 2207 1855KV"]
    assert {p.model for p in katalog.ara(tur=ParcaTuru.MOTOR)} == {"F60 Pro V 1950KV", "XING2 2207 1855KV"}
    assert [p.model for p in katalog.ara("tmotor", yalnizca_dogrulanmis=True)] == ["F55A Pro II"]
    assert katalog.ara("yok-boyle-bir-sey") == []
    assert len(katalog.ara(sinir=2)) == 2


def test_ara_ozel_karakterler_sorguyu_bozmaz(katalog: ParcaKatalogu) -> None:
    """% ve _ gibi SQL joker karakterleri her şeyle eşleşmemeli; tırnak da hata vermemeli."""
    katalog.ekle(_motor())
    assert katalog.ara("%") == katalog.ara()  # sadeleşince boş kalır -> filtre yok
    assert katalog.ara("x' OR 1=1 --") == []


def test_ara_alt_tur(katalog: ParcaKatalogu) -> None:
    katalog.ekle(DigerParca(uretici="Foxeer", model="Razer Mini", alt_tur=DigerAltTur.KAMERA))
    katalog.ekle(DigerParca(uretici="Matek", model="M10Q", alt_tur=DigerAltTur.GPS))
    assert [p.model for p in katalog.ara(alt_tur=DigerAltTur.GPS)] == ["M10Q"]


def test_guncelle(katalog: ParcaKatalogu) -> None:
    kayitli = katalog.ekle(_motor())
    kayitli.maks_akim_a = 45.0
    kayitli.notlar = "tartıldı"
    guncel = katalog.guncelle(kayitli)
    assert guncel.maks_akim_a == 45.0 and guncel.notlar == "tartıldı"
    assert katalog.getir(kayitli.kimlik).maks_akim_a == 45.0


def test_guncelle_cakisma_ve_tur_degisimi(katalog: ParcaKatalogu) -> None:
    a = katalog.ekle(_motor())
    b = katalog.ekle(Motor(uretici="iFlight", model="XING2"))
    b.uretici, b.model = "T-Motor", "F60 Pro V 1950KV"
    with pytest.raises(KayitZatenVarHatasi) as bilgi:
        katalog.guncelle(b)
    assert bilgi.value.mevcut_kimlik == a.kimlik

    esc = Esc(uretici="T-Motor", model="F60 Pro V 1950KV", kimlik=a.kimlik)
    with pytest.raises(GecersizDegerHatasi, match="türü değiştirilemez"):
        katalog.guncelle(esc)

    with pytest.raises(GecersizDegerHatasi, match="kimliği yok"):
        katalog.guncelle(_motor())
    with pytest.raises(KayitBulunamadiHatasi):
        katalog.guncelle(_motor(kimlik=999))


def test_dogrula(katalog: ParcaKatalogu) -> None:
    kayitli = katalog.ekle(_motor())
    assert katalog.dogrula(kayitli.kimlik).dogrulandi is True
    with pytest.raises(KayitBulunamadiHatasi):
        katalog.dogrula(999)


def test_katalog_veri_klasorundeki_dosyada(tmp_path: Path) -> None:
    """Katalog, dronelarla aynı veri/dronelar.sqlite3 dosyasında saklanmalı ve kalıcı olmalı."""
    yol = tmp_path / "veri" / "dronelar.sqlite3"
    ParcaKatalogu(Veritabani(yol)).ekle(_motor())
    assert yol.is_file()
    assert [p.model for p in ParcaKatalogu(Veritabani(yol)).ara()] == ["F60 Pro V 1950KV"]


def test_drone_parcalari_kisitlari(vt: Veritabani, katalog: ParcaKatalogu) -> None:
    """Kullanımdaki parça silinemez; drone silinince bağları silinir; adet > 0 olmalı."""
    parca = katalog.ekle(_motor())
    with vt.baglanti() as bag:
        bag.execute(
            "INSERT INTO dronelar (ad, baslangic_turu, drone_turu, amac, olusturma_zamani, guncelleme_zamani) "
            "VALUES ('D', 'sifirdan', 'quadcopter', 'FPV yarış', 't', 't')"
        )
        bag.execute(
            "INSERT INTO drone_parcalari (drone_kimlik, parca_kimlik, adet, durum, eklenme_zamani) "
            "VALUES (1, ?, 4, 'elimde', 't')", (parca.kimlik,)
        )
    with pytest.raises(sqlite3.IntegrityError):
        with vt.baglanti() as bag:
            bag.execute("DELETE FROM parcalar WHERE kimlik = ?", (parca.kimlik,))
    with pytest.raises(sqlite3.IntegrityError):
        with vt.baglanti() as bag:
            bag.execute(
                "INSERT INTO drone_parcalari (drone_kimlik, parca_kimlik, adet, durum, eklenme_zamani) "
                "VALUES (1, ?, 0, 'elimde', 't')", (parca.kimlik,)
            )
    with vt.baglanti() as bag:
        bag.execute("DELETE FROM dronelar WHERE kimlik = 1")
        assert bag.execute("SELECT COUNT(*) FROM drone_parcalari").fetchone()[0] == 0
