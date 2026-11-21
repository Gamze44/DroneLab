"""
Programın giriş noktası.

Çalıştırma: python uygulama.py
Yerel sunucuyu başlatır ve arayüzü varsayılan tarayıcıda açar.
"""

import threading
import webbrowser

import uvicorn

from arayuz.sunucu import sunucu_olustur
from cekirdek.ayarlar import (
    PROGRAM_ADI,
    SUNUCU_ADRESI,
    SUNUCU_PORTU,
    TARAYICI_ACMA_GECIKMESI_SN,
    TARAYICIYI_OTOMATIK_AC,
)


def ana() -> None:
    """
    Sunucuyu başlatır; ayar açıksa kısa bir gecikmeyle tarayıcıyı açar.

    Sunucu çalıştığı sürece bu fonksiyon geri dönmez; kapatmak için Ctrl+C.
    """
    adres = f"http://{SUNUCU_ADRESI}:{SUNUCU_PORTU}"
    print(f"{PROGRAM_ADI} başlatılıyor: {adres}")
    print("Kapatmak için Ctrl+C tuşlarına basın.")

    if TARAYICIYI_OTOMATIK_AC:
        # uvicorn.run çalışmayı bloklar; tarayıcı ayrı bir zamanlayıcıyla açılır.
        threading.Timer(TARAYICI_ACMA_GECIKMESI_SN, webbrowser.open, args=[adres]).start()

    uvicorn.run(sunucu_olustur(), host=SUNUCU_ADRESI, port=SUNUCU_PORTU)


if __name__ == "__main__":
    ana()
