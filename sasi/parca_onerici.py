"""
Parçalı şaside her parçanın rolünü (gövde / kol / ayak / diğer) ve adedini önerir.

Öneri yalnızca dosya adına ve dosyadaki özdeş gövde sayısına bakar; bu yüzden yanlış
olabilir. Kullanıcı her parçanın rolünü ve adedini ekranda onaylar veya değiştirir.

Örnek: "7in Arms.stl" içinde baskı tablasına dizilmiş 4 özdeş kol varsa ve drone quad ise
adet 1 önerilir (4 kol zaten dosyada); dosyada tek kol varsa adet 4 önerilir.
"""

import re
from typing import Final

from sasi.modeller import ParcaRolu, SasiGeometrisi, SasiParcasi

# DEĞİŞTİRİLEBİLİR: Dosya adında geçen ve rolü belirleyen sözcükler (küçük harf, Türkçe
# karaktersiz). Bir sözcük, addaki bir sözcüğün başıyla eşleşir ("arm" -> "arms").
ROL_SOZCUKLERI: Final[dict[ParcaRolu, tuple[str, ...]]] = {
    ParcaRolu.AYAK: ("leg", "ayak", "landing", "bacak", "skid", "gear"),
    ParcaRolu.KOL: ("arm", "kol"),
    ParcaRolu.GOVDE: (
        "body", "govde", "frame", "plate", "top", "bottom", "main", "center", "centre",
        "ust", "alt", "plaka", "sasi", "chassis", "base",
    ),
}
# Rol sözcükleri bu sırayla denenir (ör. "landing arm" önce ayak sayılır).
ROL_SIRASI: Final[tuple[ParcaRolu, ...]] = (ParcaRolu.AYAK, ParcaRolu.KOL, ParcaRolu.GOVDE)
# DEĞİŞTİRİLEBİLİR: Bu sözcüklerden biri geçen parça bağlantı/aksesuar sayılır ("Arm Support",
# "Camera Mount"); kol veya gövde sanılırsa dingil ve dış ölçü hesabı bozulur.
YARDIMCI_SOZCUKLER: Final[tuple[str, ...]] = (
    "support", "suport", "destek", "brace", "mount", "guard", "holder", "tutucu", "koruma",
    "bracket", "spacer", "standoff", "clip", "strap", "camera", "kamera", "antenna", "anten",
)
# DEĞİŞTİRİLEBİLİR: Ayaklı şasilerde varsayılan ayak sayısı.
AYAK_SAYISI: Final[int] = 4

# Türkçe harfler sadeleştirilir ki "Gövde" ile "govde" aynı sayılsın.
TURKCE_HARFLER: Final[dict[int, int]] =str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
# "TopPlate", "top_plate", "top-plate 2" -> ["top", "plate", "2"]
SOZCUK_DESENI: Final[re.Pattern[str]] = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+")


class ParcaOnerici:
    """Parçalı şasinin parçalarına rol ve adet önerir."""

    @staticmethod
    def sozcukler(dosya_adi: str) -> list[str]:
        """
        Dosya adını (uzantısız) küçük harfli, Türkçe karaktersiz sözcüklere ayırır.

        Parametreler:
            dosya_adi: Parçanın dosya adı (ör. "7in Arms.stl").
        Dönüş:
            Sözcük listesi (ör. ["7", "in", "arms"]).
        """
        govde = dosya_adi.rsplit(".", 1)[0] if "." in dosya_adi else dosya_adi
        return [s.lower() for s in SOZCUK_DESENI.findall(govde.translate(TURKCE_HARFLER))]

    def rol_oner(self, dosya_adi: str) -> ParcaRolu:
        """
        Dosya adından parçanın rolünü önerir.

        Parametreler:
            dosya_adi: Parçanın dosya adı.
        Dönüş:
            ParcaRolu; ad tanınmazsa DIGER.
        """
        sozcukler = self.sozcukler(dosya_adi)

        def gecer_mi(adaylar: tuple[str, ...]) -> bool:
            return any(s.startswith(a) for s in sozcukler for a in adaylar)

        if gecer_mi(YARDIMCI_SOZCUKLER):
            return ParcaRolu.DIGER
        for rol in ROL_SIRASI:
            if gecer_mi(ROL_SOZCUKLERI[rol]):
                return rol
        return ParcaRolu.DIGER

    def oner(self, geometriler: list[SasiGeometrisi], motor_sayisi: int) -> list[SasiParcasi]:
        """
        Parçalara rol ve adet önerir.

        Kol adedi: toplam kol sayısı motor sayısına eşit olacak şekilde, kol dosyaları ve
        her dosyadaki özdeş kol sayısı hesaba katılarak bulunur. Ayak için AYAK_SAYISI kullanılır.
        Diğer parçalar 1 adet önerilir.

        Parametreler:
            geometriler: Zip'ten okunan parçalar, zip sırasıyla.
            motor_sayisi: Drone türüne göre motor sayısı.
        Dönüş:
            SasiParcasi listesi (sira 0'dan başlar).
        """
        roller = [self.rol_oner(g.dosya_adi) for g in geometriler]
        gereken = {ParcaRolu.KOL: motor_sayisi, ParcaRolu.AYAK: AYAK_SAYISI}
        dosya_sayilari = {rol: roller.count(rol) for rol in gereken}

        parcalar: list[SasiParcasi] = []
        for sira, (geometri, rol) in enumerate(zip(geometriler, roller)):
            adet = 1
            if rol in gereken:
                dosyadaki = max(geometri.ozdes_govde_sayisi, 1) * dosya_sayilari[rol]
                adet = max(1, round(gereken[rol] / dosyadaki))
            parcalar.append(SasiParcasi(sira=sira, geometri=geometri, rol=rol, adet=adet))
        return parcalar
