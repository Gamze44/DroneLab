"""
Drone türüne göre zorunlu parçaların kontrolü.

Bu modül yalnızca "parça var mı, yeterli sayıda mı" sorusuna bakar;
parçaların birbiriyle uyumunu uyum kontrolleri (sonraki adım) yapar.
İlk sürüm yalnızca çok rotorlu droneları kapsar; sabit kanat sonraki sürümde.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Final

from elektronik.parcalar.cekirdek_parcalar import Esc, UcusKarti
from elektronik.parcalar.parca import Parca
from elektronik.parcalar.turler import PARCA_TURU_ADLARI, DigerAltTur, ParcaTuru
from elektronik.parcalar.diger_parca import DigerParca

# DEĞİŞTİRİLEBİLİR: Bu amaçlarda GPS önerilir (zorunlu değil). Adlar drone.modeller.KULLANIM_AMACLARI ile aynı olmalı.
GPS_ONERILEN_AMACLAR: Final[frozenset[str]] = frozenset({"Yük taşıma", "Hava fotoğrafı / video çekimi"})

# DEĞİŞTİRİLEBİLİR: Her drone'da birer tane bulunması gereken parçalar.
TEKIL_ZORUNLULAR: Final[tuple[ParcaTuru, ...]] = (ParcaTuru.PIL, ParcaTuru.UCUS_KARTI, ParcaTuru.ALICI)


class ZorunlulukDurumu(str, Enum):
    """Bir zorunluluğun sonucu."""

    TAMAM = "tamam"
    EKSIK = "eksik"
    BILINMIYOR = "bilinmiyor"  # karar vermek için gereken değer girilmemiş
    ISTEGE_BAGLI = "istege_bagli"  # bu yapılandırmada gerekmiyor
    ONERILEN = "onerilen"  # zorunlu değil ama amaç için önerilir ve yok


@dataclass(frozen=True)
class Zorunluluk:
    """
    Bir parça türü için zorunluluk sonucu.

    Alanlar:
        etiket: Ekranda görünen ad (ör. "Motor").
        gereken: Gereken adet (ESC'de kanal sayısı); bilgi amaçlı.
        mevcut: Drone'daki adet (ESC'de toplam kanal; bilinmiyorsa None).
        durum: ZorunlulukDurumu.
        aciklama: Kullanıcıya gösterilecek kısa Türkçe açıklama.
    """

    etiket: str
    gereken: int
    mevcut: int | None
    durum: ZorunlulukDurumu
    aciklama: str


class ZorunluParcaDenetleyici:
    """Bir drone'un parça listesinde zorunlu parçaların eksik olup olmadığına bakar."""

    @staticmethod
    def _adet(kalemler: list[tuple[Parca, int]], tur: ParcaTuru) -> int:
        """Belirtilen türdeki parçaların toplam adedi."""
        return sum(adet for parca, adet in kalemler if parca.tur is tur)

    @staticmethod
    def _sayim(etiket: str, gereken: int, mevcut: int) -> Zorunluluk:
        """Basit "en az N adet" zorunluluğu."""
        if mevcut >= gereken:
            return Zorunluluk(etiket, gereken, mevcut, ZorunlulukDurumu.TAMAM, f"{mevcut}/{gereken}")
        return Zorunluluk(etiket, gereken, mevcut, ZorunlulukDurumu.EKSIK, f"{mevcut}/{gereken} – {gereken - mevcut} eksik")

    def denetle(self, kalemler: list[tuple[Parca, int]], motor_sayisi: int, amac: str) -> list[Zorunluluk]:
        """
        Zorunlu parçaları denetler.

        Parametreler:
            kalemler: (parça, adet) listesi; durumu ne olursa olsun (elimde/planlanan…) sayılır.
            motor_sayisi: Drone türüne göre motor sayısı.
            amac: Drone'un kullanım amacı (GPS önerisi için).
        Dönüş:
            Zorunluluk listesi (ekranda bu sırayla gösterilir).
        """
        sonuc = [
            self._sayim(PARCA_TURU_ADLARI[ParcaTuru.MOTOR], motor_sayisi, self._adet(kalemler, ParcaTuru.MOTOR)),
            self._sayim(PARCA_TURU_ADLARI[ParcaTuru.PERVANE], motor_sayisi, self._adet(kalemler, ParcaTuru.PERVANE)),
            self._esc(kalemler, motor_sayisi),
        ]
        sonuc += [self._sayim(PARCA_TURU_ADLARI[t], 1, self._adet(kalemler, t)) for t in TEKIL_ZORUNLULAR]
        sonuc.append(self._guc_dagitim(kalemler))
        if amac in GPS_ONERILEN_AMACLAR:
            sonuc.append(self._gps(kalemler))
        return sonuc

    @staticmethod
    def _esc(kalemler: list[tuple[Parca, int]], motor_sayisi: int) -> Zorunluluk:
        """
        ESC'lerin toplam kanalı motor sayısına yetiyor mu.

        4'ü 1 arada ESC 4 motor sürer; bu yüzden adet değil kanal sayılır. Kanal sayısı
        girilmemiş ESC varsa tahmin edilmez, sonuç "bilinmiyor" olur.
        """
        etiket = PARCA_TURU_ADLARI[ParcaTuru.ESC]
        escler = [(p, adet) for p, adet in kalemler if isinstance(p, Esc)]
        if not escler:
            return Zorunluluk(etiket, motor_sayisi, 0, ZorunlulukDurumu.EKSIK, f"0/{motor_sayisi} kanal – ESC eklenmedi")
        if any(p.kanal_sayisi is None for p, _ in escler):
            return Zorunluluk(
                etiket, motor_sayisi, None, ZorunlulukDurumu.BILINMIYOR,
                "ESC'nin kanal sayısı girilmemiş (4'ü 1 arada ise 4, tekli ise 1).",
            )
        kanal = sum(p.kanal_sayisi * adet for p, adet in escler)
        if kanal >= motor_sayisi:
            return Zorunluluk(etiket, motor_sayisi, kanal, ZorunlulukDurumu.TAMAM, f"{kanal}/{motor_sayisi} kanal")
        return Zorunluluk(
            etiket, motor_sayisi, kanal, ZorunlulukDurumu.EKSIK, f"{kanal}/{motor_sayisi} kanal – {motor_sayisi - kanal} eksik"
        )

    def _guc_dagitim(self, kalemler: list[tuple[Parca, int]]) -> Zorunluluk:
        """
        Güç dağıtım kartı gerekli mi.

        4'ü 1 arada ESC (birden çok kanallı) veya dahili PDB'li uçuş kartı varsa gücü
        zaten dağıtır, ayrı PDB gerekmez. Tekli ESC'lerle ayrı PDB gerekir.
        """
        etiket = PARCA_TURU_ADLARI[ParcaTuru.GUC_DAGITIM]
        mevcut = self._adet(kalemler, ParcaTuru.GUC_DAGITIM)
        if mevcut:
            return Zorunluluk(etiket, 1, mevcut, ZorunlulukDurumu.TAMAM, "eklendi")
        if any(isinstance(p, UcusKarti) and p.dahili_pdb for p, _ in kalemler):
            return Zorunluluk(etiket, 1, 0, ZorunlulukDurumu.ISTEGE_BAGLI, "uçuş kartında dahili güç dağıtımı var")
        escler = [p for p, _ in kalemler if isinstance(p, Esc)]
        if not escler or any(p.kanal_sayisi is None for p in escler):
            return Zorunluluk(
                etiket, 1, 0, ZorunlulukDurumu.BILINMIYOR, "ESC türü belli olunca karar verilir (4'ü 1 arada ise gerekmez)"
            )
        if all(p.kanal_sayisi > 1 for p in escler):
            return Zorunluluk(etiket, 1, 0, ZorunlulukDurumu.ISTEGE_BAGLI, "4'ü 1 arada ESC gücü dağıtıyor")
        return Zorunluluk(etiket, 1, 0, ZorunlulukDurumu.EKSIK, "tekli ESC'ler için güç dağıtım kartı gerekir")

    @staticmethod
    def _gps(kalemler: list[tuple[Parca, int]]) -> Zorunluluk:
        """Amaç gerektiriyorsa GPS önerisi (zorunlu değil)."""
        etiket = "GPS"
        var = any(isinstance(p, DigerParca) and p.alt_tur is DigerAltTur.GPS for p, _ in kalemler)
        if var:
            return Zorunluluk(etiket, 1, 1, ZorunlulukDurumu.TAMAM, "eklendi")
        return Zorunluluk(etiket, 1, 0, ZorunlulukDurumu.ONERILEN, "bu kullanım amacı için önerilir")
