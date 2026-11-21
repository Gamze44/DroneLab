"""
Google Gemini Interactions API istemcisi (REST, yalnızca standart kütüphane).

D:\\uzay-koc\\sohbet\\gemini.py örnek alınarak yazıldı; iki proje birbirine bağlı
değildir. Google Arama aracı KULLANILMAZ: arama Gemini 3 ve sonrası modellerde
ücretsiz kotada yoktur ve kullanıcı ücretli kullanım istemedi. Bu yüzden model
yalnızca kendi bilgisinden yanıt verir; yanıtlar "doğrulanmadı" sayılır.

Güvenlik: anahtar yalnızca istek başlığında gönderilir; hiçbir hata mesajına,
loga veya yanıta yazılmaz. İstekler store=false ile gönderilir.
"""

from collections.abc import Callable
from http import HTTPStatus
import json
import ssl
from typing import Any, Final
import urllib.error
import urllib.request

from arastirma.saglayici import ArastirmaSaglayicisi
from cekirdek.ag import ssl_baglami
from cekirdek.hatalar import YapayZekaHatasi

URL: Final[str] = "https://generativelanguage.googleapis.com/v1beta/interactions"
API_REVIZYONU: Final[str] = "2026-05-20"

# DEĞİŞTİRİLEBİLİR: Ayarlarda seçilebilecek modeller. Google'ın fiyat sayfasında (15.11.2026)
# ilk model için girdi/çıktı "Free of charge" (ücretsiz kota) yazıyor; diğerlerinin ücretsiz
# kotası ayrıca kontrol edilmedi.
MODELLER: Final[tuple[str, ...]] = ("gemini-3.6-flash", "gemini-3.8-flash", "gemini-3.5-flash-lite")
VARSAYILAN_MODEL: Final[str] = MODELLER[0]

# DEĞİŞTİRİLEBİLİR: Yanıt için en çok bekleme süresi, saniye.
ZAMAN_ASIMI_SN: Final[float] = 90.0

AYRINTI_SINIRI: Final[int] = 200


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
        )
    if kod >= HTTPStatus.INTERNAL_SERVER_ERROR:
        return YapayZekaHatasi("Gemini şu an yanıt veremiyor. Biraz sonra tekrar deneyin.", HTTPStatus.BAD_GATEWAY)
    return YapayZekaHatasi(f"Gemini isteği reddetti: {ayrinti[:AYRINTI_SINIRI] or kod}", HTTPStatus.BAD_REQUEST)


class GeminiSaglayicisi(ArastirmaSaglayicisi):
    """
    Gemini Interactions API ile şemalı JSON yanıtı alır.

    Parametreler:
        anahtar: Gemini API anahtarı.
        model: MODELLER içinden model adı.
        gonder: İsteği gönderen fonksiyon; testlerde sahtesi verilir (gerçek istek yapılmaz).
        zaman_asimi: Saniye.
    """

    def __init__(
        self,
        anahtar: str,
        model: str = VARSAYILAN_MODEL,
        gonder: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        zaman_asimi: float = ZAMAN_ASIMI_SN,
    ) -> None:
        if model not in MODELLER:
            raise YapayZekaHatasi(f"Bilinmeyen Gemini modeli: {model}", HTTPStatus.BAD_REQUEST)
        self._anahtar = anahtar
        self.model = model
        self._zaman_asimi = zaman_asimi
        self._ssl: ssl.SSLContext | None = None
        self._gonder = gonder or self._http

    def __repr__(self) -> str:
        # Nesne bir hata kaydına yazılırsa anahtar görünmesin.
        return f"GeminiSaglayicisi(model={self.model!r})"

    def _http(self, govde: dict[str, Any]) -> dict[str, Any]:
        """İsteği gönderir ve JSON yanıtını döndürür."""
        istek = urllib.request.Request(
            URL,
            data=json.dumps(govde).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json", "x-goog-api-key": self._anahtar, "Api-Revision": API_REVIZYONU},
        )
        self._ssl = self._ssl or ssl_baglami()
        try:
            with urllib.request.urlopen(istek, timeout=self._zaman_asimi, context=self._ssl) as yanit:
                return json.loads(yanit.read().decode("utf-8"))
        except urllib.error.HTTPError as hata:
            try:
                ayrinti = hata_ayrintisi(hata.read().decode("utf-8"))
            except OSError:
                ayrinti = ""
            raise hata_cevir(hata.code, ayrinti) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise YapayZekaHatasi("Gemini'ye ulaşılamadı. İnternet bağlantınızı kontrol edin.", HTTPStatus.SERVICE_UNAVAILABLE) from None
        except ValueError:
            raise YapayZekaHatasi("Gemini'den anlaşılamayan bir yanıt geldi. Tekrar deneyin.", HTTPStatus.BAD_GATEWAY) from None

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
        if yanit.get("status") in ("failed", "cancelled"):
            hatalar = yanit.get("errors") or [{}]
            mesaj = str(hatalar[0].get("message", "")) if isinstance(hatalar[0], dict) else ""
            raise YapayZekaHatasi(f"Gemini isteği tamamlayamadı. {mesaj}"[:AYRINTI_SINIRI], HTTPStatus.BAD_GATEWAY)
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
