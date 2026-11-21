"""
Şartname maddelerinin tasarımla karşılaştırılması (uyum raporu, plandaki K14).

Kurallar:
    - Ölçülemeyen madde (failsafe, irtifa…) ölçülmüş gibi gösterilmez: "doğrulanamıyor".
    - Gereken değer yoksa sonuç "doğrulanamıyor"; tahmin yapılmaz.
    - Toplam eksikse (ör. bazı parçaların ağırlığı girilmemiş) bilinen kısım bir ALT
      SINIRDIR: "en çok" sınırını şimdiden aşıyorsa kesin uyumsuz, aşmıyorsa doğrulanamıyor.
    - Puanlanan kriterler yalnızca bilgi olarak gösterilir.
    - Kullanıcının onaylamadığı madde "onay bekliyor" olur; değerlendirme yine yazılır.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Final

from drone.hedefler import DroneHedefleri
from elektronik.hesap.agirlik import AgirlikOzeti
from elektronik.hesap.ucus import HesapDegeri, UcusOzeti
from elektronik.hesap.uyum import sayi_yaz
from elektronik.parcalar.cekirdek_parcalar import Pervane, Pil
from elektronik.parcalar.diger_parca import DigerParca
from elektronik.parcalar.parca import Parca
from elektronik.parcalar.turler import DigerAltTur
from sartname.modeller import BUYUKLUK_TANIMLARI, SINIR_TURU_ADLARI, Buyukluk, Madde, MaddeSinifi, SinirTuru
from sasi.modeller import SasiOlculeri

# DEĞİŞTİRİLEBİLİR: "eşit" sınırında kabul edilen göreli fark (yuvarlama farkları için).
ESITLIK_TOLERANSI: Final[float] = 1e-6

PARCA_ALT_TURLERI: Final[dict[Buyukluk, DigerAltTur]] = {
    Buyukluk.GPS: DigerAltTur.GPS,
    Buyukluk.KAMERA: DigerAltTur.KAMERA,
    Buyukluk.VTX: DigerAltTur.VTX,
    Buyukluk.TELEMETRI: DigerAltTur.TELEMETRI,
}


class MaddeDurumu(str, Enum):
    """Bir maddenin rapordaki sonucu."""

    UYGUN = "uygun"
    UYGUNSUZ = "uygunsuz"
    BILINMIYOR = "bilinmiyor"
    BILGI = "bilgi"  # puanlanan kriter
    ONAY_BEKLIYOR = "onay_bekliyor"


@dataclass
class SartnameBaglami:
    """
    Maddeleri karşılaştırmak için gereken tasarım bilgileri.

    Alanlar:
        kalemler: (parça, adet) listesi.
        motor_sayisi: Drone türüne göre motor sayısı.
        sasi_olculeri: Birim onaylanmış şasi ölçüleri; yoksa None.
        agirlik / ucus: Ağırlık ve uçuş hesabı.
        hedefler: Drone hedefleri (yük).
        maliyet_tl: Toplam maliyet; hesaplanmadıysa None.
        maliyet_eksik: Fiyatı eksik kalem varsa True (maliyet bir alt sınırdır).
        maliyet_tahmini: Kurla çevrilmiş tutar içeriyorsa True.
    """

    kalemler: list[tuple[Parca, int]]
    motor_sayisi: int
    sasi_olculeri: SasiOlculeri | None
    agirlik: AgirlikOzeti
    ucus: UcusOzeti
    hedefler: DroneHedefleri
    maliyet_tl: float | None = None
    maliyet_eksik: bool = False
    maliyet_tahmini: bool = False


@dataclass(frozen=True)
class Olcum:
    """
    Tasarımın bir büyüklükteki değeri.

    Alanlar:
        deger: Değer; ölçülemediyse None.
        tahmini: Tahmine dayanıyorsa True.
        alt_sinir: Değer eksik bir toplamsa (gerçek değer daha büyük olabilir) True.
        neden: Ölçülemediyse veya eksikse Türkçe açıklama.
    """

    deger: float | None
    tahmini: bool = False
    alt_sinir: bool = False
    neden: str | None = None


@dataclass(frozen=True)
class MaddeSonucu:
    """
    Alanlar:
        madde: Şartname maddesi.
        durum: MaddeDurumu.
        tasarim: Tasarımın değeri (ör. "2.150 g"); ölçülemediyse "?".
        aciklama: Türkçe açıklama (ör. "150 g fazla").
        tahmini: Tasarım değeri tahminse True.
    """

    madde: Madde
    durum: MaddeDurumu
    tasarim: str
    aciklama: str
    tahmini: bool = False


def _hesap(h: HesapDegeri, alt_sinir: bool = False) -> Olcum:
    return Olcum(h.deger, h.tahmini, alt_sinir, None if h.deger is not None else h.aciklama)


def _en_buyuk(degerler: list[float | None], yok_mesaji: str, eksik_mesaji: str) -> Olcum:
    """Parçalardaki en büyük değer (ör. birden çok pil varsa en büyük hücre sayısı)."""
    if not degerler:
        return Olcum(None, neden=yok_mesaji)
    if any(d is None for d in degerler):
        return Olcum(None, neden=eksik_mesaji)
    return Olcum(max(degerler))


class SartnameKontrolcusu:
    """Maddeleri tasarım değerleriyle karşılaştırır."""

    def olc(self, buyukluk: Buyukluk, b: SartnameBaglami) -> Olcum:
        """
        Tasarımın verilen büyüklükteki değeri.

        Parametreler:
            buyukluk: Ölçülecek büyüklük (parça ve "diğer" büyüklükleri burada ölçülmez).
            b: Tasarım bilgileri.
        """
        if buyukluk is Buyukluk.KALKIS_AGIRLIGI:
            return _hesap(b.ucus.toplam_agirlik_g, alt_sinir=not b.agirlik.eksiksiz_mi)
        if buyukluk is Buyukluk.BOYUT:
            if b.sasi_olculeri is None:
                return Olcum(None, neden="Şasi dosyası yüklenmedi veya birimi onaylanmadı")
            return Olcum(max(b.sasi_olculeri.en_mm, b.sasi_olculeri.boy_mm))
        if buyukluk is Buyukluk.PERVANE_CAPI:
            return _en_buyuk(
                [p.cap_inc for p, _ in b.kalemler if isinstance(p, Pervane)], "Pervane eklenmedi", "Pervane çapı girilmemiş"
            )
        if buyukluk is Buyukluk.MOTOR_SAYISI:
            return Olcum(float(b.motor_sayisi))
        if buyukluk is Buyukluk.PIL_HUCRE:
            return _en_buyuk(
                [p.hucre_sayisi_s for p, _ in b.kalemler if isinstance(p, Pil)], "Pil eklenmedi", "Pil hücre sayısı girilmemiş"
            )
        if buyukluk is Buyukluk.PIL_KAPASITE:
            return _en_buyuk(
                [p.kapasite_mah for p, _ in b.kalemler if isinstance(p, Pil)], "Pil eklenmedi", "Pil kapasitesi girilmemiş"
            )
        if buyukluk is Buyukluk.UCUS_SURESI:
            return _hesap(b.ucus.ucus_suresi_dk)
        if buyukluk is Buyukluk.ITKI_AGIRLIK:
            return _hesap(b.ucus.itki_agirlik_orani)
        if buyukluk is Buyukluk.YUK:
            if b.hedefler.yuk_g is None:
                return Olcum(None, neden="Hedefler sekmesinde taşınacak yük girilmedi")
            return Olcum(b.hedefler.yuk_g)
        if buyukluk is Buyukluk.MALIYET:
            if b.maliyet_tl is None:
                return Olcum(None, neden="Maliyet hesaplanmadı")
            return Olcum(b.maliyet_tl, b.maliyet_tahmini, b.maliyet_eksik, "bazı fiyatlar girilmemiş" if b.maliyet_eksik else None)
        return Olcum(None, neden="Program bu maddeyi ölçemez; elle kontrol edin")

    def kontrol_et(self, maddeler: list[Madde], baglam: SartnameBaglami) -> list[MaddeSonucu]:
        """
        Parametreler:
            maddeler: Şartname maddeleri.
            baglam: Tasarım bilgileri.
        Dönüş:
            Her madde için bir MaddeSonucu, aynı sırayla.
        """
        sonuclar = []
        for m in maddeler:
            durum, tasarim, aciklama, tahmini = self._karsilastir(m, baglam)
            if m.sinif is MaddeSinifi.PUANLANAN:
                durum = MaddeDurumu.BILGI
                aciklama = "Puanlanan kriter (yalnızca bilgi)" + (f" – {aciklama}" if aciklama else "")
            if not m.onaylandi:
                aciklama = f"Madde onay bekliyor (şartnameden kontrol edip onaylayın). Şu anki değerlendirme: {durum_adi(durum)}" + (
                    f" – {aciklama}" if aciklama else ""
                )
                durum = MaddeDurumu.ONAY_BEKLIYOR
            sonuclar.append(MaddeSonucu(m, durum, tasarim, aciklama, tahmini))
        return sonuclar

    def _karsilastir(self, m: Madde, b: SartnameBaglami) -> tuple[MaddeDurumu, str, str, bool]:
        """(durum, tasarım değeri metni, açıklama, tahmini)."""
        tanim = BUYUKLUK_TANIMLARI[m.buyukluk]
        if m.buyukluk in PARCA_ALT_TURLERI:
            alt_tur = PARCA_ALT_TURLERI[m.buyukluk]
            var = any(isinstance(p, DigerParca) and p.alt_tur is alt_tur for p, _ in b.kalemler)
            if var:
                return MaddeDurumu.UYGUN, "var", f"{tanim.ad} eklendi", False
            return MaddeDurumu.UYGUNSUZ, "yok", f"{tanim.ad} zorunlu ama drone'da yok (Elektronik → Diğer)", False

        olcum = self.olc(m.buyukluk, b)
        if olcum.deger is None or m.deger is None:
            return MaddeDurumu.BILINMIYOR, "?", olcum.neden or "Sınır değeri girilmemiş", olcum.tahmini
        birim = f" {tanim.birim}" if tanim.birim else ""
        tasarim = f"{sayi_yaz(olcum.deger)}{birim}"
        sinir = f"{SINIR_TURU_ADLARI[m.sinir_turu]} {sayi_yaz(m.deger)}{birim}"
        fark = abs(olcum.deger - m.deger)
        eksik = f" ({olcum.neden}; gerçek değer daha yüksek olabilir)" if olcum.alt_sinir else ""

        if m.sinir_turu is SinirTuru.EN_COK:
            if olcum.deger > m.deger:
                return MaddeDurumu.UYGUNSUZ, tasarim, f"Sınır {sinir}; {sayi_yaz(fark)}{birim} fazla{eksik}", olcum.tahmini
            if olcum.alt_sinir:
                return MaddeDurumu.BILINMIYOR, tasarim, f"Sınır {sinir}; şimdilik altında{eksik}", olcum.tahmini
            return MaddeDurumu.UYGUN, tasarim, f"Sınır {sinir}; {sayi_yaz(fark)}{birim} pay var", olcum.tahmini
        if m.sinir_turu is SinirTuru.EN_AZ:
            if olcum.deger >= m.deger:
                return MaddeDurumu.UYGUN, tasarim, f"Sınır {sinir}", olcum.tahmini
            if olcum.alt_sinir:
                return MaddeDurumu.BILINMIYOR, tasarim, f"Sınır {sinir}; şimdilik altında{eksik}", olcum.tahmini
            return MaddeDurumu.UYGUNSUZ, tasarim, f"Sınır {sinir}; {sayi_yaz(fark)}{birim} eksik", olcum.tahmini
        # EŞİT
        if fark <= ESITLIK_TOLERANSI * max(1.0, abs(m.deger)):
            return MaddeDurumu.UYGUN, tasarim, f"İstenen {sinir}", olcum.tahmini
        if olcum.alt_sinir and olcum.deger < m.deger:
            return MaddeDurumu.BILINMIYOR, tasarim, f"İstenen {sinir}{eksik}", olcum.tahmini
        return MaddeDurumu.UYGUNSUZ, tasarim, f"İstenen {sinir}; tasarım {tasarim}", olcum.tahmini


MADDE_DURUMU_ADLARI: Final[dict[MaddeDurumu, str]] = {
    MaddeDurumu.UYGUN: "uygun",
    MaddeDurumu.UYGUNSUZ: "uygun değil",
    MaddeDurumu.BILINMIYOR: "doğrulanamıyor",
    MaddeDurumu.BILGI: "bilgi",
    MaddeDurumu.ONAY_BEKLIYOR: "onay bekliyor",
}


def durum_adi(durum: MaddeDurumu) -> str:
    """Durumun Türkçe adı."""
    return MADDE_DURUMU_ADLARI[durum]
