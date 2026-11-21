"""
Parçalı şasinin (zip) parçalarından tek bir şasi özeti ve mm ölçüleri çıkarılması.

Parçalar dosyalarda montajdaki yerlerinde durmaz; bu yüzden şasinin dış ölçüsü
doğrudan ölçülemez ve her zaman "tahmini"dir:
    - Dingil biliniyorsa: motorlar dingil çemberine eşit aralıkla dizilir; dış ölçü,
      motor yerleri + kol genişliği ile gövde ölçüsünün büyüğüdür.
    - Dingil bilinmiyorsa: en büyük gövde parçasının ölçüsü yazılır (gerçek dış ölçüden
      küçüktür; dingile bağlı hesaplar "bilinmiyor" sayılır).
Hacim (ve levhada alan) her parçanın adediyle çarpılıp toplanır.
"""

from dataclasses import replace
import math
from typing import Final

from cekirdek.birimler import BirimDonusturucu
from sasi.birim_dogrulayici import BirimDogrulayici
from sasi.modeller import (
    DingilKaynagi,
    GeometriTuru,
    ParcaRolu,
    SasiGeometrisi,
    SasiOlculeri,
    SasiParcasi,
)

PARCALI_UYARISI: Final[str] = (
    "Şasi {sayi} parça dosyasından oluşuyor. Parçalar montajlı olmadığı için dış ölçüler tahminidir."
)
DINGIL_YOK_UYARISI: Final[str] = (
    "Dingil mesafesi girilmedi: dış ölçü olarak en büyük gövde parçası gösteriliyor. "
    "Pervane sığma hesabı için dingili elle girin veya gövde ve koldan hesaplatın."
)
FARKLI_BIRIM_UYARISI: Final[str] = (
    "Parçaların dosyalarında farklı birimler yazıyor ({birimler}); tek birim seçilecek, ölçüleri kontrol edin."
)


class ParcaliSasiOzetleyici:
    """Parçalardan şasi özeti (dosya biriminde) ve mm ölçüleri (tahmini) hesaplar."""

    def __init__(self, birim_dogrulayici: BirimDogrulayici | None = None) -> None:
        self._birim_dogrulayici = birim_dogrulayici or BirimDogrulayici()

    def ozet_geometri(self, dosya_adi: str, parcalar: list[SasiParcasi], ek_uyarilar: list[str]) -> SasiGeometrisi:
        """
        Parçaların özetini tek bir SasiGeometrisi olarak döndürür (birim önerisi ve kayıt için).

        Parametreler:
            dosya_adi: Zip dosyasının adı.
            parcalar: Rol ve adetleriyle parçalar.
            ek_uyarilar: Zip okunurken oluşan uyarılar (atlanan dosyalar vb.).
        Dönüş:
            SasiGeometrisi: ölçüler = parçaların en büyük boyutları, hacim/alan = adetlerle toplam.
        """
        geometriler = [p.geometri for p in parcalar]
        katilar = [p for p in parcalar if p.geometri.tur is GeometriTuru.KATI]
        levhalar = [p for p in parcalar if p.geometri.tur is GeometriTuru.LEVHA]
        uyarilar = [PARCALI_UYARISI.format(sayi=len(parcalar)), *ek_uyarilar]

        birimler = sorted({g.dosya_birimi for g in geometriler if g.dosya_birimi})
        if len(birimler) > 1:
            uyarilar.append(FARKLI_BIRIM_UYARISI.format(birimler=", ".join(birimler)))
        for g in geometriler:
            uyarilar.extend(f"'{g.dosya_adi}': {u}" for u in g.uyarilar)

        return SasiGeometrisi(
            dosya_adi=dosya_adi,
            tur=GeometriTuru.KATI if katilar else GeometriTuru.LEVHA,
            olculer=(
                max(g.olculer[0] for g in geometriler),
                max(g.olculer[1] for g in geometriler),
                max(g.olculer[2] for g in geometriler),
            ),
            dosya_birimi=birimler[0] if len(birimler) == 1 else None,
            hacim=self._toplam(katilar, "hacim"),
            alan=self._toplam(levhalar, "alan"),
            ucgen_sayisi=sum(g.ucgen_sayisi for g in geometriler),
            govde_sayisi=len(parcalar),
            kapali_mi=all(p.geometri.kapali_mi for p in katilar),
            dis_kontur_sayisi=sum(g.dis_kontur_sayisi for g in geometriler),
            delik_sayisi=sum(g.delik_sayisi for g in geometriler),
            uyarilar=uyarilar,
        )

    def toplamlari_guncelle(self, ozet: SasiGeometrisi, parcalar: list[SasiParcasi]) -> SasiGeometrisi:
        """
        Adetler değişince özetin hacim ve alan toplamını yeniler; uyarılar korunur.

        Parametreler:
            ozet: Önceki özet.
            parcalar: Güncel adetli parçalar.
        Dönüş:
            Yeni özet.
        """
        katilar = [p for p in parcalar if p.geometri.tur is GeometriTuru.KATI]
        levhalar = [p for p in parcalar if p.geometri.tur is GeometriTuru.LEVHA]
        return replace(ozet, hacim=self._toplam(katilar, "hacim"), alan=self._toplam(levhalar, "alan"))

    def olculeri_hesapla(
        self,
        ozet: SasiGeometrisi,
        parcalar: list[SasiParcasi],
        birim: str,
        motor_sayisi: int,
        dingil_mm: float | None = None,
        dingil_kaynagi: DingilKaynagi | None = None,
    ) -> SasiOlculeri:
        """
        Onaylanan birimle parçalı şasinin mm ölçülerini hesaplar (tahmini).

        Parametreler:
            ozet: ozet_geometri ile üretilmiş özet.
            parcalar: Rol ve adetleriyle parçalar.
            birim: Kullanıcının onayladığı dosya birimi.
            motor_sayisi: Drone türüne göre motor sayısı.
            dingil_mm: Biliniyorsa dingil mesafesi, mm.
            dingil_kaynagi: Dingilin kaynağı.
        Dönüş:
            SasiOlculeri (tahmini=True, parca_sayisi = parça dosyası sayısı).
        Hatalar:
            BirimHatasi: Birim tanınmıyorsa.
        """
        olculer = self._birim_dogrulayici.olculeri_mm_ye_cevir(ozet, birim)

        def mm(d: float) -> float:
            return BirimDonusturucu.uzunlugu_mm_ye_cevir(d, birim)

        govdeler = [p for p in parcalar if p.rol is ParcaRolu.GOVDE] or parcalar
        ana = max(govdeler, key=lambda p: p.geometri.olculer[0] * p.geometri.olculer[1])
        en, boy = mm(ana.geometri.olculer[0]), mm(ana.geometri.olculer[1])
        uyarilar = list(olculer.uyarilar)

        if dingil_mm is not None:
            kollar = [p for p in parcalar if p.rol is ParcaRolu.KOL]
            kol_genisligi = min(mm(d) for d in self._kol_olculeri(kollar[0])[:2]) if kollar else 0.0
            motor_en, motor_boy = self._motor_yayilimi(dingil_mm, motor_sayisi)
            en, boy = max(en, motor_en + kol_genisligi), max(boy, motor_boy + kol_genisligi)
        else:
            uyarilar.append(DINGIL_YOK_UYARISI)

        alan_mm2 = olculer.alan_mm2
        if alan_mm2 is None and ozet.alan is not None:
            # Hem 3B hem levha parça varsa levha alanı da gösterilsin.
            alan_mm2 = BirimDonusturucu.alani_mm2_ye_cevir(ozet.alan, birim)
        return replace(
            olculer,
            en_mm=en,
            boy_mm=boy,
            yukseklik_mm=max(mm(p.geometri.olculer[2]) for p in parcalar),
            alan_mm2=alan_mm2,
            uyarilar=uyarilar,
            dingil_mm=dingil_mm,
            dingil_kaynagi=dingil_kaynagi if dingil_mm is not None else None,
            parca_sayisi=len(parcalar),
            tahmini=True,
        )

    @staticmethod
    def _motor_yayilimi(dingil_mm: float, motor_sayisi: int) -> tuple[float, float]:
        """
        Motor merkezlerinin x ve y yönündeki yayılımı, mm.

        Motorlar dingil çemberine eşit aralıkla, ön tarafta iki motor ortada boşluk
        bırakacak şekilde (X düzeni) dizilir.
        """
        yaricap = dingil_mm / 2
        adim = 2 * math.pi / motor_sayisi
        acilar = [adim * i + adim / 2 for i in range(motor_sayisi)]
        xler = [yaricap * math.cos(a) for a in acilar]
        yler = [yaricap * math.sin(a) for a in acilar]
        return max(xler) - min(xler), max(yler) - min(yler)

    @staticmethod
    def _kol_olculeri(kol: SasiParcasi) -> list[float]:
        """Tek kolun ölçüleri büyükten küçüğe (dosya biriminde)."""
        return sorted(kol.geometri.tek_govde_olculeri or kol.geometri.olculer, reverse=True)

    @staticmethod
    def _toplam(parcalar: list[SasiParcasi], alan_adi: str) -> float | None:
        """Parçaların hacim veya alanının adetlerle toplamı; hiçbirinde değer yoksa None."""
        degerler = [(getattr(p.geometri, alan_adi), p.adet) for p in parcalar]
        bilinen = [(d, a) for d, a in degerler if d is not None]
        return sum(d * a for d, a in bilinen) if bilinen else None
