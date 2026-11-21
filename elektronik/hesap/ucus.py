"""
Uçuş hesabı: itki, itki/ağırlık oranı, asılı kalma gazı ve akımı, toplam en büyük
akım ve uçuş süresi (plan bölüm 5.2).

Motorun itki tablosu varsa değerler tablodan okunur; yoksa tahmini_itki.py'deki
fizik formülleri kullanılır ve sonuç "tahmini" etiketlenir. Gereken bir değer
girilmemişse o çıktı None olur ve nedeni yazılır; değer uydurulmaz.
Uçuş süresi her zaman tahminidir (uçuş tarzına bağlıdır).
"""

import math
from dataclasses import dataclass, field

from cekirdek.bicim import sayi_yaz
from cekirdek.birimler import BirimDonusturucu
from elektronik.hesap.agirlik import AgirlikOzeti
from elektronik.hesap.akim import EnBuyukAkimHesaplayici
from elektronik.hesap.itki_tablosu import ItkiTablosuOkuyucu
from elektronik.hesap.katsayilar import (
    HEDEF_ITKI_AGIRLIK,
    KULLANILABILIR_PIL_ORANI,
    NOMINAL_HUCRE_GERILIMI_V,
    UCUS_TARZI_KATSAYILARI,
    VARSAYILAN_HEDEF_ITKI_AGIRLIK,
    VARSAYILAN_NOMINAL_HUCRE_GERILIMI_V,
    VARSAYILAN_UCUS_TARZI_KATSAYISI,
    YUZDE,
)
from elektronik.hesap.tahmini_itki import TahminiItkiHesaplayici
from elektronik.parcalar.cekirdek_parcalar import Motor, Pervane, Pil
from elektronik.parcalar.parca import Parca
from elektronik.parcalar.turler import alan_etiketi


@dataclass(frozen=True)
class HesapDegeri:
    """
    Tek bir hesap çıktısı.

    Alanlar:
        deger: Sonuç; hesaplanamadıysa None.
        tahmini: Sonuç tahmine dayanıyorsa True.
        aciklama: Nasıl hesaplandığı veya neden hesaplanamadığı (Türkçe).
    """

    deger: float | None
    tahmini: bool = False
    aciklama: str = ""


@dataclass
class UcusOzeti:
    """
    Uçuş hesabının bütün çıktıları.

    Alanlar:
        toplam_agirlik_g: Toplam kalkış ağırlığı, g.
        toplam_itki_g: Bütün motorların tam gaz itkisi, g.
        itki_agirlik_orani: toplam itki / toplam ağırlık.
        hedef_itki_agirlik: Kullanım amacına göre hedef oran.
        asili_gaz_yuzde: Havada asılı kalmak için gereken gaz, %.
        asili_akim_a: Asılı kalırken bütün motorların toplam akımı, A.
        toplam_maks_akim_a: Tam gazda toplam en büyük akım, A.
        ucus_suresi_dk: Tahmini uçuş süresi, dakika.
        notlar: Hesapta kullanılan kabuller (ör. "pil kimyası girilmedi, 3,7 V/hücre alındı").
        hedef_ucus_suresi_dk: Kullanıcının istediği en az uçuş süresi; girilmediyse None.
    """

    toplam_agirlik_g: HesapDegeri
    toplam_itki_g: HesapDegeri
    itki_agirlik_orani: HesapDegeri
    hedef_itki_agirlik: float
    asili_gaz_yuzde: HesapDegeri
    asili_akim_a: HesapDegeri
    toplam_maks_akim_a: HesapDegeri
    ucus_suresi_dk: HesapDegeri
    notlar: list[str] = field(default_factory=list)
    hedef_ucus_suresi_dk: float | None = None

    @property
    def ucus_suresi_hedefe_ulasiyor_mu(self) -> bool | None:
        """Tahmini uçuş süresi hedefe ulaşıyorsa True; hedef yoksa veya süre hesaplanamadıysa None."""
        if self.hedef_ucus_suresi_dk is None or self.ucus_suresi_dk.deger is None:
            return None
        return self.ucus_suresi_dk.deger >= self.hedef_ucus_suresi_dk

    @property
    def hedefe_ulasiyor_mu(self) -> bool | None:
        """İtki/ağırlık hedefe ulaşıyorsa True; oran hesaplanamadıysa None."""
        if self.itki_agirlik_orani.deger is None:
            return None
        return self.itki_agirlik_orani.deger >= self.hedef_itki_agirlik


def _eksik(parca: Parca | None, tur_adi: str, *alanlar: str) -> list[str]:
    """Parça yoksa "X eklenmedi", varsa girilmemiş alanların listesi."""
    if parca is None:
        return [f"{tur_adi} eklenmedi"]
    return [f"{tur_adi} {alan_etiketi(a).split(' (')[0]} girilmemiş" for a in alanlar if getattr(parca, a) is None]


def _ilk(kalemler: list[tuple[Parca, int]], sinif: type) -> Parca | None:
    """Verilen sınıftaki ilk parça (hesap tek bir yapılandırma için yapılır)."""
    return next((p for p, _ in kalemler if isinstance(p, sinif)), None)


class UcusHesaplayici:
    """
    Drone'un parça listesinden uçuş değerlerini hesaplar.

    Parametreler:
        tahmini_itki: İtki tablosu yokken kullanılan fizik tahmincisi.
    """

    def __init__(self, tahmini_itki: TahminiItkiHesaplayici | None = None) -> None:
        self._tahmini = tahmini_itki or TahminiItkiHesaplayici()
        self._akim = EnBuyukAkimHesaplayici()

    def hesapla(
        self,
        kalemler: list[tuple[Parca, int]],
        motor_sayisi: int,
        amac: str,
        agirlik: AgirlikOzeti,
        hedef_ucus_suresi_dk: float | None = None,
    ) -> UcusOzeti:
        """
        Uçuş değerlerini hesaplar.

        Parametreler:
            kalemler: (parça, adet) listesi.
            motor_sayisi: Drone türüne göre motor sayısı.
            amac: Kullanım amacı (hedef oran ve uçuş tarzı katsayısı için).
            agirlik: AgirlikHesaplayici sonucu (yük dahil).
            hedef_ucus_suresi_dk: Kullanıcının istediği en az uçuş süresi; yoksa None.
        Dönüş:
            UcusOzeti.
        """
        notlar: list[str] = []
        motor, pervane, pil = _ilk(kalemler, Motor), _ilk(kalemler, Pervane), _ilk(kalemler, Pil)
        for sinif, ad in ((Motor, "motor"), (Pervane, "pervane"), (Pil, "pil")):
            if sum(1 for p, _ in kalemler if isinstance(p, sinif)) > 1:
                notlar.append(f"Birden çok {ad} modeli var; hesap listedeki ilk {ad} ile yapıldı.")

        gerilim = self._nominal_gerilim(pil, notlar)
        toplam = self._toplam_agirlik(agirlik)
        motor_itkisi, tablo = self._motor_itkisi(motor, pervane, pil, gerilim)

        toplam_itki = HesapDegeri(
            motor_itkisi.deger * motor_sayisi if motor_itkisi.deger is not None else None,
            motor_itkisi.tahmini, motor_itkisi.aciklama,
        )
        oran = self._oran(toplam_itki, toplam)
        asili_gaz, asili_akim = self._asili(toplam, motor_itkisi, tablo, pervane, gerilim, motor_sayisi)
        maks_akim = self._akim.hesapla(kalemler, motor_sayisi)

        return UcusOzeti(
            toplam_agirlik_g=toplam,
            toplam_itki_g=toplam_itki,
            itki_agirlik_orani=oran,
            hedef_itki_agirlik=HEDEF_ITKI_AGIRLIK.get(amac, VARSAYILAN_HEDEF_ITKI_AGIRLIK),
            asili_gaz_yuzde=asili_gaz,
            asili_akim_a=asili_akim,
            toplam_maks_akim_a=HesapDegeri(
                maks_akim.toplam_a,
                aciklama=f"{motor_sayisi} × motor en büyük akımı" if maks_akim.toplam_a is not None else maks_akim.eksik,
            ),
            ucus_suresi_dk=self._ucus_suresi(pil, asili_akim, amac),
            notlar=notlar,
            hedef_ucus_suresi_dk=hedef_ucus_suresi_dk,
        )

    # ---------- Adımlar ----------

    @staticmethod
    def _nominal_gerilim(pil: Pil | None, notlar: list[str]) -> float | None:
        """Pil nominal gerilimi, V. Kimya girilmemişse varsayılan hücre gerilimi alınır ve not düşülür."""
        if pil is None or pil.hucre_sayisi_s is None:
            return None
        if pil.kimya is None:
            notlar.append(
                f"Pil kimyası girilmedi; hesapta hücre başına {sayi_yaz(VARSAYILAN_NOMINAL_HUCRE_GERILIMI_V)} V alındı."
            )
            return pil.hucre_sayisi_s * VARSAYILAN_NOMINAL_HUCRE_GERILIMI_V
        return pil.hucre_sayisi_s * NOMINAL_HUCRE_GERILIMI_V[pil.kimya]

    @staticmethod
    def _toplam_agirlik(agirlik: AgirlikOzeti) -> HesapDegeri:
        """Ağırlık özetini hesap değerine çevirir; hiç ağırlık yoksa None."""
        if agirlik.toplam_g <= 0:
            return HesapDegeri(None, aciklama="şasi ve parça ağırlıkları girilmemiş")
        aciklama = "şasi + parçalar + kablo payı" + (" + yük" if agirlik.yuk_g else "")
        if not agirlik.eksiksiz_mi:
            aciklama += " (bazı ağırlıklar eksik, gerçek değer daha yüksek)"
        return HesapDegeri(agirlik.toplam_g, agirlik.tahmini, aciklama)

    def _motor_itkisi(
        self, motor: Motor | None, pervane: Pervane | None, pil: Pil | None, gerilim: float | None
    ) -> tuple[HesapDegeri, ItkiTablosuOkuyucu | None]:
        """Tek motorun tam gaz itkisi: önce itki tablosu, yoksa tahmini formül."""
        cap = pervane.cap_inc if pervane else None
        if motor is not None and motor.itki_tablosu and gerilim is not None:
            tablo = ItkiTablosuOkuyucu(motor.itki_tablosu, gerilim, cap)
            return HesapDegeri(
                tablo.en_buyuk_itki_g, aciklama=f"itki tablosundan ({sayi_yaz(tablo.secilen_gerilim_v)} V)"
            ), tablo
        eksikler = (
            _eksik(motor, "Motor", "kv")
            + _eksik(pervane, "Pervane", "cap_inc", "hatve_inc")
            + _eksik(pil, "Pil", "hucre_sayisi_s")
        )
        if eksikler or gerilim is None:
            return HesapDegeri(None, aciklama="; ".join(eksikler)), None
        itki = self._tahmini.en_buyuk_itki_g(motor.kv, gerilim, pervane.cap_inc, pervane.hatve_inc)
        return HesapDegeri(itki, True, "itki tablosu yok; KV, gerilim ve pervaneden tahmin"), None

    @staticmethod
    def _oran(toplam_itki: HesapDegeri, toplam: HesapDegeri) -> HesapDegeri:
        """İtki/ağırlık oranı."""
        if toplam_itki.deger is None or toplam.deger is None:
            neden = toplam_itki.aciklama if toplam_itki.deger is None else toplam.aciklama
            return HesapDegeri(None, aciklama=neden)
        return HesapDegeri(
            toplam_itki.deger / toplam.deger, toplam_itki.tahmini or toplam.tahmini, "toplam itki / toplam ağırlık"
        )

    def _asili(
        self,
        toplam: HesapDegeri,
        motor_itkisi: HesapDegeri,
        tablo: ItkiTablosuOkuyucu | None,
        pervane: Pervane | None,
        gerilim: float | None,
        motor_sayisi: int,
    ) -> tuple[HesapDegeri, HesapDegeri]:
        """Asılı kalma gazı (%) ve toplam akımı (A)."""
        if toplam.deger is None or motor_itkisi.deger is None:
            neden = toplam.aciklama if toplam.deger is None else motor_itkisi.aciklama
            return HesapDegeri(None, aciklama=neden), HesapDegeri(None, aciklama=neden)
        gereken = toplam.deger / motor_sayisi
        if gereken > motor_itkisi.deger:
            neden = "motorların itkisi ağırlığı kaldırmaya yetmiyor"
            return HesapDegeri(None, aciklama=neden), HesapDegeri(None, aciklama=neden)

        if tablo is not None:
            gaz = tablo.gaz_yuzde(gereken)
            gaz_degeri = HesapDegeri(gaz, toplam.tahmini, "itki tablosundan ara değer")
            motor_akimi = tablo.akim_a(gaz)
            if motor_akimi is not None:
                return gaz_degeri, HesapDegeri(motor_akimi * motor_sayisi, toplam.tahmini, "itki tablosundan ara değer")
        else:
            # Tablo yoksa itki ≈ gaz² kabulüyle (pervane itkisi devrin karesiyle artar) gaz = √(oran).
            gaz_degeri = HesapDegeri(
                math.sqrt(gereken / motor_itkisi.deger) * YUZDE, True, "≈ √(asılı itki / en büyük itki), tahmini"
            )

        if pervane is None or pervane.cap_inc is None or gerilim is None:
            return gaz_degeri, HesapDegeri(None, aciklama="pervane çapı veya pil gerilimi girilmemiş")
        guc = self._tahmini.asili_guc_w(gereken, pervane.cap_inc)
        return gaz_degeri, HesapDegeri(guc / gerilim * motor_sayisi, True, "momentum teorisiyle tahmin")

    @staticmethod
    def _ucus_suresi(pil: Pil | None, asili_akim: HesapDegeri, amac: str) -> HesapDegeri:
        """Uçuş süresi = kullanılabilir kapasite / ortalama akım; ortalama akım = asılı akım × uçuş tarzı katsayısı."""
        if pil is None or pil.kapasite_mah is None:
            return HesapDegeri(None, True, "pil eklenmedi" if pil is None else "pil kapasitesi girilmemiş")
        if asili_akim.deger is None:
            return HesapDegeri(None, True, asili_akim.aciklama)
        katsayi = UCUS_TARZI_KATSAYILARI.get(amac, VARSAYILAN_UCUS_TARZI_KATSAYISI)
        kullanilabilir_ah = BirimDonusturucu.mah_i_ah_a_cevir(pil.kapasite_mah) * KULLANILABILIR_PIL_ORANI
        sure = BirimDonusturucu.saati_dakikaya_cevir(kullanilabilir_ah / (asili_akim.deger * katsayi))
        return HesapDegeri(
            sure, True,
            f"kapasitenin %{sayi_yaz(KULLANILABILIR_PIL_ORANI * YUZDE)}'i, ortalama akım = asılı akım × {sayi_yaz(katsayi)} (uçuş tarzı)",
        )
