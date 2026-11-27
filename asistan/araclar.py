"""
Asistanın çağırabileceği araçlar (Gemini "function calling").

Model hesap yapmaz ve değer uydurmaz; sayılar yalnızca bu araçların döndürdüğü, programın
kendi hesap sınıflarından gelen değerlerdir. Okuma araçları onaysız çalışır. Değişiklik
yalnızca degisiklik_oner ile ÖNERİLİR; uygulama kullanıcının "Uygula" düğmesine bağlıdır.
"""

from dataclasses import dataclass
from typing import Any, Final

from arastirma.sohbet import AracTanimi
from asistan.ayarlar import KATALOG_SONUC_SINIRI
from asistan.oneriler import Oneri, OneriDeposu
from asistan.senaryo import HEDEF_ALANLARI, DegisiklikTuru, SenaryoHesaplayici, degisiklikleri_coz
from cekirdek.bicim import sayi_yaz
from cekirdek.hatalar import DroneProgramHatasi, GecersizDegerHatasi
from drone.modeller import BASLANGIC_TURU_ADLARI, DRONE_TURU_ADLARI
from elektronik.hesap.agirlik import AgirlikOzeti
from elektronik.hesap.ucus import HesapDegeri, UcusOzeti
from elektronik.hesap.uyum import UyumDurumu
from elektronik.parcalar.diger_parca import DigerParca
from elektronik.parcalar.parca import Parca
from elektronik.parcalar.serilestirme import ITKI_TABLOSU_ALANI, ParcaSerilestirici
from elektronik.parcalar.turler import DIGER_ALT_TUR_ADLARI, PARCA_DURUMU_ADLARI, PARCA_TURU_ADLARI, ParcaTuru
from elektronik.servis import ElektronikServisi
from sartname.kontrol import durum_adi
from sartname.modeller import BUYUKLUK_TANIMLARI, SINIR_TURU_ADLARI
from sartname.servis import SartnameServisi

# DEĞİŞTİRİLEBİLİR: Gerekçenin en çok uzunluğu (karakter).
EN_UZUN_GEREKCE: Final[int] = 1000

# Araç adları (model bu adlarla çağırır).
PROJE_OZETI: Final[str] = "proje_ozeti_getir"
PARCA_LISTESI: Final[str] = "parca_listesi_getir"
UYUM_SONUCLARI: Final[str] = "uyum_sonuclarini_getir"
UCUS_HESABI: Final[str] = "ucus_hesabini_getir"
SARTNAME_MADDELERI: Final[str] = "sartname_maddelerini_getir"
KATALOGDA_ARA: Final[str] = "katalogda_ara"
SENARYO_HESAPLA: Final[str] = "senaryo_hesapla"
DEGISIKLIK_ONER: Final[str] = "degisiklik_oner"

# Araç çalışırken panelde görünen kısa açıklama.
ARAC_ACIKLAMALARI: Final[dict[str, str]] = {
    PROJE_OZETI: "Proje özeti okunuyor",
    PARCA_LISTESI: "Parça listesi okunuyor",
    UYUM_SONUCLARI: "Uyum kontrolleri okunuyor",
    UCUS_HESABI: "Uçuş hesabı okunuyor",
    SARTNAME_MADDELERI: "Şartname maddeleri okunuyor",
    KATALOGDA_ARA: "Katalogda aranıyor",
    SENARYO_HESAPLA: "Değişikliğin etkisi hesaplanıyor",
    DEGISIKLIK_ONER: "Değişiklik önerisi hazırlanıyor",
}

BOS_NESNE: Final[dict[str, Any]] = {"type": "object", "properties": {}}
_DEGISIKLIK_SEMASI: Final[dict[str, Any]] = {
    "type": "array",
    "description": "Sırayla uygulanacak değişiklikler.",
    "items": {
        "type": "object",
        "properties": {
            "islem": {"type": "string", "enum": [t.value for t in DegisiklikTuru]},
            "parca_kimlik": {"type": "integer", "description": "Katalogdaki parça (parca_ekle, parca_degistir)."},
            "bag_kimlik": {
                "type": "integer",
                "description": "Drone'daki parça satırı, parca_listesi_getir'deki bag_kimlik (parca_degistir, adet_degistir, parca_cikar).",
            },
            "adet": {"type": "integer", "description": "Adet (parca_ekle, adet_degistir; parca_degistir'de isteğe bağlı)."},
            "ucus_suresi_dk": {"type": "number", "description": "Yeni uçuş süresi hedefi, dakika (hedef_degistir)."},
            "yuk_g": {"type": "number", "description": "Yeni yük hedefi, gram (hedef_degistir)."},
            "butce_tl": {"type": "number", "description": "Yeni bütçe, TL (hedef_degistir)."},
            "itki_agirlik": {
                "type": "number",
                "description": "Yeni itki/ağırlık hedefi, birimsiz, 1'den büyük (hedef_degistir).",
            },
            "kablo_vida_g": {
                "type": "number",
                "description": "Tartılmış kablo/vida ağırlığı, gram; tahmini payın yerine geçer (hedef_degistir).",
            },
        },
        "required": ["islem"],
    },
}


@dataclass
class AracSonucu:
    """
    Alanlar:
        veri: Modele geri verilecek JSON'a uygun sonuç.
        hata_mi: Araç hata verdiyse True (model düzeltip yeniden deneyebilir).
        oneri: degisiklik_oner yeni bir öneri kaydettiyse o öneri.
    """

    veri: Any
    hata_mi: bool = False
    oneri: Oneri | None = None


def _hesap(h: HesapDegeri) -> dict[str, Any]:
    return {"deger": h.deger, "tahmini": h.tahmini, "aciklama": h.aciklama}


def _agirlik(a: AgirlikOzeti) -> dict[str, Any]:
    return {
        "toplam_g": a.toplam_g, "sasi_g": a.sasi_g, "parcalar_g": a.parcalar_g, "yuk_g": a.yuk_g,
        "kablo_payi_g": a.kablo_payi_g, "kablo_payi_elle_mi": a.kablo_payi_elle_mi, "tahmini": a.tahmini,
        "agirligi_eksik_parcalar": a.agirligi_eksik_parcalar,
    }


def _ucus(u: UcusOzeti) -> dict[str, Any]:
    return {
        "toplam_itki_g": _hesap(u.toplam_itki_g), "itki_agirlik_orani": _hesap(u.itki_agirlik_orani),
        "hedef_itki_agirlik": u.hedef_itki_agirlik, "hedef_itki_agirlik_elle_mi": u.hedef_itki_agirlik_elle_mi,
        "asili_gaz_yuzde": _hesap(u.asili_gaz_yuzde),
        "asili_akim_a": _hesap(u.asili_akim_a), "toplam_maks_akim_a": _hesap(u.toplam_maks_akim_a),
        "ucus_suresi_dk": _hesap(u.ucus_suresi_dk), "hedef_ucus_suresi_dk": u.hedef_ucus_suresi_dk,
        "notlar": u.notlar,
    }


def _parca(parca: Parca) -> dict[str, Any]:
    """Parçanın modele verilen kısa hali (boş teknik alanlar atılır)."""
    teknik = {k: v for k, v in ParcaSerilestirici.teknik_sozluk(parca).items() if v is not None}
    if ITKI_TABLOSU_ALANI in teknik:
        teknik[ITKI_TABLOSU_ALANI] = f"{len(teknik[ITKI_TABLOSU_ALANI])} satırlık ölçülmüş itki tablosu var"
    sozluk = {
        "parca_kimlik": parca.kimlik, "tur": PARCA_TURU_ADLARI[parca.tur], "ad": parca.gorunen_ad,
        "agirlik_g": parca.agirlik_g, "dogrulandi": parca.dogrulandi, "teknik": teknik,
    }
    if isinstance(parca, DigerParca):
        sozluk["alt_tur"] = DIGER_ALT_TUR_ADLARI[parca.alt_tur]
    return sozluk


class AsistanAraclari:
    """
    Araç tanımlarını verir ve model çağırdığında aracı çalıştırır.

    Parametreler:
        elektronik: ElektronikServisi.
        sartname: SartnameServisi.
        senaryo: SenaryoHesaplayici.
        oneriler: OneriDeposu (degisiklik_oner öneriyi buraya kaydeder).
    """

    def __init__(
        self,
        elektronik: ElektronikServisi,
        sartname: SartnameServisi,
        senaryo: SenaryoHesaplayici,
        oneriler: OneriDeposu,
    ) -> None:
        self._elektronik = elektronik
        self._sartname = sartname
        self._senaryo = senaryo
        self._oneriler = oneriler

    def tanimlar(self, drone_var: bool) -> list[AracTanimi]:
        """
        Modele verilecek araçlar.

        Parametreler:
            drone_var: Açık drone varsa True; yoksa yalnızca katalog araması verilir.
        """
        katalog = AracTanimi(
            KATALOGDA_ARA,
            "Ortak parça kataloğunda arar. Değişiklik önerirken parça kimliğini buradan al.",
            {
                "type": "object",
                "properties": {
                    "metin": {"type": "string", "description": "Üretici, model veya ad içinden aranacak metin."},
                    "tur": {"type": "string", "enum": [t.value for t in ParcaTuru], "description": "Parça türü."},
                },
            },
        )
        if not drone_var:
            return [katalog]
        return [
            AracTanimi(PROJE_OZETI, "Açık drone'un özeti: tür, amaç, hedefler, ağırlık, uçuş özeti, uyum sayıları, "
                       "eksik zorunlu parçalar, şasi ölçüleri.", BOS_NESNE),
            AracTanimi(PARCA_LISTESI, "Drone'daki parçalar: bag_kimlik (satır), parça, adet, durum, ağırlık, teknik değerler.",
                       BOS_NESNE),
            AracTanimi(UYUM_SONUCLARI, "Uyum kontrolleri K1–K13 (durum ve açıklama) ve zorunlu parça sonuçları.", BOS_NESNE),
            AracTanimi(UCUS_HESABI, "Uçuş hesabı ayrıntısı: itki, itki/ağırlık, asılı kalma gazı ve akımı, tam gaz akımı, "
                       "uçuş süresi, ağırlık dökümü.", BOS_NESNE),
            AracTanimi(SARTNAME_MADDELERI, "Drone'a bağlı yarışma şartnamesinin maddeleri ve her maddeye uyum durumu.",
                       BOS_NESNE),
            katalog,
            AracTanimi(
                SENARYO_HESAPLA,
                "Değişikliklerin etkisini KAYDETMEDEN hesaplar (önce/sonra ağırlık, itki/ağırlık, uçuş süresi, uyum).",
                {"type": "object", "properties": {"degisiklikler": _DEGISIKLIK_SEMASI}, "required": ["degisiklikler"]},
            ),
            AracTanimi(
                DEGISIKLIK_ONER,
                "Kullanıcıya değişiklik önerir: panelde önce/sonra değerleriyle 'Uygula / Vazgeç' kartı gösterilir. "
                "Değişikliği UYGULAMAZ; uygulamak yalnızca kullanıcının kararıdır.",
                {
                    "type": "object",
                    "properties": {
                        "degisiklikler": _DEGISIKLIK_SEMASI,
                        "gerekce": {"type": "string", "description": "Kullanıcıya gösterilecek kısa Türkçe gerekçe."},
                    },
                    "required": ["degisiklikler", "gerekce"],
                },
            ),
        ]

    def calistir(self, ad: str, argumanlar: dict[str, Any], drone_kimlik: int | None) -> AracSonucu:
        """
        Aracı çalıştırır; programın hataları modele "hata" sonucu olarak döner.

        Parametreler:
            ad: Aracın adı.
            argumanlar: Modelin verdiği argümanlar.
            drone_kimlik: Açık drone; genel sohbette None.
        """
        try:
            if ad == KATALOGDA_ARA:
                return AracSonucu(self._katalogda_ara(argumanlar))
            if drone_kimlik is None:
                raise GecersizDegerHatasi("Açık drone yok; bu araç yalnızca bir drone'un sayfasında kullanılabilir.")
            if ad == DEGISIKLIK_ONER:
                return self._degisiklik_oner(drone_kimlik, argumanlar)
            islemler = {
                PROJE_OZETI: self._proje_ozeti,
                PARCA_LISTESI: self._parca_listesi,
                UYUM_SONUCLARI: self._uyum_sonuclari,
                UCUS_HESABI: self._ucus_hesabi,
                SARTNAME_MADDELERI: self._sartname_maddeleri,
            }
            if ad == SENARYO_HESAPLA:
                degisiklikler = degisiklikleri_coz(argumanlar.get("degisiklikler"))
                return AracSonucu(self._senaryo.hesapla(drone_kimlik, degisiklikler).sozluk())
            if ad not in islemler:
                raise GecersizDegerHatasi(f"Böyle bir araç yok: {ad}.")
            return AracSonucu(islemler[ad](drone_kimlik))
        except DroneProgramHatasi as hata:
            return AracSonucu({"hata": hata.mesaj}, hata_mi=True)

    # ---------- Okuma araçları ----------

    def _proje_ozeti(self, drone_kimlik: int) -> dict[str, Any]:
        ozet = self._elektronik.ozet(drone_kimlik)
        d, h, s = ozet.drone, ozet.hedefler, ozet.sasi_olculeri
        sartname = self._sartname.drone_sartnamesi(drone_kimlik)
        return {
            "drone": {
                "ad": d.ad, "tur": DRONE_TURU_ADLARI[d.drone_turu], "motor_sayisi": d.motor_sayisi, "amac": d.amac,
                "baslangic": BASLANGIC_TURU_ADLARI[d.baslangic_turu], "elle_girilen_sasi_agirligi_g": d.sasi_agirlik_g,
            },
            "hedefler": {alan: getattr(h, alan) for alan in HEDEF_ALANLARI},
            "agirlik": _agirlik(ozet.agirlik),
            "ucus": {
                "itki_agirlik_orani": _hesap(ozet.ucus.itki_agirlik_orani),
                "ucus_suresi_dk": _hesap(ozet.ucus.ucus_suresi_dk),
                "asili_gaz_yuzde": _hesap(ozet.ucus.asili_gaz_yuzde),
            },
            "uyum_sayilari": {durum.value: sum(1 for u in ozet.uyum if u.durum is durum) for durum in UyumDurumu},
            "zorunlu_parcalar": [{"etiket": z.etiket, "durum": z.durum.value, "aciklama": z.aciklama} for z in ozet.zorunluluklar],
            "sasi_olculeri_mm": {
                "en": s.en_mm, "boy": s.boy_mm, "yukseklik": s.yukseklik_mm,
                "dingil": s.dingil_mm, "dingil_kaynagi": s.dingil_kaynagi.value if s.dingil_kaynagi else None,
                "parca_sayisi": s.parca_sayisi, "tahmini": s.tahmini,
            } if s else None,
            "sartname": sartname.ad if sartname else None,
            "parca_satiri_sayisi": len(ozet.kalemler),
        }

    def _parca_listesi(self, drone_kimlik: int) -> dict[str, Any]:
        return {
            "parcalar": [
                {"bag_kimlik": bag.kimlik, "adet": bag.adet, "durum": PARCA_DURUMU_ADLARI[bag.durum], **_parca(parca)}
                for bag, parca in self._elektronik.kalemler(drone_kimlik)
            ]
        }

    def _uyum_sonuclari(self, drone_kimlik: int) -> dict[str, Any]:
        ozet = self._elektronik.ozet(drone_kimlik)
        return {
            "uyum": [
                {"kod": u.kod, "baslik": u.baslik, "durum": u.durum.value, "aciklama": u.aciklama,
                 "ilgili_parcalar": list(u.ilgili_parcalar), "tahmini": u.tahmini}
                for u in ozet.uyum
            ],
            "zorunlu_parcalar": [{"etiket": z.etiket, "durum": z.durum.value, "aciklama": z.aciklama} for z in ozet.zorunluluklar],
        }

    def _ucus_hesabi(self, drone_kimlik: int) -> dict[str, Any]:
        ozet = self._elektronik.ozet(drone_kimlik)
        return {"ucus": _ucus(ozet.ucus), "agirlik": _agirlik(ozet.agirlik)}

    def _sartname_maddeleri(self, drone_kimlik: int) -> dict[str, Any]:
        rapor = self._sartname.rapor(drone_kimlik)
        if rapor.sartname is None:
            return {"sartname": None, "maddeler": [], "not": "Bu drone'a şartname bağlanmamış."}
        maddeler = []
        for s in rapor.sonuclar:
            m = s.madde
            tanim = BUYUKLUK_TANIMLARI[m.buyukluk]
            maddeler.append({
                "madde_no": m.madde_no, "sayfa": m.sayfa, "aciklama": m.aciklama, "buyukluk": tanim.ad,
                "sinir": f"{SINIR_TURU_ADLARI[m.sinir_turu]} {sayi_yaz(m.deger) if m.deger is not None else ''} {tanim.birim}".strip(),
                "onaylandi": m.onaylandi, "durum": durum_adi(s.durum), "tasarim": s.tasarim,
                "degerlendirme": s.aciklama, "tahmini": s.tahmini,
            })
        return {"sartname": rapor.sartname.ad, "maddeler": maddeler}

    def _katalogda_ara(self, argumanlar: dict[str, Any]) -> dict[str, Any]:
        metin = argumanlar.get("metin") or ""
        tur_degeri = argumanlar.get("tur")
        if not isinstance(metin, str):
            raise GecersizDegerHatasi("metin bir yazı olmalı.")
        try:
            tur = ParcaTuru(tur_degeri) if tur_degeri else None
        except ValueError:
            raise GecersizDegerHatasi(f"Parça türü tanınmıyor: {tur_degeri!r}.") from None
        parcalar = self._elektronik.katalog_ara(metin, tur=tur)
        return {"sonuclar": [_parca(p) for p in parcalar[:KATALOG_SONUC_SINIRI]], "toplam_bulunan": len(parcalar)}

    # ---------- Öneri ----------

    def _degisiklik_oner(self, drone_kimlik: int, argumanlar: dict[str, Any]) -> AracSonucu:
        gerekce = argumanlar.get("gerekce")
        if not isinstance(gerekce, str) or not gerekce.strip():
            raise GecersizDegerHatasi("Kullanıcıya gösterilecek bir gerekçe yazın.")
        degisiklikler = degisiklikleri_coz(argumanlar.get("degisiklikler"))
        senaryo = self._senaryo.hesapla(drone_kimlik, degisiklikler)
        oneri = self._oneriler.ekle(drone_kimlik, gerekce.strip()[:EN_UZUN_GEREKCE], degisiklikler, senaryo.sozluk())
        return AracSonucu(
            {
                "oneri_kimlik": oneri.kimlik,
                "durum": "Kullanıcıya 'Uygula / Vazgeç' kartı gösterildi; değişiklik HENÜZ UYGULANMADI.",
                "senaryo": senaryo.sozluk(),
            },
            oneri=oneri,
        )
