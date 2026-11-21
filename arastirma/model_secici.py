"""
Gemini modelleri arasında otomatik geçiş.

Ayarlarda "Otomatik" seçiliyse istek önce sıradaki ilk modele gider. Model kotasını
doldurduysa (429), aşırı yüklüyse (503) veya bulunamazsa (404) aynı istek kendiliğinden
bir sonraki modelle tekrarlanır. Böylece kullanıcı model seçmekle uğraşmaz ve bir modelin
ücretsiz kotası dolduğunda asistan çalışmaya devam eder.

Gereksiz başarısız istek atmamak için:
    - günlük kotası dolan (veya hiç bulunamayan) model o gün bir daha denenmez,
    - dakikalık hız sınırına takılan model kısa bir süre dinlendirilir,
    - internet bağlantısı yoksa model değiştirilmez (hepsi aynı hatayı verir).
Durum bellekte tutulur; program yeniden açılınca sıfırlanır.
"""

from collections.abc import Callable
from http import HTTPStatus
import threading
import time
from typing import Final

from cekirdek.hatalar import YapayZekaHatasi
from cekirdek.zaman import bugun_iso

# Ayarlarda "model" alanının otomatik seçim değeri.
OTOMATIK_MODEL: Final[str] = "otomatik"

# DEĞİŞTİRİLEBİLİR: Otomatik modda modellerin deneme sırası. En yeni ve en yetenekli "flash"
# önce (araç kullanan sohbet için), kota dolunca önceki nesil, en son en hafif model.
OTOMATIK_SIRA: Final[tuple[str, ...]] = ("gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite")

# Bu hatalarda sıradaki model denenir.
YEDEGE_GECILEN_KODLAR: Final[frozenset[int]] = frozenset(
    {HTTPStatus.TOO_MANY_REQUESTS, HTTPStatus.SERVICE_UNAVAILABLE, HTTPStatus.NOT_FOUND}
)
# DEĞİŞTİRİLEBİLİR: Dakikalık hız sınırına takılan model bu kadar saniye denenmez.
KISA_DINLENME_SN: Final[float] = 60.0
# Google'ın 429 mesajında günlük kotayı belirten ifadeler (boşluksuz, küçük harfle aranır).
GUNLUK_KOTA_IPUCLARI: Final[tuple[str, ...]] = ("perday", "per_day", "daily")
HEPSI_DOLU_MESAJI: Final[str] = (
    "Bugün bütün Gemini modellerinin ücretsiz kullanım sınırı doldu. Yarın tekrar deneyin."
)


class ModelSecici:
    """
    Bir istek için denenecek modelleri sıralar ve başarısız modelleri dinlendirir.

    İş parçacığı güvenlidir (sunucu istekleri ayrı iş parçacıklarında çalışır).

    Parametreler:
        sira: Otomatik modda deneme sırası.
        saat: Saniye veren saat (testler için).
        bugun: Bugünün tarihini veren fonksiyon (testler için).
    """

    def __init__(
        self,
        sira: tuple[str, ...] = OTOMATIK_SIRA,
        saat: Callable[[], float] = time.monotonic,
        bugun: Callable[[], str] = bugun_iso,
    ) -> None:
        self._sira = sira
        self._saat = saat
        self._bugun = bugun
        self._gunluk_dinlenen: dict[str, str] = {}
        self._kisa_dinlenen: dict[str, float] = {}
        self._kilit = threading.Lock()

    def adaylar(self, tercih: str) -> list[str]:
        """
        Denenecek modeller, sırasıyla.

        Parametreler:
            tercih: Ayarlardaki model; OTOMATIK_MODEL ise otomatik sıra kullanılır.
        Dönüş:
            Elle seçilmiş modelde yalnızca o model; otomatikte dinlenmede olmayanlar
            (hepsi dinlenmedeyse boş liste).
        """
        if tercih != OTOMATIK_MODEL:
            return [tercih]
        with self._kilit:
            return [m for m in self._sira if not self._dinlenmede_mi(m)]

    def basarisiz(self, model: str, hata: YapayZekaHatasi) -> bool:
        """
        Modelin başarısız olduğunu bildirir.

        Parametreler:
            model: Başarısız olan model.
            hata: Alınan hata.
        Dönüş:
            Sıradaki modelin denenmesi anlamlıysa True.
        """
        if hata.http_kodu not in YEDEGE_GECILEN_KODLAR:
            return False
        with self._kilit:
            if hata.http_kodu == HTTPStatus.NOT_FOUND or self._gunluk_kota_mi(hata):
                self._gunluk_dinlenen[model] = self._bugun()
            elif hata.http_kodu == HTTPStatus.TOO_MANY_REQUESTS:
                self._kisa_dinlenen[model] = self._saat() + KISA_DINLENME_SN
            # 503 (aşırı yük) geçicidir: dinlendirilmez, yalnızca bu istekte sıradakine geçilir.
        return True

    def _dinlenmede_mi(self, model: str) -> bool:
        """Model bugün için ya da kısa süreliğine dinlenmede mi (kilit tutulurken çağrılır)."""
        if self._gunluk_dinlenen.get(model) == self._bugun():
            return True
        return self._kisa_dinlenen.get(model, 0.0) > self._saat()

    @staticmethod
    def _gunluk_kota_mi(hata: YapayZekaHatasi) -> bool:
        """429 hatasının günlük kotadan mı (dakikalık hız sınırından değil) kaynaklandığı."""
        if hata.http_kodu != HTTPStatus.TOO_MANY_REQUESTS:
            return False
        ayrinti = hata.ayrinti.lower().replace(" ", "")
        return any(ipucu.replace(" ", "") in ayrinti for ipucu in GUNLUK_KOTA_IPUCLARI)
