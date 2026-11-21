"""
Yerel sunucunun güvenlik katmanları (ASGI ara katmanları).

Sunucu yalnızca 127.0.0.1'de çalışsa da, bilgisayardaki tarayıcıda açık olan BAŞKA bir
web sitesi bu adrese istek gönderebilir. Bu modüldeki katmanlar bu tür saldırıları keser:

- HostDenetimi: DNS rebinding saldırısında kötü site kendi alan adını 127.0.0.1'e
  yönlendirir; tarayıcı isteği "aynı site" sanır. Host başlığı yalnızca izinli adlar
  (127.0.0.1, localhost) olduğunda kabul edilir.
- KaynakDenetimi (CSRF): Başka bir sitenin, kullanıcı fark etmeden drone silmesi veya
  dosya yüklemesi gibi yazma istekleri reddedilir.
- IstekBoyutuSiniri: Çok büyük istekler gövde diske yazılmadan önce 413 ile reddedilir.
- GuvenlikBasliklari: Tarayıcıya sayfanın başka sitelere gömülmemesini ve yalnızca
  kendi betiklerini çalıştırmasını söyleyen başlıklar eklenir.

Katmanlar Starlette'in BaseHTTPMiddleware'i yerine saf ASGI olarak yazıldı: gövdeyi
okumadan karar verebilmek ve her istekte ek yük getirmemek için.
"""

from collections.abc import Awaitable, Callable, MutableMapping
from http import HTTPStatus
import json
from typing import Any, Final
from urllib.parse import urlsplit

from cekirdek.birimler import BAYT_BIR_MB

Kapsam = MutableMapping[str, Any]
Mesaj = MutableMapping[str, Any]
Alici = Callable[[], Awaitable[Mesaj]]
Gonderici = Callable[[Mesaj], Awaitable[None]]
AsgiUygulamasi = Callable[[Kapsam, Alici, Gonderici], Awaitable[None]]

# Veri değiştiren yöntemler; GET/HEAD/OPTIONS hiçbir şeyi değiştirmediği için denetlenmez.
YAZMA_YONTEMLERI: Final[frozenset[str]] = frozenset({"POST", "PUT", "PATCH", "DELETE"})
# Tarayıcının Sec-Fetch-Site başlığında güvenli sayılan değerler: aynı köken ve kullanıcının
# kendisinin başlattığı istek. "same-site" kabul edilmez: 127.0.0.1'in başka bir portundaki
# program da tarayıcıya göre "aynı site"dir.
GUVENLI_KAYNAK_DEGERLERI: Final[frozenset[str]] = frozenset({"same-origin", "none"})

# multipart gövdesinde dosyanın yanında alan adları ve sınır satırları da bulunur.
# DEĞİŞTİRİLEBİLİR: Dosya boyut sınırının üzerine eklenen pay (bayt).
COK_PARCALI_EK_PAY_BAYT: Final[int] = BAYT_BIR_MB
COK_PARCALI_ICERIK_TURU: Final[str] = "multipart/form-data"

# DEĞİŞTİRİLEBİLİR: Sayfaların yükleyebileceği kaynaklar. Arayüz yalnızca kendi
# dosyalarını kullanır (CDN yok); satır içi stil, JS'in çizdiği SVG'ler için gereklidir.
ICERIK_GUVENLIK_POLITIKASI: Final[str] = (
    "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
    "frame-ancestors 'none'; base-uri 'none'; form-action 'self'; object-src 'none'"
)
GUVENLIK_BASLIKLARI: Final[tuple[tuple[bytes, bytes], ...]] = (
    (b"content-security-policy", ICERIK_GUVENLIK_POLITIKASI.encode()),
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"cross-origin-opener-policy", b"same-origin"),
    (b"cross-origin-resource-policy", b"same-origin"),
)

HOST_RED_MESAJI: Final[str] = (
    "İstek tanınmayan bir adresten geldi ve reddedildi. Programı http://127.0.0.1 adresinden açın."
)
KAYNAK_RED_MESAJI: Final[str] = (
    "Bu istek başka bir web sitesinden geldiği için güvenlik nedeniyle reddedildi. "
    "İşlemi programın kendi penceresinden yapın."
)
BOYUT_RED_MESAJI: Final[str] = "Gönderilen dosya veya veri {mb} MB sınırını aşıyor. Daha küçük bir dosya deneyin."


def _baslik(kapsam: Kapsam, ad: bytes) -> str | None:
    """İstek başlığının değerini döndürür (ASGI başlıkları küçük harfli bayt çiftleridir)."""
    for anahtar, deger in kapsam.get("headers", ()):
        if anahtar == ad:
            return deger.decode("latin-1")
    return None


async def _hata_gonder(gonder: Gonderici, kod: HTTPStatus, mesaj: str) -> None:
    """Programın diğer hatalarıyla aynı biçimde ({"hata": ...}) JSON hata yanıtı gönderir."""
    govde = json.dumps({"hata": mesaj}, ensure_ascii=False).encode("utf-8")
    await gonder({
        "type": "http.response.start",
        "status": int(kod),
        "headers": [(b"content-type", b"application/json; charset=utf-8"), (b"content-length", str(len(govde)).encode())],
    })
    await gonder({"type": "http.response.body", "body": govde})


class HostDenetimi:
    """
    Host başlığı izinli adlardan biri değilse isteği reddeder (DNS rebinding'e karşı).

    Parametreler:
        uygulama: Sarılan ASGI uygulaması.
        izinli_hostlar: Kabul edilen ana makine adları (port olmadan).
    """

    def __init__(self, uygulama: AsgiUygulamasi, izinli_hostlar: tuple[str, ...]) -> None:
        self._uygulama = uygulama
        self._izinli = frozenset(h.lower() for h in izinli_hostlar)

    def izinli_mi(self, host: str | None) -> bool:
        """
        Parametreler:
            host: Host başlığı (ör. "127.0.0.1:8000").
        Dönüş:
            Port atıldıktan sonra ad izinliyse True.
        """
        if not host:
            return False
        return host.rsplit(":", 1)[0].lower() in self._izinli

    async def __call__(self, kapsam: Kapsam, al: Alici, gonder: Gonderici) -> None:
        if kapsam["type"] in ("http", "websocket") and not self.izinli_mi(_baslik(kapsam, b"host")):
            if kapsam["type"] == "http":
                await _hata_gonder(gonder, HTTPStatus.BAD_REQUEST, HOST_RED_MESAJI)
            return
        await self._uygulama(kapsam, al, gonder)


class KaynakDenetimi:
    """
    Başka bir web sitesinden gelen yazma isteklerini reddeder (CSRF'e karşı).

    Karar sırası:
      1. Tarayıcı Sec-Fetch-Site gönderdiyse yalnızca "same-origin" ve "none" kabul edilir.
      2. Yoksa Origin başlığı varsa, köken sunucunun kendi adresi olmalıdır.
      3. İkisi de yoksa istek tarayıcıdan gelmiyordur (ör. komut satırı aracı); kabul edilir.
         Tarayıcılar başka siteden yapılan POST/PUT/DELETE isteklerinde Origin'i hep gönderir.

    Parametreler:
        uygulama: Sarılan ASGI uygulaması.
    """

    def __init__(self, uygulama: AsgiUygulamasi) -> None:
        self._uygulama = uygulama

    @staticmethod
    def kabul_edilir_mi(yontem: str, getirme_sitesi: str | None, koken: str | None, host: str | None) -> bool:
        """
        Parametreler:
            yontem: HTTP yöntemi.
            getirme_sitesi: Sec-Fetch-Site başlığı.
            koken: Origin başlığı.
            host: Host başlığı.
        Dönüş:
            İstek işlenebilirse True.
        """
        if yontem.upper() not in YAZMA_YONTEMLERI:
            return True
        if getirme_sitesi is not None:
            return getirme_sitesi.strip().lower() in GUVENLI_KAYNAK_DEGERLERI
        if koken is not None:
            # "null" kökeni (dosyadan açılmış sayfa, sandbox iframe) netloc vermez; reddedilir.
            parcalar = urlsplit(koken.strip())
            return bool(host) and parcalar.scheme == "http" and parcalar.netloc.lower() == host.strip().lower()
        return True

    async def __call__(self, kapsam: Kapsam, al: Alici, gonder: Gonderici) -> None:
        if kapsam["type"] == "http" and not self.kabul_edilir_mi(
            kapsam["method"], _baslik(kapsam, b"sec-fetch-site"), _baslik(kapsam, b"origin"), _baslik(kapsam, b"host")
        ):
            await _hata_gonder(gonder, HTTPStatus.FORBIDDEN, KAYNAK_RED_MESAJI)
            return
        await self._uygulama(kapsam, al, gonder)


class IstekBoyutuSinirlari:
    """
    Bir isteğin gövdesinin en çok kaç bayt olabileceğini belirler.

    Dosya yüklemelerinde (multipart) sınır, o adrese özel dosya sınırından gelir; diğer
    isteklerde (JSON) küçük bir genel sınır kullanılır.

    Parametreler:
        dosya_sinirlari_mb: Adres -> dosya sınırı (MB); listede olmayan yüklemeler için varsayılan kullanılır.
        varsayilan_dosya_mb: Varsayılan dosya sınırı (MB).
        diger_mb: Dosya olmayan istekler için sınır (MB).
    """

    def __init__(self, dosya_sinirlari_mb: dict[str, int], varsayilan_dosya_mb: int, diger_mb: int) -> None:
        self._dosya_sinirlari_mb = dosya_sinirlari_mb
        self._varsayilan_dosya_mb = varsayilan_dosya_mb
        self._diger_mb = diger_mb

    def sinir_mb(self, yol: str, icerik_turu: str | None) -> int:
        """Kullanıcıya gösterilecek sınır (MB)."""
        if icerik_turu and icerik_turu.lower().startswith(COK_PARCALI_ICERIK_TURU):
            return self._dosya_sinirlari_mb.get(yol.rstrip("/"), self._varsayilan_dosya_mb)
        return self._diger_mb

    def sinir_bayt(self, yol: str, icerik_turu: str | None) -> int:
        """Gövdenin en çok bayt sayısı (multipart için çerçeve payı dahil)."""
        sinir = self.sinir_mb(yol, icerik_turu) * BAYT_BIR_MB
        if icerik_turu and icerik_turu.lower().startswith(COK_PARCALI_ICERIK_TURU):
            sinir += COK_PARCALI_EK_PAY_BAYT
        return sinir


class _GovdeSiniriAsildi(Exception):
    """Gövde, Content-Length bildirilmeden gönderilip sınırı aştığında içeride fırlatılır."""


class IstekBoyutuSiniri:
    """
    Sınırı aşan istekleri 413 ile reddeder.

    Content-Length başlığı varsa karar gövde hiç okunmadan verilir (200 MB'lık bir dosya
    önce diske yazılıp sonra reddedilmez). Başlık yoksa (parça parça gönderim) gelen bayt
    sayılır ve sınır aşılınca okuma kesilir.

    Parametreler:
        uygulama: Sarılan ASGI uygulaması.
        sinirlar: Adrese ve içerik türüne göre sınırı veren IstekBoyutuSinirlari.
    """

    def __init__(self, uygulama: AsgiUygulamasi, sinirlar: IstekBoyutuSinirlari) -> None:
        self._uygulama = uygulama
        self._sinirlar = sinirlar

    async def __call__(self, kapsam: Kapsam, al: Alici, gonder: Gonderici) -> None:
        if kapsam["type"] != "http":
            await self._uygulama(kapsam, al, gonder)
            return
        icerik_turu = _baslik(kapsam, b"content-type")
        sinir = self._sinirlar.sinir_bayt(kapsam["path"], icerik_turu)
        mesaj = BOYUT_RED_MESAJI.format(mb=self._sinirlar.sinir_mb(kapsam["path"], icerik_turu))

        bildirilen = _baslik(kapsam, b"content-length")
        if bildirilen is not None:
            if not bildirilen.strip().isdigit():
                await _hata_gonder(gonder, HTTPStatus.BAD_REQUEST, "İstek başlığı (Content-Length) geçersiz.")
                return
            if int(bildirilen) > sinir:
                await _hata_gonder(gonder, HTTPStatus.REQUEST_ENTITY_TOO_LARGE, mesaj)
                return

        alinan = 0
        asildi = False
        yanit_basladi = False

        async def sayarak_al() -> Mesaj:
            nonlocal alinan, asildi
            ileti = await al()
            if ileti["type"] == "http.request":
                alinan += len(ileti.get("body", b""))
                if alinan > sinir:
                    asildi = True
                    raise _GovdeSiniriAsildi()
            return ileti

        async def izleyerek_gonder(ileti: Mesaj) -> None:
            nonlocal yanit_basladi
            if asildi:
                # FastAPI gövde okuma hatasını kendi 400 yanıtına çevirir; kullanıcı doğru
                # nedeni görsün diye onun yerine 413 gönderilir.
                if ileti["type"] == "http.response.start" and not yanit_basladi:
                    yanit_basladi = True
                    await _hata_gonder(gonder, HTTPStatus.REQUEST_ENTITY_TOO_LARGE, mesaj)
                return
            if ileti["type"] == "http.response.start":
                yanit_basladi = True
            await gonder(ileti)

        try:
            await self._uygulama(kapsam, sayarak_al, izleyerek_gonder)
        except _GovdeSiniriAsildi:
            if not yanit_basladi:
                await _hata_gonder(gonder, HTTPStatus.REQUEST_ENTITY_TOO_LARGE, mesaj)


class GuvenlikBasliklari:
    """
    Her HTTP yanıtına güvenlik başlıklarını ekler (CSP, X-Frame-Options, nosniff...).

    Parametreler:
        uygulama: Sarılan ASGI uygulaması.
        basliklar: Eklenecek (ad, değer) bayt çiftleri.
    """

    def __init__(
        self, uygulama: AsgiUygulamasi, basliklar: tuple[tuple[bytes, bytes], ...] = GUVENLIK_BASLIKLARI
    ) -> None:
        self._uygulama = uygulama
        self._basliklar = basliklar

    async def __call__(self, kapsam: Kapsam, al: Alici, gonder: Gonderici) -> None:
        if kapsam["type"] != "http":
            await self._uygulama(kapsam, al, gonder)
            return

        async def baslik_ekleyerek_gonder(ileti: Mesaj) -> None:
            if ileti["type"] == "http.response.start":
                mevcut = {ad.lower() for ad, _ in ileti.get("headers", ())}
                ileti["headers"] = [*ileti.get("headers", ()), *(b for b in self._basliklar if b[0] not in mevcut)]
            await gonder(ileti)

        await self._uygulama(kapsam, al, baslik_ekleyerek_gonder)
