"""
Parçalı şasi okuyucusu: kol, gövde, ayak gibi parçaları ayrı dosyalarda olan bir zip arşivi.

Güvenlik:
    - Arşiv açılmadan önce zip bombasına karşı denetlenir (ArsivDenetleyici).
    - Zip içindeki adlar ASLA disk yolu olarak kullanılmaz ("..\\..\\a.stl" gibi adlar
      klasör dışına yazdırabilir). Her parça yeni, boş bir geçici klasöre programın
      ürettiği "parca_<sıra><uzantı>" adıyla çıkarılır; asıl ad yalnızca ekranda gösterilir.
    - Parça okunduktan sonra geçici klasör silinir; dosyanın kendisi zaten arşivde saklanır.
"""

from dataclasses import dataclass, field
from collections.abc import Callable
import logging
from pathlib import Path, PurePosixPath
import shutil
import tempfile
from typing import Final
import zipfile

from cekirdek.arsiv_denetimi import BOZUK_ARSIV_MESAJI, ArsivDenetleyici
from cekirdek.hatalar import DroneProgramHatasi, DosyaOkumaHatasi
from sasi.modeller import SasiGeometrisi
from sasi.okuyucular.temel import SasiOkuyucu

gunluk = logging.getLogger(__name__)

# DEĞİŞTİRİLEBİLİR: Bir zip'te okunacak en çok parça dosyası. Gerçek şasiler 3–15 parçadır;
# sınır, yüzlerce dosyalı bir arşivin okunması sırasında programın uzun süre donmasını önler.
EN_FAZLA_SASI_PARCASI: Final[int] = 30
# Ekranda gösterilen parça adının en çok uzunluğu (zip'teki ad çok uzun olabilir).
EN_UZUN_PARCA_ADI: Final[int] = 120
# İşletim sistemlerinin arşive eklediği, parça olmayan klasör ve dosyalar.
ATLANAN_KLASORLER: Final[frozenset[str]] = frozenset({"__macosx"})
GECICI_KLASOR_ONEKI: Final[str] = "dronelab_zip_"
GECICI_PARCA_ONEKI: Final[str] = "parca_"


@dataclass
class ZipOkumaSonucu:
    """
    Alanlar:
        parcalar: Okunan parça geometrileri, zip'teki sırayla (dosya_adi = zip'teki dosya adı).
        uyarilar: Atlanan veya okunamayan dosyalar için Türkçe uyarılar.
    """

    parcalar: list[SasiGeometrisi] = field(default_factory=list)
    uyarilar: list[str] = field(default_factory=list)


class ZipSasiOkuyucu:
    """
    Zip içindeki her şasi parçasını, uzantısına uygun okuyucuyla okur.

    Parametreler:
        parca_okuyucusu: Uzantıdan (ör. ".stl") okuyucu döndüren işlev; uzantı desteklenmiyorsa None.
            Neden dışarıdan verilir: okuyucu seçici bu sınıfı da tanıdığı için doğrudan
            içe aktarmak döngüsel bağımlılık yaratırdı.
        arsiv_denetleyici: Zip bombası denetimi; verilmezse varsayılan sınırlar kullanılır.
    """

    UZANTILAR: Final[tuple[str, ...]] = (".zip",)

    def __init__(
        self,
        parca_okuyucusu: Callable[[str], SasiOkuyucu | None],
        arsiv_denetleyici: ArsivDenetleyici | None = None,
    ) -> None:
        self._parca_okuyucusu = parca_okuyucusu
        self._arsiv = arsiv_denetleyici or ArsivDenetleyici()

    def oku(self, yol: Path) -> ZipOkumaSonucu:
        """
        Zip'teki şasi parçalarını okur.

        Parametreler:
            yol: .zip dosyasının yolu.
        Dönüş:
            ZipOkumaSonucu (ölçüler her parçanın dosya biriminde).
        Hatalar:
            DosyaOkumaHatasi: Zip bozuk veya şüpheliyse, parola korumalıysa, parça yoksa
                ya da parça sayısı sınırı aşıyorsa.
        """
        self._arsiv.denetle(yol)
        sonuc = ZipOkumaSonucu()
        try:
            with zipfile.ZipFile(yol) as arsiv:
                uyeler = self._parca_uyelerini_sec(arsiv.infolist(), sonuc.uyarilar)
                if len(uyeler) > EN_FAZLA_SASI_PARCASI:
                    raise DosyaOkumaHatasi(
                        f"Zip'te {len(uyeler)} parça dosyası var; en çok {EN_FAZLA_SASI_PARCASI} parça okunabilir. "
                        "Şasiye ait olmayan dosyaları çıkarıp tekrar deneyin."
                    )
                with tempfile.TemporaryDirectory(prefix=GECICI_KLASOR_ONEKI) as klasor:
                    for sira, (uye, okuyucu) in enumerate(uyeler):
                        geometri = self._parcayi_oku(arsiv, uye, okuyucu, Path(klasor), sira, sonuc.uyarilar)
                        if geometri is not None:
                            sonuc.parcalar.append(geometri)
        except (zipfile.BadZipFile, OSError, ValueError) as hata:
            gunluk.warning("Zip okunamadı: %s", hata)
            raise DosyaOkumaHatasi(BOZUK_ARSIV_MESAJI) from hata

        if not sonuc.parcalar:
            ek = f" {' '.join(sonuc.uyarilar)}" if sonuc.uyarilar else ""
            raise DosyaOkumaHatasi(
                "Zip içinde okunabilen şasi parçası bulunamadı. Parçalar STL, OBJ, 3MF veya DXF olmalı." + ek
            )
        return sonuc

    def _parca_uyelerini_sec(
        self, uyeler: list[zipfile.ZipInfo], uyarilar: list[str]
    ) -> list[tuple[zipfile.ZipInfo, SasiOkuyucu]]:
        """
        Klasörleri, sistem dosyalarını ve desteklenmeyen türleri ayıklar.

        Parametreler:
            uyeler: Arşivin içindekiler listesi.
            uyarilar: Atlanan dosyalar için uyarının ekleneceği liste.
        Dönüş:
            (üye, okuyucu) listesi.
        """
        secilen: list[tuple[zipfile.ZipInfo, SasiOkuyucu]] = []
        atlanan: list[str] = []
        for uye in uyeler:
            if uye.is_dir():
                continue
            yol = PurePosixPath(uye.filename.replace("\\", "/"))
            if any(p.lower() in ATLANAN_KLASORLER for p in yol.parts) or yol.name.startswith("."):
                continue
            okuyucu = self._parca_okuyucusu(yol.suffix.lower())
            if okuyucu is None:
                atlanan.append(self.gorunen_ad(uye))
                continue
            secilen.append((uye, okuyucu))
        if atlanan:
            uyarilar.append(f"Şasi parçası olmayan dosyalar atlandı: {', '.join(atlanan)}.")
        return secilen

    def _parcayi_oku(
        self,
        arsiv: zipfile.ZipFile,
        uye: zipfile.ZipInfo,
        okuyucu: SasiOkuyucu,
        klasor: Path,
        sira: int,
        uyarilar: list[str],
    ) -> SasiGeometrisi | None:
        """
        Bir üyeyi güvenli adla geçici klasöre çıkarıp okur.

        Neden okunamayan parça tüm zip'i durdurmaz: kullanıcı diğer parçalarla devam
        edebilsin; hangi dosyanın atlandığı uyarıda yazar.

        Dönüş:
            Parçanın geometrisi; okunamadıysa None (uyarı eklenir).
        Hatalar:
            DosyaOkumaHatasi: Üye parola korumalıysa (diğerleri de büyük olasılıkla öyledir).
        """
        ad = self.gorunen_ad(uye)
        hedef = klasor / f"{GECICI_PARCA_ONEKI}{sira}{PurePosixPath(uye.filename).suffix.lower()}"
        try:
            with arsiv.open(uye) as kaynak, hedef.open("wb") as cikti:
                shutil.copyfileobj(kaynak, cikti)
        except RuntimeError as hata:
            # zipfile parola isteyen üyede RuntimeError fırlatır.
            raise DosyaOkumaHatasi("Zip parola korumalı; parolasız bir zip olarak yeniden kaydedip yükleyin.") from hata
        try:
            geometri = okuyucu.oku(hedef)
        except DroneProgramHatasi as hata:
            # Okuyucunun mesajında geçici ad geçer; kullanıcı kendi dosya adını görmeli.
            uyarilar.append(f"'{ad}' okunamadı ve atlandı: {hata.mesaj.replace(hedef.name, ad)}")
            return None
        except Exception as hata:
            # Bozuk bir parça kütüphanede beklenmedik bir hata verebilir; diğer parçalar yine okunur.
            gunluk.warning("Zip parçası okunamadı: %s", hata)
            uyarilar.append(f"'{ad}' okunamadı ve atlandı; dosya bozuk olabilir.")
            return None
        finally:
            hedef.unlink(missing_ok=True)
        geometri.dosya_adi = ad
        # Ağ (trimesh) yalnızca okuma sırasında gerekir; 30 parçanın ağını bellekte tutmaya gerek yok.
        geometri.ag = None
        return geometri

    @staticmethod
    def gorunen_ad(uye: zipfile.ZipInfo) -> str:
        """
        Zip üyesinin ekranda gösterilecek adı (klasör yolu olmadan, kısaltılmış).

        Parametreler:
            uye: Zip üyesi.
        Dönüş:
            Dosya adı.
        """
        ad = PurePosixPath(uye.filename.replace("\\", "/")).name
        return ad if len(ad) <= EN_UZUN_PARCA_ADI else ad[: EN_UZUN_PARCA_ADI - 1] + "…"
