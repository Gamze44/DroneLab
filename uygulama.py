"""
Programın giriş noktası.

Çalıştırma: python uygulama.py
Yerel sunucuyu başlatır ve arayüzü varsayılan tarayıcıda açar.
"""

import threading
import time
from typing import Final
import webbrowser

import uvicorn

from arayuz.sunucu import sunucu_olustur
from cekirdek.ayarlar import (
    PROGRAM_ADI,
    SUNUCU_ADRESI,
    SUNUCU_HAZIR_BEKLEME_SN,
    SUNUCU_PORTU,
    TARAYICIYI_OTOMATIK_AC,
)

BEKLEME_ADIMI_SN: Final[float] = 0.1


def hazir_olunca_tarayiciyi_ac(sunucu: uvicorn.Server, adres: str, bekleme_sn: float = SUNUCU_HAZIR_BEKLEME_SN) -> bool:
    """
    Sunucu istek kabul etmeye başlayınca tarayıcıyı açar.

    Neden sabit gecikme değil: Port başka bir program tarafından kullanılıyorsa sunucu
    hiç başlamaz; o zaman tarayıcı açılmamalıdır. Aksi halde tarayıcı o başka programın
    sayfasını DroneLab sanarak açar ve kullanıcı oraya bilgi (ör. API anahtarı) girebilir.

    Parametreler:
        sunucu: Çalışan uvicorn sunucusu.
        adres: Açılacak adres.
        bekleme_sn: En çok bekleme süresi, saniye.
    Dönüş:
        Tarayıcı açıldıysa True.
    """
    son = time.monotonic() + bekleme_sn
    while time.monotonic() < son:
        if sunucu.started:
            webbrowser.open(adres)
            return True
        if sunucu.should_exit:
            return False
        time.sleep(BEKLEME_ADIMI_SN)
    return False


def ana() -> None:
    """
    Sunucuyu başlatır; ayar açıksa sunucu hazır olunca tarayıcıyı açar.

    Sunucu çalıştığı sürece bu fonksiyon geri dönmez; kapatmak için Ctrl+C.
    """
    adres = f"http://{SUNUCU_ADRESI}:{SUNUCU_PORTU}"
    print(f"{PROGRAM_ADI} başlatılıyor: {adres}")
    print("Kapatmak için Ctrl+C tuşlarına basın.")

    sunucu = uvicorn.Server(uvicorn.Config(sunucu_olustur(), host=SUNUCU_ADRESI, port=SUNUCU_PORTU))
    if TARAYICIYI_OTOMATIK_AC:
        # sunucu.run çalışmayı bloklar; tarayıcı ayrı iş parçacığında, sunucu hazır olunca açılır.
        threading.Thread(target=hazir_olunca_tarayiciyi_ac, args=(sunucu, adres), daemon=True).start()
    sunucu.run()


if __name__ == "__main__":
    ana()
