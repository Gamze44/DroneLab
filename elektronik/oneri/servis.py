"""
Öneri akışını yöneten servis: "Öner" düğmesi ve "Bunu seç" bu sınıfı çağırır.

Gemini yalnızca kullanıcı "Öner"e bastığında ve günlük sınır aşılmadıysa çağrılır.
Katalogda aynı parça zaten varsa modelin değerleri yerine katalogdaki (çoğu zaman
kullanıcının doğruladığı) kayıt kullanılır.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from arastirma.istemci import YapayZekaIstemcisi
from cekirdek.hatalar import GecersizDegerHatasi, YapayZekaHatasi
from elektronik.oneri.aday import AdayDonusturucu
from elektronik.oneri.degerlendirici import AdayDegerlendirici, Degerlendirme
from elektronik.oneri.istem import ADAY_SAYISI, SISTEM_TALIMATI, OneriIstemiOlusturucu
from elektronik.oneri.sema import OneriSemasiOlusturucu
from elektronik.parcalar.drone_parcasi import DroneParcasi
from elektronik.parcalar.kayit import parca_sinifi
from elektronik.parcalar.parca import Parca
from elektronik.parcalar.turler import ALT_TUR_GEREKLI_MESAJI, DigerAltTur, ParcaDurumu, ParcaTuru
from elektronik.servis import ElektronikServisi
from sartname.modeller import Madde

# Drone kimliği -> öneride uyulacak şartname maddeleri (şartname yoksa boş liste).
SartnameMaddeKaynagi = Callable[[int], list[Madde]]


def _sartname_yok(_: int) -> list[Madde]:
    return []


@dataclass
class OneriAdayi:
    """
    Alanlar:
        parca: Aday parça (katalogdaysa katalog kaydı, değilse kaydedilmemiş ve doğrulanmamış).
        gerekce: Modelin gerekçesi.
        katalog_kimlik: Katalogda varsa kaydın kimliği.
        silinen_alanlar: Geçersiz olduğu için silinen alanlar.
        degerlendirme: Programın uyum ve uçuş değerlendirmesi.
    """

    parca: Parca
    gerekce: str
    katalog_kimlik: int | None
    silinen_alanlar: list[str]
    degerlendirme: Degerlendirme


@dataclass
class OneriSonucu:
    """
    Alanlar:
        adaylar: Sıralanmış adaylar (uyumsuzlar sonda).
        atlanan: Kullanılamayan (adı eksik, tekrar eden, zaten drone'da olan) aday sayısı.
        bugun_kullanilan / gunluk_sinir: Günlük kullanım bilgisi.
        model: Kullanılan model.
    """

    adaylar: list[OneriAdayi] = field(default_factory=list)
    atlanan: int = 0
    bugun_kullanilan: int = 0
    gunluk_sinir: int = 0
    model: str = ""


class OneriServisi:
    """
    Parça önerisi ister, adayları doğrular ve değerlendirir; seçilen adayı drone'a ekler.

    Parametreler:
        elektronik: Parça ve drone bilgilerine erişen ElektronikServisi.
        yapay_zeka: Anahtar ve günlük sınır kontrolüyle istek gönderen istemci.
        sartname_maddeleri: Drone'un şartnamesindeki onaylı kesin maddeleri veren fonksiyon.
    """

    def __init__(
        self,
        elektronik: ElektronikServisi,
        yapay_zeka: YapayZekaIstemcisi,
        sartname_maddeleri: SartnameMaddeKaynagi = _sartname_yok,
    ) -> None:
        self._elektronik = elektronik
        self._yz = yapay_zeka
        self._sartname_maddeleri = sartname_maddeleri
        self._istem = OneriIstemiOlusturucu()
        self._sema = OneriSemasiOlusturucu()
        self._donusturucu = AdayDonusturucu()
        self._degerlendirici = AdayDegerlendirici()

    def oner(self, drone_kimlik: int, tur: ParcaTuru, alt_tur: DigerAltTur | None = None) -> OneriSonucu:
        """
        Gemini'den aday ister ve değerlendirir.

        Hatalar:
            KayitBulunamadiHatasi: Drone yoksa.
            GecersizDegerHatasi: "Diğer" türünde alt tür seçilmediyse.
            YapayZekaHatasi: Anahtar yoksa, günlük sınır dolduysa veya istek başarısızsa.
        """
        if tur is ParcaTuru.DIGER and alt_tur is None:
            raise GecersizDegerHatasi(ALT_TUR_GEREKLI_MESAJI)
        if tur is not ParcaTuru.DIGER:
            alt_tur = None
        ozet = self._elektronik.ozet(drone_kimlik)
        maddeler = self._sartname_maddeleri(drone_kimlik)
        kalemler = ozet.parca_adetleri
        istem = self._istem.olustur(
            ozet.drone, kalemler, ozet.sasi_olculeri, tur, alt_tur, hedefler=ozet.hedefler, sartname_maddeleri=maddeler
        )
        yanit = self._yz.istek(SISTEM_TALIMATI, istem, self._sema.olustur(parca_sinifi(tur)))
        ham_adaylar = yanit.veri.get("adaylar")
        if not isinstance(ham_adaylar, list):
            raise YapayZekaHatasi("Gemini beklenen biçimde aday listesi döndürmedi. Tekrar deneyin.")

        sonuc = OneriSonucu(bugun_kullanilan=yanit.bugun_kullanilan, gunluk_sinir=yanit.gunluk_sinir, model=yanit.model)
        gorulen = {p.arama_anahtari for p, _ in kalemler}  # drone'da zaten olanlar önerilmez
        for ham in ham_adaylar[: ADAY_SAYISI * 2]:  # model fazla döndürürse sınırla
            donusen = self._donusturucu.donustur(tur, alt_tur, ham)
            if donusen is None or donusen.parca.arama_anahtari in gorulen:
                sonuc.atlanan += 1
                continue
            gorulen.add(donusen.parca.arama_anahtari)
            katalogdaki = self._elektronik.katalogdaki_karsiligi(donusen.parca)
            parca = katalogdaki or donusen.parca
            sonuc.adaylar.append(OneriAdayi(
                parca=parca,
                gerekce=donusen.gerekce,
                katalog_kimlik=katalogdaki.kimlik if katalogdaki else None,
                silinen_alanlar=[] if katalogdaki else donusen.silinen_alanlar,
                degerlendirme=self._degerlendirici.degerlendir(
                    parca, ozet.drone, kalemler, ozet.sasi_olculeri, ozet.hedefler, maddeler
                ),
            ))
            if len(sonuc.adaylar) == ADAY_SAYISI:
                break
        sonuc.adaylar.sort(key=lambda a: a.degerlendirme.siralama_anahtari)
        return sonuc

    def sec(
        self,
        drone_kimlik: int,
        adet: int,
        parca_kimlik: int | None = None,
        tur: ParcaTuru | None = None,
        alt_tur: DigerAltTur | None = None,
        ortak: dict[str, Any] | None = None,
        teknik: dict[str, Any] | None = None,
    ) -> DroneParcasi:
        """
        Seçilen adayı drone'a "önerilen" durumuyla ekler.

        Katalogdaki aday kimliğiyle, yeni aday parça bilgisiyle gelir. Yeni aday yeniden
        doğrulanır ve "doğrulanmadı" olarak kataloğa yazılır.

        Hatalar:
            KayitBulunamadiHatasi, KayitZatenVarHatasi, GecersizDegerHatasi.
        """
        if parca_kimlik is not None:
            return self._elektronik.katalogdan_ekle(drone_kimlik, parca_kimlik, adet, ParcaDurumu.ONERILEN)
        if tur is None or ortak is None:
            raise GecersizDegerHatasi("Seçilen önerinin parça bilgisi eksik.")
        parca = self._elektronik.oneri_parcasi_olustur(tur, alt_tur, ortak, teknik or {})
        return self._elektronik.yeni_parca_ekle(drone_kimlik, parca, adet, ParcaDurumu.ONERILEN)
