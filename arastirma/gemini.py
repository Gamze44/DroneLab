"""
Google Gemini Interactions API istemcisi (REST, yalnızca standart kütüphane).

D:\\uzay-koc\\sohbet\\gemini.py örnek alınarak yazıldı; iki proje birbirine bağlı
değildir. Google Arama aracı KULLANILMAZ: arama Gemini 3 ve sonrası modellerde
ücretsiz kotada yoktur ve kullanıcı ücretli kullanım istemedi. Bu yüzden model
yalnızca kendi bilgisinden yanıt verir; yanıtlar "doğrulanmadı" sayılır.
Asistan sohbetinde modele yalnızca programın KENDİ araçları (hesap sınıfları) verilir.

İki kullanım:
    - json_uret: tek seferlik, şemaya uyan JSON yanıtı (öneri, şartname çıkarımı).
    - sohbet_et: çok turlu, araç çağıran, istenirse akışlı (SSE) sohbet (asistan).

Güvenlik: anahtar yalnızca istek başlığında gönderilir; hiçbir hata mesajına,
loga veya yanıta yazılmaz. İstekler store=false ile gönderilir (sohbet Google
tarafında saklanmaz; bu yüzden geçmiş her turda yeniden gönderilir).
"""

from collections.abc import Callable, Iterable, Iterator
from http import HTTPStatus
import json
import logging
import ssl
from typing import Any, Final
import urllib.error
import urllib.request

from arastirma.saglayici import ArastirmaSaglayicisi
from arastirma.sohbet import (
    ARAC_CAGRISI,
    ARAC_SERBEST,
    METIN_BLOGU,
    MODEL_CIKTISI,
    OLAY_ARAC_CAGRISI,
    OLAY_BITTI,
    OLAY_METIN,
    AracCagrisi,
    AracTanimi,
    SohbetOlayi,
)
from cekirdek.ag import ssl_baglami
from cekirdek.hatalar import YapayZekaHatasi

URL: Final[str] = "https://generativelanguage.googleapis.com/v1beta/interactions"
API_REVIZYONU: Final[str] = "2026-05-20"

# DEĞİŞTİRİLEBİLİR: Ayarlarda seçilebilecek modeller. Google'ın fiyat sayfasında (21.11.2026)
# üçü için de girdi/çıktı "Free of charge" (ücretsiz katman) yazıyor ve üçü de araç çağırmayı
# (function calling) destekliyor. Otomatik seçimin sırası arastirma/model_secici.py'dedir.
MODELLER: Final[tuple[str, ...]] = ("gemini-3.6-flash", "gemini-3.8-flash", "gemini-3.5-flash-lite")
VARSAYILAN_MODEL: Final[str] = MODELLER[0]

# DEĞİŞTİRİLEBİLİR: Yanıt için en çok bekleme süresi, saniye.
ZAMAN_ASIMI_SN: Final[float] = 90.0

# DEĞİŞTİRİLEBİLİR: Sohbette (asistan) modelin "düşünme" seviyesi. Varsayılan seviye (medium)
# kısa sorularda bile yanıtı onlarca saniye geciktiriyordu; sayılar zaten programın araçlarından
# geldiği için daha az düşünme yeterli. Değerler Google belgesindeki desteklenen seviyelerdir
# (3.8-flash "minimal"i desteklemez). Listede olmayan modelde ayar gönderilmez.
SOHBET_DUSUNME_SEVIYELERI: Final[dict[str, str]] = {
    "gemini-3.8-flash": "low",
    "gemini-3.6-flash": "low",
    "gemini-3.5-flash-lite": "minimal",
}

AYRINTI_SINIRI: Final[int] = 200
ULASILAMADI_MESAJI: Final[str] = "Gemini'ye ulaşılamadı. İnternet bağlantınızı kontrol edin."
BASARISIZ_DURUMLAR: Final[frozenset[str]] = frozenset({"failed", "cancelled"})
DUSUNCE: Final[str] = "thought"
SSE_BITTI: Final[str] = "[DONE]"
# Akış içi "error" olayındaki kod metni -> eşdeğer HTTP kodu.
AKIS_HATA_KODLARI: Final[dict[str, int]] = {
    "exhausted": HTTPStatus.TOO_MANY_REQUESTS,
    "rate": HTTPStatus.TOO_MANY_REQUESTS,
    "unavailable": HTTPStatus.SERVICE_UNAVAILABLE,
    "overload": HTTPStatus.SERVICE_UNAVAILABLE,
    "not_found": HTTPStatus.NOT_FOUND,
    "invalid": HTTPStatus.BAD_REQUEST,
}

gunluk = logging.getLogger(__name__)


def hata_ayrintisi(govde: str) -> str:
    """Google hata gövdesinden mesajı çıkarır ({"error": {...}} veya [{"error": {...}}])."""
    try:
        veri = json.loads(govde)
    except ValueError:
        return ""
    if isinstance(veri, list):
        veri = veri[0] if veri else {}
    hata = veri.get("error", {}) if isinstance(veri, dict) else {}
    return str(hata.get("message", "")) if isinstance(hata, dict) else ""


def hata_cevir(kod: int, ayrinti: str = "") -> YapayZekaHatasi:
    """HTTP hata kodunu kullanıcının anlayacağı Türkçe hataya çevirir."""
    if kod == HTTPStatus.BAD_REQUEST and "key" in ayrinti.lower():
        return YapayZekaHatasi("Gemini API anahtarı geçersiz. Ayarlar sayfasından yeni anahtar girin.", HTTPStatus.UNAUTHORIZED)
    if kod in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
        return YapayZekaHatasi("Gemini API anahtarı geçersiz ya da bu modele erişim izni yok.", HTTPStatus.UNAUTHORIZED)
    if kod == HTTPStatus.NOT_FOUND:
        return YapayZekaHatasi("Gemini modeli bulunamadı. Ayarlar sayfasından başka bir model seçin.", HTTPStatus.NOT_FOUND)
    if kod == HTTPStatus.TOO_MANY_REQUESTS:
        return YapayZekaHatasi(
            "Gemini'nin ücretsiz kullanım sınırına ulaşıldı. Biraz bekleyip (gerekirse yarın) tekrar deneyin.",
            HTTPStatus.TOO_MANY_REQUESTS,
            ayrinti,
        )
    if kod == HTTPStatus.SERVICE_UNAVAILABLE:
        # Model geçici olarak aşırı yüklü; otomatik model seçimi sıradaki modele geçebilsin diye ayrı kod.
        return YapayZekaHatasi("Gemini şu an çok yoğun. Biraz sonra tekrar deneyin.", HTTPStatus.SERVICE_UNAVAILABLE, ayrinti)
    if kod >= HTTPStatus.INTERNAL_SERVER_ERROR:
        return YapayZekaHatasi("Gemini şu an yanıt veremiyor. Biraz sonra tekrar deneyin.", HTTPStatus.BAD_GATEWAY)
    return YapayZekaHatasi(f"Gemini isteği reddetti: {ayrinti[:AYRINTI_SINIRI] or kod}", HTTPStatus.BAD_REQUEST)


class SseOkuyucu:
    """
    Server-Sent Events (SSE) satırlarını olay sözlüklerine çevirir.

    Her olay "event: ..." ve bir ya da daha çok "data: ..." satırından oluşur ve boş satırla
    biter. Veri JSON'dur; akışın sonundaki "[DONE]" işareti ve çözülemeyen veri atlanır.
    """

    @classmethod
    def olaylar(cls, satirlar: Iterable[bytes]) -> Iterator[dict[str, Any]]:
        """
        Parametreler:
            satirlar: Yanıtın bayt satırları (ör. açık HTTP yanıtı).
        Dönüş:
            Olay sözlükleri.
        """
        veri: list[str] = []
        for ham in satirlar:
            satir = ham.decode("utf-8").rstrip("\r\n")
            if not satir:
                yield from cls._coz(veri)
                veri = []
            elif not satir.startswith(":"):  # ":" ile başlayan satır yorumdur
                alan, _, deger = satir.partition(":")
                if alan == "data":
                    veri.append(deger[1:] if deger.startswith(" ") else deger)
        yield from cls._coz(veri)

    @staticmethod
    def _coz(veri: list[str]) -> Iterator[dict[str, Any]]:
        metin = "\n".join(veri).strip()
        if not metin or metin == SSE_BITTI:
            return
        try:
            olay = json.loads(metin)
        except ValueError:
            gunluk.warning("Gemini akışında çözülemeyen veri atlandı.")
            return
        if isinstance(olay, dict):
            yield olay


def akis_hatasi(hata: dict[str, Any]) -> YapayZekaHatasi:
    """
    Akış içinde gelen "error" olayını Türkçe hataya çevirir.

    Kota ve yoğunluk hataları HTTP karşılıklarıyla aynı koda çevrilir ki otomatik model
    seçimi sıradaki modele geçebilsin.
    """
    kod_metni = str(hata.get("code", "")).lower()
    ayrinti = str(hata.get("message", ""))
    for anahtar_soz, kod in AKIS_HATA_KODLARI.items():
        if anahtar_soz in kod_metni:
            return hata_cevir(kod, ayrinti)
    return YapayZekaHatasi("Gemini yanıtı yarıda kesildi. Tekrar deneyin.", HTTPStatus.BAD_GATEWAY, ayrinti)


class GeminiSaglayicisi(ArastirmaSaglayicisi):
    """
    Gemini Interactions API istemcisi: şemalı JSON yanıtı ve araç kullanan, akışlı sohbet.

    Parametreler:
        anahtar: Gemini API anahtarı.
        model: MODELLER içinden model adı.
        gonder: Tek seferlik isteği gönderen fonksiyon; testlerde sahtesi verilir (gerçek istek yapılmaz).
        akis_gonder: Akışlı isteği gönderip olay sözlüklerini veren fonksiyon; testlerde sahtesi verilir.
        zaman_asimi: Saniye.
    """

    def __init__(
        self,
        anahtar: str,
        model: str = VARSAYILAN_MODEL,
        gonder: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        akis_gonder: Callable[[dict[str, Any]], Iterable[dict[str, Any]]] | None = None,
        zaman_asimi: float = ZAMAN_ASIMI_SN,
    ) -> None:
        if model not in MODELLER:
            raise YapayZekaHatasi(f"Bilinmeyen Gemini modeli: {model}", HTTPStatus.BAD_REQUEST)
        self._anahtar = anahtar
        self.model = model
        self._zaman_asimi = zaman_asimi
        self._ssl: ssl.SSLContext | None = None
        self._gonder = gonder or self._http
        self._akis_gonder = akis_gonder or self._akis_http

    def __repr__(self) -> str:
        # Nesne bir hata kaydına yazılırsa anahtar görünmesin.
        return f"GeminiSaglayicisi(model={self.model!r})"

    def _istek(self, govde: dict[str, Any]) -> urllib.request.Request:
        """HTTP isteğini hazırlar; anahtar yalnızca başlıkta durur."""
        self._ssl = self._ssl or ssl_baglami()
        return urllib.request.Request(
            URL,
            data=json.dumps(govde).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json", "x-goog-api-key": self._anahtar, "Api-Revision": API_REVIZYONU},
        )

    @staticmethod
    def _http_hatasi(hata: urllib.error.HTTPError) -> YapayZekaHatasi:
        """HTTP hata yanıtını Türkçe hataya çevirir."""
        try:
            ayrinti = hata_ayrintisi(hata.read().decode("utf-8"))
        except OSError:
            ayrinti = ""
        return hata_cevir(hata.code, ayrinti)

    def _http(self, govde: dict[str, Any]) -> dict[str, Any]:
        """İsteği gönderir ve JSON yanıtını döndürür."""
        istek = self._istek(govde)
        try:
            with urllib.request.urlopen(istek, timeout=self._zaman_asimi, context=self._ssl) as yanit:
                return json.loads(yanit.read().decode("utf-8"))
        except urllib.error.HTTPError as hata:
            raise self._http_hatasi(hata) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise YapayZekaHatasi(ULASILAMADI_MESAJI, HTTPStatus.GATEWAY_TIMEOUT) from None
        except ValueError:
            raise YapayZekaHatasi("Gemini'den anlaşılamayan bir yanıt geldi. Tekrar deneyin.", HTTPStatus.BAD_GATEWAY) from None

    def _akis_http(self, govde: dict[str, Any]) -> Iterator[dict[str, Any]]:
        """Akışlı isteği gönderir; SSE olaylarını geldikçe verir."""
        istek = self._istek(govde)
        try:
            yanit = urllib.request.urlopen(istek, timeout=self._zaman_asimi, context=self._ssl)
        except urllib.error.HTTPError as hata:
            raise self._http_hatasi(hata) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise YapayZekaHatasi(ULASILAMADI_MESAJI, HTTPStatus.GATEWAY_TIMEOUT) from None
        with yanit:
            try:
                yield from SseOkuyucu.olaylar(yanit)
            except (TimeoutError, OSError):
                raise YapayZekaHatasi("Gemini bağlantısı yanıt sırasında koptu. Tekrar deneyin.", HTTPStatus.GATEWAY_TIMEOUT) from None

    # ---------- Sohbet ----------

    def sohbet_et(
        self,
        sistem_talimati: str,
        girdiler: list[dict[str, Any]],
        araclar: list[AracTanimi],
        akis: bool = True,
        arac_kullanimi: str = ARAC_SERBEST,
    ) -> Iterator[SohbetOlayi]:
        """Bkz. ArastirmaSaglayicisi.sohbet_et. store=false: geçmiş her turda yeniden gönderilir."""
        govde: dict[str, Any] = {
            "model": self.model,
            "input": girdiler,
            "system_instruction": sistem_talimati,
            "store": False,
        }
        ayar: dict[str, Any] = {}
        if self.model in SOHBET_DUSUNME_SEVIYELERI:
            ayar["thinking_level"] = SOHBET_DUSUNME_SEVIYELERI[self.model]
        if araclar:
            # Araç tanımları sohbette saklanmaz; her istekte yeniden verilir.
            govde["tools"] = [
                {"type": "function", "name": a.ad, "description": a.aciklama, "parameters": a.parametreler} for a in araclar
            ]
            ayar["tool_choice"] = arac_kullanimi
        if ayar:
            govde["generation_config"] = ayar
        if akis:
            govde["stream"] = True
            return self._akisi_coz(self._akis_gonder(govde))
        return self._yanittan_olaylar(self._gonder(govde))

    @staticmethod
    def _durumu_denetle(etkilesim: dict[str, Any]) -> None:
        """Başarısız veya iptal edilmiş etkileşimde Türkçe hata fırlatır."""
        if etkilesim.get("status") in BASARISIZ_DURUMLAR:
            hatalar = etkilesim.get("errors") or [{}]
            mesaj = str(hatalar[0].get("message", "")) if isinstance(hatalar[0], dict) else ""
            raise YapayZekaHatasi(f"Gemini isteği tamamlayamadı. {mesaj}"[:AYRINTI_SINIRI], HTTPStatus.BAD_GATEWAY)

    def _yanittan_olaylar(self, yanit: dict[str, Any]) -> Iterator[SohbetOlayi]:
        """Akışsız yanıtın adımlarını olaylara çevirir; adımlar geçmişe OLDUĞU GİBİ eklenir."""
        self._durumu_denetle(yanit)
        adimlar = [a for a in (yanit.get("steps") or []) if isinstance(a, dict)]
        for adim in adimlar:
            if adim.get("type") == MODEL_CIKTISI:
                for blok in adim.get("content") or []:
                    if isinstance(blok, dict) and blok.get("type") == METIN_BLOGU and blok.get("text"):
                        yield SohbetOlayi(OLAY_METIN, metin=blok["text"])
            elif adim.get("type") == ARAC_CAGRISI:
                yield SohbetOlayi(OLAY_ARAC_CAGRISI, cagri=self._cagri(adim))
        yield SohbetOlayi(OLAY_BITTI, adimlar=adimlar, durum=str(yanit.get("status", "")), kullanim=yanit.get("usage"))

    def _akisi_coz(self, olaylar: Iterable[dict[str, Any]]) -> Iterator[SohbetOlayi]:
        """
        SSE olaylarından metin parçalarını ve araç çağrılarını üretir; adımları yeniden kurar.

        Her adım "step.start → step.delta… → step.stop" ile gelir. Geçmişe eklenecek adım:
        düşünce (imzasıyla), araç çağrısı (birleştirilmiş argümanlarla) ve model metni.
        """
        adimlar: dict[int, dict[str, Any]] = {}
        parcalar: dict[int, list[str]] = {}
        durum = ""
        kullanim: dict[str, Any] | None = None
        for olay in olaylar:
            tur = olay.get("event_type")
            sira = olay.get("index")
            if tur == "step.start" and isinstance(sira, int):
                adimlar[sira] = dict(olay.get("step") or {})
                parcalar[sira] = []
            elif tur == "step.delta" and isinstance(sira, int):
                fark = olay.get("delta") or {}
                fark_turu = fark.get("type")
                if fark_turu == METIN_BLOGU and fark.get("text"):
                    parcalar.setdefault(sira, []).append(fark["text"])
                    yield SohbetOlayi(OLAY_METIN, metin=fark["text"])
                elif fark_turu == "thought_signature":
                    adimlar.setdefault(sira, {"type": DUSUNCE})["signature"] = fark.get("signature")
                elif fark_turu == "arguments_delta":
                    parcalar.setdefault(sira, []).append(str(fark.get("arguments", "")))
                # Diğer fark türleri (ör. düşünce özeti) kullanılmaz; belge de atlanmasını önerir.
            elif tur == "step.stop" and sira in adimlar:
                cagri = self._adimi_tamamla(adimlar[sira], "".join(parcalar.get(sira, [])))
                if cagri is not None:
                    yield SohbetOlayi(OLAY_ARAC_CAGRISI, cagri=cagri)
            elif tur == "interaction.completed":
                etkilesim = olay.get("interaction") or {}
                self._durumu_denetle(etkilesim)
                durum = str(etkilesim.get("status", durum))
                kullanim = etkilesim.get("usage")
            elif tur == "interaction.status_update":
                durum = str(olay.get("status", durum))
            elif tur == "error":
                raise akis_hatasi(olay.get("error") or {})
        yield SohbetOlayi(OLAY_BITTI, adimlar=[adimlar[i] for i in sorted(adimlar)], durum=durum, kullanim=kullanim)

    def _adimi_tamamla(self, adim: dict[str, Any], birikmis: str) -> AracCagrisi | None:
        """
        Akışta biten adımı geçmişe uygun biçime getirir.

        Dönüş:
            Adım araç çağrısıysa AracCagrisi, değilse None.
        """
        if adim.get("type") == MODEL_CIKTISI:
            adim["content"] = [{"type": METIN_BLOGU, "text": birikmis}]
        elif adim.get("type") == ARAC_CAGRISI:
            if birikmis:
                try:
                    adim["arguments"] = json.loads(birikmis)
                except ValueError:
                    raise YapayZekaHatasi("Gemini araç çağrısını bozuk gönderdi. Tekrar deneyin.", HTTPStatus.BAD_GATEWAY) from None
            return self._cagri(adim)
        return None

    @staticmethod
    def _cagri(adim: dict[str, Any]) -> AracCagrisi:
        """Araç çağrısı adımını AracCagrisi'na çevirir."""
        argumanlar = adim.get("arguments")
        return AracCagrisi(
            kimlik=str(adim.get("id", "")), ad=str(adim.get("name", "")),
            argumanlar=argumanlar if isinstance(argumanlar, dict) else {},
        )

    # ---------- Şemalı JSON ----------

    @staticmethod
    def _metin(adimlar: list[dict[str, Any]]) -> str:
        """Yanıt adımlarındaki model metnini birleştirir."""
        return "\n".join(
            blok.get("text", "")
            for adim in adimlar
            if adim.get("type") == "model_output"
            for blok in adim.get("content") or []
            if blok.get("type") == "text"
        ).strip()

    def json_uret(self, sistem_talimati: str, istem: str, sema: dict[str, Any]) -> dict[str, Any]:
        """Bkz. ArastirmaSaglayicisi.json_uret. Araç (arama) kullanılmaz."""
        govde = {
            "model": self.model,
            "input": [{"type": "user_input", "content": [{"type": "text", "text": istem}]}],
            "system_instruction": sistem_talimati,
            "response_format": {"type": "text", "mime_type": "application/json", "schema": sema},
            "store": False,
        }
        yanit = self._gonder(govde)
        self._durumu_denetle(yanit)
        metin = self._metin(yanit.get("steps") or [])
        if not metin:
            raise YapayZekaHatasi("Gemini boş yanıt döndürdü (istek reddedilmiş olabilir). Tekrar deneyin.", HTTPStatus.BAD_GATEWAY)
        try:
            veri = json.loads(metin)
        except ValueError:
            raise YapayZekaHatasi("Gemini geçerli JSON döndürmedi. Tekrar deneyin.", HTTPStatus.BAD_GATEWAY) from None
        if not isinstance(veri, dict):
            raise YapayZekaHatasi("Gemini beklenmeyen biçimde yanıt verdi. Tekrar deneyin.", HTTPStatus.BAD_GATEWAY)
        return veri
