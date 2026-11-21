"""
Parça türleri, alt türler, pil kimyaları, drone'daki parça durumları ve
ekranda gösterilecek Türkçe adlar.
"""

from enum import Enum
from typing import Final


class ParcaTuru(str, Enum):
    """Katalogdaki parça türü. Değerler veritabanında saklanır; değiştirilmemeli."""

    MOTOR = "motor"
    PERVANE = "pervane"
    ESC = "esc"
    PIL = "pil"
    UCUS_KARTI = "ucus_karti"
    ALICI = "alici"
    GUC_DAGITIM = "guc_dagitim"
    DIGER = "diger"


class DigerAltTur(str, Enum):
    """İkinci grup parçaların alt türü (ilk sürümde yalnızca ağırlık ve gerilim kontrolü)."""

    KAMERA = "kamera"
    VTX = "vtx"
    GPS = "gps"
    TELEMETRI = "telemetri"
    YUK = "yuk"


class PilKimyasi(str, Enum):
    """Pil kimyası; dolu hücre gerilimi buna göre değişir (LiHV daha yüksek)."""

    LIPO = "lipo"
    LIHV = "lihv"
    LIION = "liion"


class ParcaDurumu(str, Enum):
    """
    Parçanın BİR DRONE'daki durumu.

    Katalog tüm dronelar arasında ortak olduğu için bu bilgi parçada değil,
    drone–parça bağında (DroneParcasi) tutulur.
    """

    ELIMDE = "elimde"
    ONERILEN = "onerilen"
    PLANLANAN = "planlanan"


# DEĞİŞTİRİLEBİLİR: Ekranda görünen adlar.
PARCA_TURU_ADLARI: Final[dict[ParcaTuru, str]] = {
    ParcaTuru.MOTOR: "Motor",
    ParcaTuru.PERVANE: "Pervane",
    ParcaTuru.ESC: "ESC (hız kontrolcüsü)",
    ParcaTuru.PIL: "Pil",
    ParcaTuru.UCUS_KARTI: "Uçuş kontrol kartı (FC)",
    ParcaTuru.ALICI: "Alıcı",
    ParcaTuru.GUC_DAGITIM: "Güç dağıtım kartı (PDB)",
    ParcaTuru.DIGER: "Diğer",
}

ALT_TUR_GEREKLI_MESAJI: Final[str] = "Diğer parçalar için alt tür (kamera, VTX, GPS…) seçilmeli."

DIGER_ALT_TUR_ADLARI: Final[dict[DigerAltTur, str]] = {
    DigerAltTur.KAMERA: "Kamera",
    DigerAltTur.VTX: "Video verici (VTX)",
    DigerAltTur.GPS: "GPS",
    DigerAltTur.TELEMETRI: "Telemetri",
    DigerAltTur.YUK: "Yük",
}

PIL_KIMYASI_ADLARI: Final[dict[PilKimyasi, str]] = {
    PilKimyasi.LIPO: "LiPo",
    PilKimyasi.LIHV: "LiHV",
    PilKimyasi.LIION: "Li-ion",
}

PARCA_DURUMU_ADLARI: Final[dict[ParcaDurumu, str]] = {
    ParcaDurumu.ELIMDE: "Elimde",
    ParcaDurumu.ONERILEN: "Önerilen",
    ParcaDurumu.PLANLANAN: "Planlanan",
}

# DEĞİŞTİRİLEBİLİR: Alan adı -> ekranda ve hata mesajlarında görünen etiket (birimiyle).
ALAN_ETIKETLERI: Final[dict[str, str]] = {
    "uretici": "Üretici (marka)",
    "model": "Model",
    "ad": "Görünen ad",
    "agirlik_g": "Ağırlık (g)",
    "kaynak_url": "Kaynak bağlantısı",
    "notlar": "Notlar",
    # Motor
    "kv": "KV (dev/dk/V)",
    "maks_akim_a": "En büyük akım (A)",
    "boyut": "Stator boyutu (ör. 2207)",
    "min_s": "En az hücre (S)",
    "maks_s": "En çok hücre (S)",
    "montaj_deseni_mm": "Montaj deseni (mm)",
    "onerilen_pervane_min_inc": "Önerilen en küçük pervane (inç)",
    "onerilen_pervane_maks_inc": "Önerilen en büyük pervane (inç)",
    "itki_tablosu": "İtki tablosu",
    # Pervane
    "cap_inc": "Çap (inç)",
    "hatve_inc": "Hatve / adım (inç)",
    "kanat_sayisi": "Kanat sayısı",
    "mil_deligi_mm": "Mil deliği (mm)",
    # ESC
    "surekli_akim_a": "Sürekli akım (A)",
    "tepe_akim_a": "Anlık (tepe) akım (A)",
    "protokoller": "Desteklenen protokoller",
    "montaj_olcusu_mm": "Montaj ölçüsü (mm)",
    "kanal_sayisi": "Kanal sayısı",
    "konnektor": "Konnektör",
    # Pil
    "hucre_sayisi_s": "Hücre sayısı (S)",
    "kapasite_mah": "Kapasite (mAh)",
    "desarj_c": "Deşarj oranı (C)",
    "kimya": "Kimya",
    # Uçuş kartı
    "giris_gerilimi_min_v": "En düşük giriş gerilimi (V)",
    "giris_gerilimi_maks_v": "En yüksek giriş gerilimi (V)",
    "esc_protokolleri": "Desteklenen ESC protokolleri",
    "alici_protokolleri": "Desteklenen alıcı protokolleri",
    "uart_sayisi": "UART sayısı",
    "bec_cikislari_v": "BEC çıkışları (V)",
    "dahili_pdb": "Dahili güç dağıtımı",
    # Alıcı
    "protokol": "Protokol",
    "besleme_gerilimi_v": "Besleme gerilimi (V)",
    "baglanti": "Bağlantı (UART / SBUS)",
    # Güç dağıtım
    "cikis_gerilimleri_v": "Çıkış gerilimleri (V)",
    # Diğer
    "alt_tur": "Alt tür",
    "guc_w": "Güç (W)",
    # İtki noktası
    "pervane": "Pervane",
    "gerilim_v": "Gerilim (V)",
    "gaz_yuzde": "Gaz (%)",
    "itki_g": "İtki (g)",
    "akim_a": "Akım (A)",
}


def alan_etiketi(alan: str) -> str:
    """Alanın Türkçe etiketini döndürür; tanımlı değilse alan adını."""
    return ALAN_ETIKETLERI.get(alan, alan)
