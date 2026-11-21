"""
Drone kaydının veri modelleri ve seçenek listeleri.

Bir drone; adı, nasıl başlandığı (sıfırdan / elimdeki), türü ve kullanım amacıyla
tanımlanır. Şasi bilgisi ayrı tutulur (bkz. sasi.modeller.KayitliSasi).
"""

from dataclasses import dataclass
from enum import Enum
from typing import Final


class BaslangicTuru(str, Enum):
    """Kullanıcının drone'a nasıl başladığı."""

    SIFIRDAN = "sifirdan"
    ELIMDEKI = "elimdeki"


class DroneTuru(str, Enum):
    """Drone türü. İlk sürüm yalnızca çok rotorlu droneları kapsar."""

    QUADCOPTER = "quadcopter"
    HEXACOPTER = "hexacopter"
    OKTOKOPTER = "oktokopter"


# DEĞİŞTİRİLEBİLİR: Ekranda görünen adlar.
BASLANGIC_TURU_ADLARI: Final[dict[BaslangicTuru, str]] = {
    BaslangicTuru.SIFIRDAN: "Sıfırdan yapım",
    BaslangicTuru.ELIMDEKI: "Elimdeki drone",
}

DRONE_TURU_ADLARI: Final[dict[DroneTuru, str]] = {
    DroneTuru.QUADCOPTER: "Quadcopter (4 motor)",
    DroneTuru.HEXACOPTER: "Hexacopter (6 motor)",
    DroneTuru.OKTOKOPTER: "Oktokopter (8 motor)",
}

MOTOR_SAYILARI: Final[dict[DroneTuru, int]] = {
    DroneTuru.QUADCOPTER: 4,
    DroneTuru.HEXACOPTER: 6,
    DroneTuru.OKTOKOPTER: 8,
}

# DEĞİŞTİRİLEBİLİR: Kullanım amacı listesi. Yeni amaç eklemek için buraya yazmak yeterli.
KULLANIM_AMACLARI: Final[tuple[str, ...]] = (
    "FPV yarış",
    "Serbest uçuş (freestyle)",
    "Hava fotoğrafı / video çekimi",
    "Yük taşıma",
    "Yarışma (şartnameli)",
    "Eğitim / deneme",
    "Diğer",
)


@dataclass
class Drone:
    """
    Kayıtlı bir drone.

    Alanlar:
        kimlik: Veritabanındaki benzersiz numara.
        ad: Kullanıcının verdiği ad.
        baslangic_turu: Sıfırdan mı, elimdeki drone'dan mı başlandığı.
        drone_turu: Quadcopter, hexacopter veya oktokopter.
        amac: Kullanım amacı (KULLANIM_AMACLARI içinden).
        olusturma_zamani: ISO biçiminde yerel zaman.
        guncelleme_zamani: Son değişikliğin ISO biçiminde yerel zamanı.
        sasi_agirlik_g: Elle girilen şasi ağırlığı, gram; girilmediyse None.
        sasi_var: Drone'a şasi dosyası yüklenmiş mi.
    """

    kimlik: int
    ad: str
    baslangic_turu: BaslangicTuru
    drone_turu: DroneTuru
    amac: str
    olusturma_zamani: str
    guncelleme_zamani: str
    sasi_agirlik_g: float | None = None
    sasi_var: bool = False

    @property
    def motor_sayisi(self) -> int:
        """Drone türüne göre motor sayısı."""
        return MOTOR_SAYILARI[self.drone_turu]
