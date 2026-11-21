"""
Çekirdek parça türleri: motor, pervane, ESC, pil, uçuş kontrol kartı, alıcı, güç dağıtımı.

Bu parçalar ilk sürümde tam uyum kontrolüne girer. Alanlar
docs/elektronik_plani.md bölüm 2.1'e ve uyum kontrollerinin (K1–K13)
ihtiyaçlarına göre seçilmiştir. Tüm teknik alanlar isteğe bağlıdır: değer
bilinmiyorsa None kalır ve ilgili kontrol "doğrulanamıyor" sonucunu verir.
"""

from dataclasses import dataclass
from typing import ClassVar

from cekirdek.hatalar import GecersizDegerHatasi
from elektronik.parcalar.denetim import DegerDenetleyici
from elektronik.parcalar.parca import Parca
from elektronik.parcalar.turler import ParcaTuru, PilKimyasi

EN_FAZLA_GAZ_YUZDE: float = 100.0


@dataclass(frozen=True, kw_only=True)
class ItkiNoktasi:
    """
    Motor itki tablosunun bir satırı (bir pervane + gerilim + gaz için ölçüm).

    Alanlar:
        gerilim_v: Ölçümdeki gerilim, V.
        gaz_yuzde: Gaz, % (0'dan büyük, en çok 100).
        itki_g: İtki, gram.
        pervane: Ölçümde kullanılan pervane (ör. "5x4.3x3"); bilinmiyorsa None.
        akim_a: Çekilen akım, A; bilinmiyorsa None.
        guc_w: Güç, W; bilinmiyorsa None.
    """

    gerilim_v: float
    gaz_yuzde: float
    itki_g: float
    pervane: str | None = None
    akim_a: float | None = None
    guc_w: float | None = None

    def __post_init__(self) -> None:
        d = DegerDenetleyici
        for alan in ("gerilim_v", "gaz_yuzde", "itki_g"):
            deger = getattr(self, alan)
            if deger is None:
                raise GecersizDegerHatasi("İtki tablosu satırında gerilim, gaz ve itki zorunludur.")
            d.pozitif_sayi(alan, deger)
        d.pozitif_sayi("akim_a", self.akim_a)
        d.pozitif_sayi("guc_w", self.guc_w)
        if self.gaz_yuzde > EN_FAZLA_GAZ_YUZDE:
            raise GecersizDegerHatasi(f"Gaz yüzdesi en çok {EN_FAZLA_GAZ_YUZDE:.0f} olabilir (girilen: {self.gaz_yuzde}).")


@dataclass(kw_only=True)
class Motor(Parca):
    """
    Fırçasız motor.

    Alanlar:
        kv: Gerilim başına devir, dev/dk/V.
        maks_akim_a: Kısa süreli en büyük akım, A.
        boyut: Stator boyutu, ör. "2207" (22 mm çap, 7 mm yükseklik).
        min_s / maks_s: Desteklenen pil hücre sayısı aralığı (K1).
        montaj_deseni_mm: Vida deliği deseninin kenar uzunluğu, mm (ör. 16 → 16×16).
        onerilen_pervane_min_inc / maks_inc: Üreticinin önerdiği pervane çapı aralığı (K4).
        itki_tablosu: Ölçülmüş itki satırları; yoksa itki "tahmini" hesaplanır.
    """

    TUR: ClassVar[ParcaTuru] = ParcaTuru.MOTOR
    ARALIK_CIFTLERI: ClassVar[tuple[tuple[str, str], ...]] = (
        ("min_s", "maks_s"),
        ("onerilen_pervane_min_inc", "onerilen_pervane_maks_inc"),
    )

    kv: float | None = None
    maks_akim_a: float | None = None
    boyut: str | None = None
    min_s: int | None = None
    maks_s: int | None = None
    montaj_deseni_mm: float | None = None
    onerilen_pervane_min_inc: float | None = None
    onerilen_pervane_maks_inc: float | None = None
    itki_tablosu: list[ItkiNoktasi] | None = None

    def _ture_ozel_denetim(self) -> None:
        if self.itki_tablosu is not None:
            if not all(isinstance(n, ItkiNoktasi) for n in self.itki_tablosu):
                raise GecersizDegerHatasi("İtki tablosu yalnızca itki satırlarından oluşmalı.")
            # Boş tablo "veri yok" ile aynı anlama gelir; tek biçimde tutulsun.
            self.itki_tablosu = list(self.itki_tablosu) or None


@dataclass(kw_only=True)
class Pervane(Parca):
    """
    Pervane.

    Alanlar:
        cap_inc: Çap, inç.
        hatve_inc: Hatve (adım), inç.
        kanat_sayisi: Kanat sayısı (tam sayı).
        mil_deligi_mm: Göbekteki mil deliği çapı, mm (motor miline uyum için).
    """

    TUR: ClassVar[ParcaTuru] = ParcaTuru.PERVANE

    cap_inc: float | None = None
    hatve_inc: float | None = None
    kanat_sayisi: int | None = None
    mil_deligi_mm: float | None = None


@dataclass(kw_only=True)
class Esc(Parca):
    """
    Elektronik hız kontrolcüsü (ESC).

    Alanlar:
        surekli_akim_a: Kanal başına sürekli akım, A (K6).
        tepe_akim_a: Kanal başına kısa süreli akım, A.
        min_s / maks_s: Desteklenen hücre aralığı (K2).
        protokoller: Desteklenen sinyal protokolleri, ör. ["DShot600", "DShot300"] (K9).
        montaj_olcusu_mm: Montaj delikleri arası, mm (30,5 / 20 / 25,5) (K8).
        kanal_sayisi: Sürdürebildiği motor sayısı; 4'ü 1 arada ESC için 4.
        konnektor: Pil konnektörü, ör. "XT60" (K12).
    """

    TUR: ClassVar[ParcaTuru] = ParcaTuru.ESC
    ARALIK_CIFTLERI: ClassVar[tuple[tuple[str, str], ...]] = (
        ("min_s", "maks_s"),
        ("surekli_akim_a", "tepe_akim_a"),
    )

    surekli_akim_a: float | None = None
    tepe_akim_a: float | None = None
    min_s: int | None = None
    maks_s: int | None = None
    protokoller: list[str] | None = None
    montaj_olcusu_mm: float | None = None
    kanal_sayisi: int | None = None
    konnektor: str | None = None


@dataclass(kw_only=True)
class Pil(Parca):
    """
    Pil.

    Alanlar:
        hucre_sayisi_s: Seri hücre sayısı (S).
        kapasite_mah: Kapasite, mAh.
        desarj_c: Sürekli deşarj oranı, C (sürekli akım = kapasite_Ah × C) (K7).
        konnektor: ör. "XT60" (K12).
        kimya: LiPo / LiHV / Li-ion; dolu hücre gerilimi buna bağlı (K3).
    """

    TUR: ClassVar[ParcaTuru] = ParcaTuru.PIL

    hucre_sayisi_s: int | None = None
    kapasite_mah: float | None = None
    desarj_c: float | None = None
    konnektor: str | None = None
    kimya: PilKimyasi | None = None

    def _ture_ozel_denetim(self) -> None:
        if self.kimya is not None and not isinstance(self.kimya, PilKimyasi):
            try:
                self.kimya = PilKimyasi(self.kimya)
            except ValueError:
                gecerli = ", ".join(k.value for k in PilKimyasi)
                raise GecersizDegerHatasi(f"Pil kimyası tanınmıyor: {self.kimya!r}. Seçenekler: {gecerli}.") from None


@dataclass(kw_only=True)
class UcusKarti(Parca):
    """
    Uçuş kontrol kartı (FC).

    Alanlar:
        montaj_olcusu_mm: Montaj delikleri arası, mm (K8).
        giris_gerilimi_min_v / maks_v: Kabul ettiği giriş gerilimi aralığı, V (K3).
        esc_protokolleri: Desteklenen ESC protokolleri (K9).
        alici_protokolleri: Desteklenen alıcı protokolleri, ör. ["CRSF", "SBUS"] (K10).
        uart_sayisi: Seri port sayısı (alıcı, GPS, VTX bağlantısı için).
        bec_cikislari_v: Dahili regülatör çıkış gerilimleri, ör. [5.0, 9.0] (K10, K13).
        dahili_pdb: Güç dağıtımı kartın üzerinde mi (PDB zorunluluğunu etkiler).
    """

    TUR: ClassVar[ParcaTuru] = ParcaTuru.UCUS_KARTI
    ARALIK_CIFTLERI: ClassVar[tuple[tuple[str, str], ...]] = (("giris_gerilimi_min_v", "giris_gerilimi_maks_v"),)

    montaj_olcusu_mm: float | None = None
    giris_gerilimi_min_v: float | None = None
    giris_gerilimi_maks_v: float | None = None
    esc_protokolleri: list[str] | None = None
    alici_protokolleri: list[str] | None = None
    uart_sayisi: int | None = None
    bec_cikislari_v: list[float] | None = None
    dahili_pdb: bool | None = None


@dataclass(kw_only=True)
class Alici(Parca):
    """
    RC alıcı.

    Alanlar:
        protokol: ör. "CRSF" (ExpressLRS), "SBUS".
        besleme_gerilimi_v: Nominal besleme gerilimi, V.
        baglanti: Karta bağlanma şekli, ör. "UART" veya "SBUS" (K10).
    """

    TUR: ClassVar[ParcaTuru] = ParcaTuru.ALICI

    protokol: str | None = None
    besleme_gerilimi_v: float | None = None
    baglanti: str | None = None


@dataclass(kw_only=True)
class GucDagitim(Parca):
    """
    Güç dağıtım kartı (PDB).

    Alanlar:
        maks_akim_a: Taşıyabildiği sürekli akım, A.
        cikis_gerilimleri_v: Regülatör çıkışları, V, ör. [5.0, 12.0].
        giris_gerilimi_maks_v: Kabul ettiği en yüksek pil gerilimi, V (K3).
        konnektor: Pil konnektörü (K12).
    """

    TUR: ClassVar[ParcaTuru] = ParcaTuru.GUC_DAGITIM

    maks_akim_a: float | None = None
    cikis_gerilimleri_v: list[float] | None = None
    giris_gerilimi_maks_v: float | None = None
    konnektor: str | None = None
