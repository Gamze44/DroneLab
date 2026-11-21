"""
Program simgesini (.ico) üretir: koyu zemin üzerinde camgöbeği quad logosu.

Çalıştırma: .venv\\Scripts\\python.exe -m araclar.simge_olustur
Ek kütüphane gerekmez: çizim numpy ile yapılır, PNG ve ICO biçimi standart kütüphaneyle
(zlib, struct) yazılır. Simge masaüstü kısayolunda, pencerede ve tarayıcı sekmesinde kullanılır.
"""

import struct
import zlib
from typing import Final

import numpy as np

from cekirdek.ayarlar import SIMGE_YOLU

# DEĞİŞTİRİLEBİLİR: Simgedeki boyutlar (Windows küçükten büyüğe hepsini kullanır) ve renkler.
BOYUTLAR: Final[tuple[int, ...]] = (16, 24, 32, 48, 64, 128, 256)
ZEMIN_RENGI: Final[tuple[int, int, int]] = (13, 20, 34)
CERCEVE_RENGI: Final[tuple[int, int, int]] = (36, 52, 78)
LOGO_RENGI: Final[tuple[int, int, int]] = (34, 211, 238)
KENAR_YUMUSATMA: Final[int] = 4  # her piksel 4×4 alt örnekle çizilir (kenarlar tırtıklı olmasın)

# Logo geometrisi, simge kenarına göre oran (0–1).
KOSE_YARICAPI: Final[float] = 0.22
CERCEVE_KALINLIGI: Final[float] = 0.03
ROTOR_MERKEZI: Final[float] = 0.27  # rotorlar (r, r), (1-r, r)… noktalarında
ROTOR_YARICAPI: Final[float] = 0.135
ROTOR_KALINLIGI: Final[float] = 0.05
KOL_KALINLIGI: Final[float] = 0.065
GOVDE_YARI: Final[float] = 0.095


def _parca_uzakligi(x: np.ndarray, y: np.ndarray, a: tuple[float, float], b: tuple[float, float]) -> np.ndarray:
    """Noktaların [a, b] doğru parçasına uzaklığı."""
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    t = np.clip(((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy), 0, 1)
    return np.hypot(x - (ax + t * dx), y - (ay + t * dy))


def simge_ciz(boyut: int) -> np.ndarray:
    """
    Simgeyi çizer.

    Parametreler:
        boyut: Kenar uzunluğu, piksel.
    Dönüş:
        boyut × boyut × 4 RGBA (uint8) dizi.
    """
    n = boyut * KENAR_YUMUSATMA
    eksen = (np.arange(n) + 0.5) / n
    x, y = np.meshgrid(eksen, eksen)

    # Yuvarlatılmış kare zemin ve ince çerçeve.
    k = KOSE_YARICAPI
    qx = np.maximum(np.abs(x - 0.5) - (0.5 - k), 0)
    qy = np.maximum(np.abs(y - 0.5) - (0.5 - k), 0)
    kose = np.hypot(qx, qy)
    zemin = kose <= k
    cerceve = zemin & (kose > k - CERCEVE_KALINLIGI) & ((qx > 0) | (qy > 0) | (np.abs(x - 0.5) > 0.5 - CERCEVE_KALINLIGI) | (np.abs(y - 0.5) > 0.5 - CERCEVE_KALINLIGI))

    # Quad logosu: X kollar, dört rotor halkası, ortada gövde.
    r = ROTOR_MERKEZI
    rotorlar = [(r, r), (1 - r, r), (r, 1 - r), (1 - r, 1 - r)]
    logo = np.zeros_like(x, dtype=bool)
    for merkez in rotorlar:
        logo |= _parca_uzakligi(x, y, (0.5, 0.5), merkez) <= KOL_KALINLIGI / 2
        logo |= np.abs(np.hypot(x - merkez[0], y - merkez[1]) - ROTOR_YARICAPI) <= ROTOR_KALINLIGI / 2
    logo |= (np.abs(x - 0.5) <= GOVDE_YARI) & (np.abs(y - 0.5) <= GOVDE_YARI)

    rgb = np.zeros((n, n, 3), dtype=float)
    rgb[zemin] = ZEMIN_RENGI
    rgb[cerceve] = CERCEVE_RENGI
    rgb[logo & zemin] = LOGO_RENGI
    alfa = zemin.astype(float)

    # Alt örnekleri birleştirerek kenarları yumuşat.
    def kucult(d: np.ndarray) -> np.ndarray:
        return d.reshape(boyut, KENAR_YUMUSATMA, boyut, KENAR_YUMUSATMA, *d.shape[2:]).mean(axis=(1, 3))

    a = kucult(alfa)
    renk = kucult(rgb * alfa[..., None]) / np.maximum(a[..., None], 1e-9)
    return np.dstack([renk, a * 255]).round().clip(0, 255).astype(np.uint8)


def png_yaz(rgba: np.ndarray) -> bytes:
    """RGBA diziyi PNG baytlarına çevirir (standart kütüphaneyle)."""
    yukseklik, genislik = rgba.shape[:2]

    def parca(tur: bytes, veri: bytes) -> bytes:
        return struct.pack(">I", len(veri)) + tur + veri + struct.pack(">I", zlib.crc32(tur + veri) & 0xFFFFFFFF)

    ham = b"".join(b"\x00" + rgba[satir].tobytes() for satir in range(yukseklik))
    return (
        b"\x89PNG\r\n\x1a\n"
        + parca(b"IHDR", struct.pack(">IIBBBBB", genislik, yukseklik, 8, 6, 0, 0, 0))
        + parca(b"IDAT", zlib.compress(ham, 9))
        + parca(b"IEND", b"")
    )


def ico_yaz(boyutlar: tuple[int, ...] = BOYUTLAR) -> bytes:
    """Her boyut için PNG içeren ICO dosyası baytları (Windows Vista ve sonrası destekler)."""
    resimler = [png_yaz(simge_ciz(b)) for b in boyutlar]
    baslik = struct.pack("<HHH", 0, 1, len(boyutlar))
    konum = len(baslik) + 16 * len(boyutlar)
    girdiler = b""
    for b, resim in zip(boyutlar, resimler):
        # 256 piksel ICO'da 0 olarak yazılır.
        girdiler += struct.pack("<BBBBHHII", b % 256, b % 256, 0, 0, 1, 32, len(resim), konum)
        konum += len(resim)
    return baslik + girdiler + b"".join(resimler)


def ana() -> None:
    """Simgeyi arayuz/statik/<program adı>.ico olarak yazar."""
    SIMGE_YOLU.write_bytes(ico_yaz())
    print(f"Simge yazıldı: {SIMGE_YOLU}")


if __name__ == "__main__":
    ana()
