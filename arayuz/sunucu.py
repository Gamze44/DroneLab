"""
Yerel FastAPI sunucusunun kurulumu.

Sunucu yalnızca bu bilgisayarda çalışır ve tarayıcıya arayüz sayfalarını verir.
Programa özel hatalar burada yakalanıp kullanıcıya Türkçe mesajla JSON olarak
döndürülür; böylece her uçta ayrı hata yakalama yazmak gerekmez.
"""

from collections.abc import Callable
import logging
from pathlib import Path
from typing import Final

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from arayuz.drone_rotalari import drone_rotalarini_olustur
from arayuz.elektronik_rotalari import elektronik_rotalarini_olustur
from arayuz.parametreler import Kimlik
from arayuz.guvenlik import (
    GuvenlikBasliklari,
    HostDenetimi,
    IstekBoyutuSiniri,
    IstekBoyutuSinirlari,
    KaynakDenetimi,
)
from cekirdek.ayarlar import (
    EN_BUYUK_ISTEK_MB,
    EN_BUYUK_SARTNAME_MB,
    EN_BUYUK_YUKLEME_MB,
    EN_FAZLA_SARTNAME_SAYFASI,
    IZINLI_HOSTLAR,
    PROGRAM_ADI,
    PROGRAM_SURUMU,
    SIMGE_YOLU,
    STATIK_KLASORU,
    VERI_KLASORU,
)
from cekirdek.hatalar import (
    DesteklenmeyenDosyaHatasi,
    DroneProgramHatasi,
    KayitBulunamadiHatasi,
    KayitZatenVarHatasi,
    YapayZekaHatasi,
)
from arastirma.istemci import SaglayiciUretici, YapayZekaIstemcisi, gemini_uret
from arayuz.maliyet_rotalari import maliyet_rotalarini_olustur
from arayuz.oneri_rotalari import oneri_rotalarini_olustur
from arayuz.sartname_rotalari import sartname_rotalarini_olustur
from drone.servis import DroneServisi
from elektronik.oneri.servis import OneriServisi
from elektronik.servis import ElektronikServisi
from maliyet.kur import tcmb_xml_getir
from maliyet.servis import MaliyetServisi
from sartname.servis import SartnameServisi

ANA_SAYFA_DOSYASI: Final[str] = "index.html"
DRONE_SAYFASI_DOSYASI: Final[str] = "drone.html"
AYARLAR_SAYFASI_DOSYASI: Final[str] = "ayarlar.html"
STATIK_ADRES_ONEKI: Final[str] = "/statik"
# Dosya sınırı genel yükleme sınırından farklı olan adresler (bkz. IstekBoyutuSiniri).
SARTNAME_YUKLEME_ADRESI: Final[str] = "/api/sartnameler"

# HTML sayfalarındaki yer tutucular ve yerine yazılacak değerler (bkz. sayfa_yaniti).
SAYFA_YER_TUTUCULARI: Final[dict[str, str]] = {
    "{{PROGRAM_ADI}}": PROGRAM_ADI,
    "{{PROGRAM_ADI_BUYUK}}": PROGRAM_ADI.upper(),
    "{{SIMGE}}": f"{STATIK_ADRES_ONEKI}/{SIMGE_YOLU.name}",
    "{{SARTNAME_SAYFA_SINIRI}}": str(EN_FAZLA_SARTNAME_SAYFASI),
}

HTTP_HATALI_ISTEK: Final[int] = 400
HTTP_BULUNAMADI: Final[int] = 404
HTTP_CAKISMA: Final[int] = 409
HTTP_DESTEKLENMEYEN_TUR: Final[int] = 415
HTTP_ISLENEMEYEN_ISTEK: Final[int] = 422
HTTP_SUNUCU_HATASI: Final[int] = 500

BEKLENMEYEN_HATA_MESAJI: Final[str] = (
    "Beklenmeyen bir hata oluştu. Lütfen işlemi tekrar deneyin; sorun sürerse "
    "program penceresindeki hata kaydını kontrol edin."
)
GECERSIZ_ISTEK_MESAJI: Final[str] = "Gönderilen bilgiler eksik veya hatalı. Lütfen alanları kontrol edin."

gunluk = logging.getLogger(__name__)


def _hata_yakalayicilari_ekle(sunucu: FastAPI) -> None:
    """
    Hataları uygun HTTP koduyla JSON'a çeviren yakalayıcıları ekler.

    Yanıt biçimi: {"hata": "<Türkçe mesaj>", "rehber": [...]}  (rehber yalnızca varsa)
    """

    @sunucu.exception_handler(DroneProgramHatasi)
    def program_hatasi(_: Request, hata: DroneProgramHatasi) -> JSONResponse:
        govde: dict[str, object] = {"hata": hata.mesaj}
        kod = HTTP_HATALI_ISTEK
        if isinstance(hata, KayitBulunamadiHatasi):
            kod = HTTP_BULUNAMADI
        elif isinstance(hata, KayitZatenVarHatasi):
            # Arayüz mevcut kaydı önerebilsin diye kimliği de gönderilir.
            kod = HTTP_CAKISMA
            govde["mevcut_kimlik"] = hata.mevcut_kimlik
        elif isinstance(hata, YapayZekaHatasi):
            kod = hata.http_kodu
        elif isinstance(hata, DesteklenmeyenDosyaHatasi):
            kod = HTTP_DESTEKLENMEYEN_TUR
            if hata.rehber:
                govde["rehber"] = hata.rehber
        return JSONResponse(status_code=kod, content=govde)

    @sunucu.exception_handler(RequestValidationError)
    def gecersiz_istek(_: Request, hata: RequestValidationError) -> JSONResponse:
        # FastAPI'nin İngilizce doğrulama mesajları kullanıcıya gösterilmez; ayrıntı konsola yazılır.
        gunluk.warning("Geçersiz istek: %s", hata.errors())
        return JSONResponse(status_code=HTTP_ISLENEMEYEN_ISTEK, content={"hata": GECERSIZ_ISTEK_MESAJI})

    @sunucu.exception_handler(Exception)
    def beklenmeyen_hata(_: Request, hata: Exception) -> JSONResponse:
        # Ayrıntı kullanıcıya değil konsola yazılır; kullanıcı sade mesaj görür.
        gunluk.exception("Beklenmeyen hata: %s", hata)
        return JSONResponse(status_code=HTTP_SUNUCU_HATASI, content={"hata": BEKLENMEYEN_HATA_MESAJI})


def sayfa_yaniti(dosya_adi: str) -> HTMLResponse:
    """
    HTML sayfasını, içindeki yer tutucuları ayardaki değerlerle doldurarak gönderir.

    Programın adı sayfalara elle yazılmaz; {{PROGRAM_ADI}} gibi yer tutucular burada
    cekirdek/ayarlar.py'deki değerle değiştirilir. Böylece adı değiştirmek için tek bir
    ayarı değiştirmek yeterli olur.

    Parametreler:
        dosya_adi: arayuz/statik içindeki HTML dosyasının adı.
    """
    metin = (STATIK_KLASORU / dosya_adi).read_text(encoding="utf-8")
    for yer_tutucu, deger in SAYFA_YER_TUTUCULARI.items():
        metin = metin.replace(yer_tutucu, deger)
    return HTMLResponse(metin)


def _guvenlik_katmanlarini_ekle(sunucu: FastAPI, izinli_hostlar: tuple[str, ...]) -> None:
    """
    Güvenlik ara katmanlarını ekler (ayrıntı: arayuz/guvenlik.py).

    Starlette'te son eklenen katman en dışta çalışır. Sıra (dıştan içe): güvenlik
    başlıkları -> Host -> kaynak (CSRF) -> istek boyutu -> uygulama. Başlıklar en dışta
    olduğu için reddedilen isteklerin yanıtlarına da eklenir.
    """
    sinirlar = IstekBoyutuSinirlari(
        dosya_sinirlari_mb={SARTNAME_YUKLEME_ADRESI: EN_BUYUK_SARTNAME_MB},
        varsayilan_dosya_mb=EN_BUYUK_YUKLEME_MB,
        diger_mb=EN_BUYUK_ISTEK_MB,
    )
    sunucu.add_middleware(IstekBoyutuSiniri, sinirlar=sinirlar)
    sunucu.add_middleware(KaynakDenetimi)
    sunucu.add_middleware(HostDenetimi, izinli_hostlar=izinli_hostlar)
    sunucu.add_middleware(GuvenlikBasliklari)


def sunucu_olustur(
    veri_klasoru: Path = VERI_KLASORU,
    saglayici_uretici: SaglayiciUretici = gemini_uret,
    kur_getirici: Callable[[], bytes] = tcmb_xml_getir,
    izinli_hostlar: tuple[str, ...] | None = None,
) -> FastAPI:
    """
    FastAPI uygulamasını oluşturur; sayfaları, statik dosyaları ve API uçlarını bağlar.

    Parametreler:
        veri_klasoru: Veritabanı ve şasi dosyalarının klasörü (testlerde geçici klasör verilir).
        saglayici_uretici: Yapay zeka sağlayıcısını üreten fonksiyon; testlerde sahtesi verilir
            ki gerçek Gemini isteği yapılmasın.
        kur_getirici: TCMB kur dosyasını indiren fonksiyon; testlerde sahtesi verilir.
        izinli_hostlar: Kabul edilen Host adları; verilmezse IZINLI_HOSTLAR (çağrı anında
            okunur ki testler test istemcisinin adını ekleyebilsin).
    Dönüş:
        Çalıştırılmaya hazır FastAPI nesnesi.
    """
    # API belgeleri (/docs, /redoc, /openapi.json) kapalı: kullanıcıya gerekmez ve
    # saldırgana bütün uçların haritasını verir.
    sunucu = FastAPI(title=PROGRAM_ADI, version=PROGRAM_SURUMU, docs_url=None, redoc_url=None, openapi_url=None)
    _hata_yakalayicilari_ekle(sunucu)
    _guvenlik_katmanlarini_ekle(sunucu, izinli_hostlar if izinli_hostlar is not None else IZINLI_HOSTLAR)
    elektronik = ElektronikServisi(veri_klasoru)
    maliyet = MaliyetServisi(elektronik, veri_klasoru, kur_getirici)
    yapay_zeka = YapayZekaIstemcisi(veri_klasoru, saglayici_uretici)
    sartname = SartnameServisi(veri_klasoru, elektronik, maliyet, yapay_zeka)
    sunucu.include_router(drone_rotalarini_olustur(DroneServisi(veri_klasoru)))
    sunucu.include_router(elektronik_rotalarini_olustur(elektronik))
    sunucu.include_router(oneri_rotalarini_olustur(OneriServisi(elektronik, yapay_zeka, sartname.oneri_maddeleri)))
    sunucu.include_router(maliyet_rotalarini_olustur(maliyet))
    sunucu.include_router(sartname_rotalarini_olustur(sartname))
    sunucu.mount(STATIK_ADRES_ONEKI, StaticFiles(directory=STATIK_KLASORU), name="statik")

    @sunucu.get("/", include_in_schema=False)
    def ana_sayfa() -> HTMLResponse:
        """Tarayıcıya ana sayfayı (üç seçenek) gönderir."""
        return sayfa_yaniti(ANA_SAYFA_DOSYASI)

    @sunucu.get("/drone/{kimlik}", include_in_schema=False)
    def drone_sayfasi(kimlik: Kimlik) -> HTMLResponse:
        """Drone çalışma sayfasını gönderir; veriyi sayfa API'den kendisi çeker."""
        return sayfa_yaniti(DRONE_SAYFASI_DOSYASI)

    @sunucu.get("/ayarlar", include_in_schema=False)
    def ayarlar_sayfasi() -> HTMLResponse:
        """Ayarlar sayfasını (Gemini anahtarı, model, günlük sınır) gönderir."""
        return sayfa_yaniti(AYARLAR_SAYFASI_DOSYASI)

    return sunucu
