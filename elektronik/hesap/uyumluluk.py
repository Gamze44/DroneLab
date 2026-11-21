"""
Bütün uyum kontrollerini sırayla çalıştıran sınıf.

Yeni bir kontrol eklemek için uyum_kontrolleri.py'de UyumKontrolu'ndan türeyen
bir sınıf yazıp VARSAYILAN_KONTROLLER listesine eklemek yeterlidir.
"""

from elektronik.hesap.uyum import KontrolBaglami, UyumKontrolu, UyumSonucu
from elektronik.hesap.uyum_kontrolleri import (
    AliciFcKontrolu,
    EscAkimKontrolu,
    FcEscMontajKontrolu,
    FcEscProtokolKontrolu,
    IkinciGrupGerilimKontrolu,
    KonnektorKontrolu,
    MotorPervaneKontrolu,
    MotorSayisiKontrolu,
    PervaneSasiKontrolu,
    PilAkimKontrolu,
    PilEscHucreKontrolu,
    PilGirisGerilimiKontrolu,
    PilMotorHucreKontrolu,
)
from elektronik.parcalar.parca import Parca
from sasi.modeller import SasiOlculeri

# DEĞİŞTİRİLEBİLİR: Çalıştırılacak kontroller ve ekrandaki sırası.
VARSAYILAN_KONTROLLER: tuple[type[UyumKontrolu], ...] = (
    PilMotorHucreKontrolu,
    PilEscHucreKontrolu,
    PilGirisGerilimiKontrolu,
    MotorPervaneKontrolu,
    PervaneSasiKontrolu,
    EscAkimKontrolu,
    PilAkimKontrolu,
    FcEscMontajKontrolu,
    FcEscProtokolKontrolu,
    AliciFcKontrolu,
    MotorSayisiKontrolu,
    KonnektorKontrolu,
    IkinciGrupGerilimKontrolu,
)


class UyumlulukKontrolcusu:
    """
    Bir drone'un parçalarını bütün uyum kontrollerinden geçirir.

    Parametreler:
        kontroller: Çalıştırılacak kontrol nesneleri; verilmezse VARSAYILAN_KONTROLLER.
    """

    def __init__(self, kontroller: list[UyumKontrolu] | None = None) -> None:
        self._kontroller = kontroller if kontroller is not None else [k() for k in VARSAYILAN_KONTROLLER]

    def kontrol_et(
        self, kalemler: list[tuple[Parca, int]], motor_sayisi: int, sasi_olculeri: SasiOlculeri | None = None
    ) -> list[UyumSonucu]:
        """
        Kontrolleri çalıştırır.

        Parametreler:
            kalemler: (parça, adet) listesi; durumu ne olursa olsun (elimde/planlanan) kontrol edilir.
            motor_sayisi: Drone türüne göre motor sayısı.
            sasi_olculeri: Birim onaylanmış şasi ölçüleri (K5 için); yoksa None.
        Dönüş:
            Her kontrol için bir UyumSonucu, ekran sırasıyla.
        """
        baglam = KontrolBaglami(kalemler=kalemler, motor_sayisi=motor_sayisi, sasi_olculeri=sasi_olculeri)
        return [k.kontrol_et(baglam) for k in self._kontroller]
