"""
Masaüstüne program kısayolu oluşturur.

Çalıştırma: .venv\\Scripts\\python.exe -m araclar.kisayol_olustur

Kısayol, programı konsol penceresi olmadan (pythonw.exe) masaustu.py ile açar ve
program simgesini kullanır. Proje klasörü veya sanal ortam taşınırsa bu komut
yeniden çalıştırılmalıdır (kısayol eski yolu gösterir). Kısayol Windows'un kendi
WScript.Shell bileşeniyle PowerShell üzerinden yazılır; ek kütüphane gerekmez.
"""

import os
from pathlib import Path
import subprocess
import sys
from typing import Final

from cekirdek.ayarlar import PROGRAM_ADI, PROJE_KOKU, SIMGE_YOLU

KISAYOL_ACIKLAMASI: Final[str] = f"{PROGRAM_ADI} – Drone tasarla, kontrol et, harekete geç"
GIRIS_DOSYASI: Final[Path] = PROJE_KOKU / "masaustu.py"
KONSOLSUZ_PYTHON: Final[str] = "pythonw.exe"
# PowerShell tam yoluyla çağrılır: yalnızca "powershell" yazılırsa Windows önce çalışma
# klasörüne bakar; oraya konmuş sahte bir powershell.exe çalışabilirdi.
POWERSHELL_GORELI_YOLU: Final[tuple[str, ...]] = ("System32", "WindowsPowerShell", "v1.0", "powershell.exe")
VARSAYILAN_WINDOWS_KLASORU: Final[str] = r"C:\Windows"

# Yollar komut metnine gömülmez, ortam değişkeniyle verilir: klasör adında boşluk veya
# tırnak olsa bile komut bozulmasın.
POWERSHELL_KOMUTU: Final[str] = (
    "$masaustu = [Environment]::GetFolderPath('Desktop'); "
    "$yol = Join-Path $masaustu ($env:GK_AD + '.lnk'); "
    "$k = (New-Object -ComObject WScript.Shell).CreateShortcut($yol); "
    "$k.TargetPath = $env:GK_HEDEF; "
    "$k.Arguments = '\"' + $env:GK_GIRIS + '\"'; "
    "$k.WorkingDirectory = $env:GK_KLASOR; "
    "$k.IconLocation = $env:GK_SIMGE + ',0'; "
    "$k.Description = $env:GK_ACIKLAMA; "
    "$k.Save(); "
    "Write-Output $yol"
)


def konsolsuz_python() -> Path:
    """
    Şu an çalışan sanal ortamın pythonw.exe yolu.

    Hatalar:
        FileNotFoundError: pythonw.exe bulunamazsa.
    """
    yol = Path(sys.executable).with_name(KONSOLSUZ_PYTHON)
    if not yol.is_file():
        raise FileNotFoundError(f"{KONSOLSUZ_PYTHON} bulunamadı: {yol}. Komutu .venv içindeki Python ile çalıştırın.")
    return yol


def powershell_yolu() -> Path:
    """
    Windows'un kendi PowerShell'inin tam yolu (%SystemRoot%\\System32\\...\\powershell.exe).

    Hatalar:
        FileNotFoundError: PowerShell bulunamazsa.
    """
    yol = Path(os.environ.get("SystemRoot", VARSAYILAN_WINDOWS_KLASORU)).joinpath(*POWERSHELL_GORELI_YOLU)
    if not yol.is_file():
        raise FileNotFoundError(f"PowerShell bulunamadı: {yol}")
    return yol


def kisayol_olustur() -> Path:
    """
    Masaüstüne kısayolu yazar (varsa üzerine yazar).

    Dönüş:
        Oluşturulan .lnk dosyasının yolu.
    Hatalar:
        FileNotFoundError: Simge veya pythonw bulunamazsa.
        subprocess.CalledProcessError: Kısayol yazılamazsa.
    """
    if not SIMGE_YOLU.is_file():
        raise FileNotFoundError(f"Simge yok: {SIMGE_YOLU}. Önce: python -m araclar.simge_olustur")
    ortam = {
        **os.environ,
        "GK_AD": PROGRAM_ADI,
        "GK_HEDEF": str(konsolsuz_python()),
        "GK_GIRIS": str(GIRIS_DOSYASI),
        "GK_KLASOR": str(PROJE_KOKU),
        "GK_SIMGE": str(SIMGE_YOLU),
        "GK_ACIKLAMA": KISAYOL_ACIKLAMASI,
    }
    sonuc = subprocess.run(
        [str(powershell_yolu()), "-NoProfile", "-NonInteractive", "-Command", POWERSHELL_KOMUTU],
        env=ortam, capture_output=True, text=True, check=True,
    )
    return Path(sonuc.stdout.strip().splitlines()[-1])


if __name__ == "__main__":
    print(f"Kısayol oluşturuldu: {kisayol_olustur()}")
