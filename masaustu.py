"""
Programın masaüstü giriş noktası: program kendi penceresinde açılır.

Çalıştırma (konsol penceresi olmadan):  .venv\\Scripts\\pythonw.exe masaustu.py
Masaüstü kısayolu bunu yapar (bkz. araclar/kisayol_olustur.py).

Akış: yerel sunucu boş bir portta arka planda başlar -> hazır olunca pencere açılır ->
pencere kapanınca sunucu da kapanır. Tarayıcıyla çalışmak isteyen için uygulama.py
olduğu gibi duruyor.

Konsol olmadığı için hatalar veri/<program adı>.log dosyasına yazılır ve kullanıcıya
Türkçe bir uyarı kutusu gösterilir.
"""

import ctypes
import logging
from logging.handlers import RotatingFileHandler
import socket
import sys
import threading
import time
from typing import Final

import uvicorn

from arayuz.sunucu import sunucu_olustur
from cekirdek.ayarlar import (
    BASLIK_CUBUGU_RENGI,
    BASLIK_YAZI_RENGI,
    GUNLUK_DOSYA_ADI,
    PENCERE_KENAR_RENGI,
    PENCERE_EN_KUCUK,
    PENCERE_GENISLIGI,
    PENCERE_YUKSEKLIGI,
    PENCERE_ZEMIN_RENGI,
    PROGRAM_ADI,
    PROGRAM_DOSYA_ADI,
    SIMGE_YOLU,
    SUNUCU_ADRESI,
    SUNUCU_HAZIR_BEKLEME_SN,
    VERI_KLASORU,
)

# Windows'ta aynı anda tek kopya çalışsın diye kullanılan adlandırılmış kilit.
TEK_KOPYA_KILIDI: Final[str] = f"{PROGRAM_DOSYA_ADI}_TekKopya"
# Görev çubuğunda programın Python'dan ayrı bir uygulama olarak görünmesi için kimlik.
UYGULAMA_KIMLIGI: Final[str] = f"{PROGRAM_DOSYA_ADI}.Masaustu"
WINDOWS_ZATEN_VAR: Final[int] = 183  # ERROR_ALREADY_EXISTS
MESAJ_KUTUSU_UYARI: Final[int] = 0x30  # MB_ICONWARNING
# Windows 11 pencere yöneticisi (DWM) öznitelik numaraları.
DWM_KENAR_RENGI: Final[int] = 34  # DWMWA_BORDER_COLOR
DWM_BASLIK_RENGI: Final[int] = 35  # DWMWA_CAPTION_COLOR
DWM_BASLIK_YAZI_RENGI: Final[int] = 36  # DWMWA_TEXT_COLOR
GUNLUK_EN_BUYUK_BAYT: Final[int] = 1_000_000
GUNLUK_YEDEK_SAYISI: Final[int] = 2
BEKLEME_ADIMI_SN: Final[float] = 0.05

gunluk = logging.getLogger(PROGRAM_DOSYA_ADI)


def uyari_kutusu(mesaj: str) -> None:
    """Konsol olmadığı için hatayı Windows uyarı kutusuyla gösterir."""
    try:
        ctypes.windll.user32.MessageBoxW(None, mesaj, PROGRAM_ADI, MESAJ_KUTUSU_UYARI)
    except (AttributeError, OSError):
        pass  # Windows dışında uyarı kutusu yok; hata yine günlüğe yazılır


def gunlugu_kur() -> None:
    """Konsolsuz (pythonw) çalışmada çıktılar kaybolmasın diye günlüğü dosyaya yönlendirir."""
    VERI_KLASORU.mkdir(parents=True, exist_ok=True)
    isleyici = RotatingFileHandler(
        VERI_KLASORU / GUNLUK_DOSYA_ADI, maxBytes=GUNLUK_EN_BUYUK_BAYT, backupCount=GUNLUK_YEDEK_SAYISI, encoding="utf-8"
    )
    isleyici.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    kok = logging.getLogger()
    kok.handlers[:] = [isleyici]
    kok.setLevel(logging.INFO)
    # Her sayfa isteğinin satırı günlüğü şişirir; yalnızca uyarı ve hatalar yazılsın.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def bos_port_bul() -> int:
    """
    İşletim sisteminden kullanılmayan bir port ister.

    Sabit port (8000) yerine boş port kullanılır; böylece tarayıcı sürümü açıkken de
    masaüstü penceresi çakışmadan açılır.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((SUNUCU_ADRESI, 0))
        return s.getsockname()[1]


class TekKopyaKilidi:
    """Programın aynı anda iki kez açılmasını önleyen Windows adlandırılmış kilidi (mutex)."""

    def __init__(self, ad: str = TEK_KOPYA_KILIDI) -> None:
        self._ad = ad
        self._tutamac = None

    def al(self) -> bool:
        """Kilidi alır. Dönüş: başka bir kopya zaten çalışıyorsa False."""
        try:
            kernel32 = ctypes.windll.kernel32
        except AttributeError:
            return True  # Windows dışında kilit yok
        self._tutamac = kernel32.CreateMutexW(None, False, self._ad)
        return kernel32.GetLastError() != WINDOWS_ZATEN_VAR


class YerelSunucu:
    """
    FastAPI sunucusunu arka plan iş parçacığında çalıştırır ve durdurur.

    Parametreler:
        port: Dinlenecek port.
        uygulama: FastAPI uygulaması; verilmezse gerçek veri klasörüyle oluşturulur
            (testlerde geçici klasörlü uygulama verilir).
    """

    def __init__(self, port: int, uygulama: object | None = None) -> None:
        self.adres = f"http://{SUNUCU_ADRESI}:{port}"
        # log_config=None: uvicorn kendi konsol günlüğünü kurmaz (pythonw'da konsol yok).
        ayar = uvicorn.Config(uygulama or sunucu_olustur(), host=SUNUCU_ADRESI, port=port, log_config=None)
        self._sunucu = uvicorn.Server(ayar)
        self._is_parcacigi = threading.Thread(target=self._sunucu.run, name="yerel-sunucu", daemon=True)

    def baslat(self, bekleme_sn: float = SUNUCU_HAZIR_BEKLEME_SN) -> None:
        """
        Sunucuyu başlatır ve istek kabul etmeye hazır olana kadar bekler.

        Hatalar:
            RuntimeError: Süre içinde hazır olmazsa.
        """
        self._is_parcacigi.start()
        son = time.monotonic() + bekleme_sn
        while not self._sunucu.started:
            if not self._is_parcacigi.is_alive() or time.monotonic() > son:
                raise RuntimeError("Yerel sunucu başlatılamadı.")
            time.sleep(BEKLEME_ADIMI_SN)

    def durdur(self) -> None:
        """Sunucuya kapanmasını söyler ve bitmesini kısa süre bekler."""
        self._sunucu.should_exit = True
        self._is_parcacigi.join(timeout=5)


def renk_kodu(onaltilik: str) -> int:
    """
    "#rrggbb" rengini Windows'un beklediği COLORREF sayısına (0x00bbggrr) çevirir.

    Parametreler:
        onaltilik: ör. "#0b111c".
    """
    r, g, b = (int(onaltilik.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    return (b << 16) | (g << 8) | r


def baslik_cubugunu_boya(pencere_tutamaci: int) -> None:
    """
    Windows başlık çubuğunu ve kenarlığını programın renklerine boyar.

    Windows 11'in pencere yöneticisi (DWM) özniteliklerini kullanır; böylece küçült /
    büyüt / kapat düğmeleri ve pencereyi kenara yaslama gibi yerel davranışlar korunur.
    Eski Windows sürümlerinde çağrı başarısız olur ve varsayılan çubuk kalır.
    """
    dwm = ctypes.windll.dwmapi
    for oznitelik, renk in (
        (DWM_KENAR_RENGI, PENCERE_KENAR_RENGI),
        (DWM_BASLIK_RENGI, BASLIK_CUBUGU_RENGI),
        (DWM_BASLIK_YAZI_RENGI, BASLIK_YAZI_RENGI),
    ):
        deger = ctypes.c_uint(renk_kodu(renk))
        dwm.DwmSetWindowAttribute(ctypes.c_void_p(pencere_tutamaci), oznitelik, ctypes.byref(deger), ctypes.sizeof(deger))


def pencereyi_bicimle(pencere) -> None:
    """
    Pencereye program simgesini atar ve başlık çubuğunu tasarımın renklerine boyar.

    pywebview Windows'ta bunları parametreyle almaz; yerel WinForms penceresine doğrudan
    uygulanır (pencerenin kendi iş parçacığında). Olmazsa program yine çalışır.
    """
    try:
        from System import Action  # pythonnet (pywebview ile gelir)
        from System.Drawing import Icon

        form = pencere.native

        def uygula() -> None:
            form.Icon = Icon(str(SIMGE_YOLU))
            baslik_cubugunu_boya(form.Handle.ToInt64())

        form.Invoke(Action(uygula))
    except Exception:  # yalnızca görünüş; hiçbir hata programı durdurmamalı
        gunluk.warning("Pencere simgesi veya başlık rengi ayarlanamadı.", exc_info=True)


def ana() -> int:
    """
    Masaüstü uygulamasını çalıştırır.

    Dönüş:
        Çıkış kodu (0 başarılı).
    """
    gunlugu_kur()
    # Kilit program kapanana kadar tutulur (değişkende saklanır ki erken bırakılmasın).
    kilit = TekKopyaKilidi()
    if not kilit.al():
        uyari_kutusu(f"{PROGRAM_ADI} zaten açık. Görev çubuğundaki pencereyi kullanın.")
        return 0
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(UYGULAMA_KIMLIGI)
    except (AttributeError, OSError):
        pass

    try:
        import webview
    except ImportError:
        uyari_kutusu("Pencere kütüphanesi (pywebview) kurulu değil.\n\n"
                     "Kurmak için: .venv\\Scripts\\python.exe -m pip install -r requirements.txt")
        return 1

    sunucu = YerelSunucu(bos_port_bul())
    try:
        sunucu.baslat()
    except Exception:
        gunluk.exception("Sunucu başlatılamadı")
        uyari_kutusu(f"{PROGRAM_ADI} başlatılamadı. Ayrıntılar: veri\\{GUNLUK_DOSYA_ADI}")
        return 1

    try:
        pencere = webview.create_window(
            PROGRAM_ADI, sunucu.adres, width=PENCERE_GENISLIGI, height=PENCERE_YUKSEKLIGI,
            min_size=PENCERE_EN_KUCUK, background_color=PENCERE_ZEMIN_RENGI,
        )
        pencere.events.shown += lambda: pencereyi_bicimle(pencere)
        webview.start()  # pencere kapanana kadar burada bekler
    except Exception:
        gunluk.exception("Pencere açılamadı")
        uyari_kutusu(
            f"{PROGRAM_ADI} penceresi açılamadı (Microsoft Edge WebView2 gerekebilir).\n"
            f"Ayrıntılar: veri\\{GUNLUK_DOSYA_ADI}\n\nGeçici çözüm: uygulama.py ile tarayıcıda açın."
        )
        return 1
    finally:
        sunucu.durdur()
    return 0


if __name__ == "__main__":
    sys.exit(ana())
