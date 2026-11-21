"""
"Şunu değiştirirsem ne olur?" hesabı.

Değişiklikler drone'un parça listesinin BELLEKTEKİ kopyasına uygulanır ve tasarım,
kayıtlı drone'un özetiyle aynı sınıfla (TasarimHesaplayici) yeniden hesaplanır.
Hiçbir şey kaydedilmez. Asistanın senaryo_hesapla ve degisiklik_oner araçları ile öneri
uygulanmadan önceki son denetim bu sınıfı kullanır.
"""

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Final

from asistan.ayarlar import EN_FAZLA_DEGISIKLIK
from cekirdek.bicim import sayi_yaz
from cekirdek.hatalar import GecersizDegerHatasi, KayitBulunamadiHatasi
from cekirdek.sayilar import gecerli_sayi_mi
from drone.hedefler import DroneHedefleri
from elektronik.hesap.tasarim import TasarimHesaplayici, TasarimSonucu
from elektronik.hesap.ucus import HesapDegeri
from elektronik.hesap.uyum import UyumDurumu
from elektronik.parcalar.drone_parcasi import EN_FAZLA_ADET
from elektronik.parcalar.parca import Parca
from elektronik.servis import ElektronikServisi
from elektronik.zorunlu_parcalar import ZorunlulukDurumu

HEDEF_ALANLARI: Final[tuple[str, ...]] = ("ucus_suresi_dk", "yuk_g", "butce_tl", "itki_agirlik")


class DegisiklikTuru(str, Enum):
    """Önerilebilecek değişiklik türleri. Değerler araç şemasında ve veritabanında kullanılır."""

    PARCA_EKLE = "parca_ekle"
    PARCA_DEGISTIR = "parca_degistir"
    ADET_DEGISTIR = "adet_degistir"
    PARCA_CIKAR = "parca_cikar"
    HEDEF_DEGISTIR = "hedef_degistir"


@dataclass(frozen=True)
class Degisiklik:
    """
    Tek bir değişiklik.

    Alanlar:
        islem: Değişiklik türü.
        parca_kimlik: Katalogdaki parça (parca_ekle, parca_degistir).
        bag_kimlik: Drone'daki parça satırı (parca_degistir, adet_degistir, parca_cikar).
        adet: Adet (parca_ekle, adet_degistir; parca_degistir'de verilmezse eski adet).
        ucus_suresi_dk, yuk_g, butce_tl, itki_agirlik: Yeni hedefler (hedef_degistir; verilmeyen aynı kalır).
    """

    islem: DegisiklikTuru
    parca_kimlik: int | None = None
    bag_kimlik: int | None = None
    adet: int | None = None
    ucus_suresi_dk: float | None = None
    yuk_g: float | None = None
    butce_tl: float | None = None
    itki_agirlik: float | None = None

    @classmethod
    def sozlukten(cls, ham: Any) -> "Degisiklik":
        """
        Modelden (veya kayıttan) gelen sözlüğü denetleyerek Degisiklik'e çevirir.

        Hatalar:
            GecersizDegerHatasi: İşlem tanınmıyorsa, gereken alan eksikse veya tür yanlışsa.
        """
        if not isinstance(ham, dict):
            raise GecersizDegerHatasi("Her değişiklik bir nesne olmalı.")
        try:
            islem = DegisiklikTuru(ham.get("islem"))
        except ValueError:
            gecerli = ", ".join(t.value for t in DegisiklikTuru)
            raise GecersizDegerHatasi(f"Değişiklik türü tanınmıyor: {ham.get('islem')!r}. Seçenekler: {gecerli}.") from None
        degerler = {
            "parca_kimlik": _tamsayi(ham.get("parca_kimlik"), "parca_kimlik"),
            "bag_kimlik": _tamsayi(ham.get("bag_kimlik"), "bag_kimlik"),
            "adet": _tamsayi(ham.get("adet"), "adet"),
            **{alan: _sayi(ham.get(alan), alan) for alan in HEDEF_ALANLARI},
        }
        degisiklik = cls(islem=islem, **degerler)
        degisiklik._gerekenleri_denetle()
        return degisiklik

    def _gerekenleri_denetle(self) -> None:
        """İşlem için gereken alanların verildiğini denetler."""
        gerekenler = {
            DegisiklikTuru.PARCA_EKLE: ("parca_kimlik",),
            DegisiklikTuru.PARCA_DEGISTIR: ("bag_kimlik", "parca_kimlik"),
            DegisiklikTuru.ADET_DEGISTIR: ("bag_kimlik", "adet"),
            DegisiklikTuru.PARCA_CIKAR: ("bag_kimlik",),
            DegisiklikTuru.HEDEF_DEGISTIR: (),
        }[self.islem]
        eksik = [alan for alan in gerekenler if getattr(self, alan) is None]
        if eksik:
            raise GecersizDegerHatasi(f"{self.islem.value} için şu alanlar gerekli: {', '.join(eksik)}.")
        if self.islem is DegisiklikTuru.HEDEF_DEGISTIR and all(getattr(self, a) is None for a in HEDEF_ALANLARI):
            raise GecersizDegerHatasi("hedef_degistir için en az bir hedef (ucus_suresi_dk, yuk_g, butce_tl, itki_agirlik) verin.")
        if self.adet is not None and not 1 <= self.adet <= EN_FAZLA_ADET:
            raise GecersizDegerHatasi(f"Adet 1 ile {EN_FAZLA_ADET} arasında olmalı.")

    def sozluk(self) -> dict[str, Any]:
        """Saklamak için sözlük (yalnızca verilmiş alanlar)."""
        sozluk: dict[str, Any] = {"islem": self.islem.value}
        for alan in ("parca_kimlik", "bag_kimlik", "adet", *HEDEF_ALANLARI):
            if getattr(self, alan) is not None:
                sozluk[alan] = getattr(self, alan)
        return sozluk


def _tamsayi(deger: Any, ad: str) -> int | None:
    if deger is None:
        return None
    if isinstance(deger, float) and deger.is_integer():
        deger = int(deger)
    if isinstance(deger, bool) or not isinstance(deger, int):
        raise GecersizDegerHatasi(f"{ad} bir tam sayı olmalı (girilen: {deger!r}).")
    return deger


def _sayi(deger: Any, ad: str) -> float | None:
    if deger is None:
        return None
    if not gecerli_sayi_mi(deger):
        raise GecersizDegerHatasi(f"{ad} geçerli bir sayı olmalı (girilen: {deger!r}).")
    return float(deger)


def degisiklikleri_coz(ham: Any) -> list[Degisiklik]:
    """
    Değişiklik listesini çözer.

    Hatalar:
        GecersizDegerHatasi: Liste değilse, boşsa, çok uzunsa veya bir öğe geçersizse.
    """
    if not isinstance(ham, list) or not ham:
        raise GecersizDegerHatasi("En az bir değişiklik içeren bir liste verin.")
    if len(ham) > EN_FAZLA_DEGISIKLIK:
        raise GecersizDegerHatasi(f"Bir öneride en çok {EN_FAZLA_DEGISIKLIK} değişiklik olabilir.")
    return [Degisiklik.sozlukten(oge) for oge in ham]


@dataclass
class _Satir:
    """Senaryodaki bir parça satırı; bag_kimlik None ise senaryoda eklenmiş satırdır."""

    bag_kimlik: int | None
    parca: Parca
    adet: int


@dataclass
class SenaryoSonucu:
    """
    Alanlar:
        aciklamalar: Her değişikliğin Türkçe açıklaması (ör. "T-Motor F60 ×4 → ×6").
        once / sonra: Tasarımın özet değerleri (bkz. tasarim_ozeti).
        uyum_degisimleri: Sonucu değişen uyum kontrolleri.
    """

    aciklamalar: list[str]
    once: dict[str, Any]
    sonra: dict[str, Any]
    uyum_degisimleri: list[dict[str, Any]] = field(default_factory=list)

    def sozluk(self) -> dict[str, Any]:
        """JSON'a uygun sözlük (araç sonucu ve öneri kartı için)."""
        return {
            "aciklamalar": self.aciklamalar, "once": self.once, "sonra": self.sonra,
            "uyum_degisimleri": self.uyum_degisimleri,
        }


def _hesap_degeri(h: HesapDegeri) -> dict[str, Any]:
    return {"deger": h.deger, "tahmini": h.tahmini}


def tasarim_ozeti(sonuc: TasarimSonucu) -> dict[str, Any]:
    """
    Tasarım sonucunun karşılaştırmada kullanılan özet değerleri.

    Dönüş:
        toplam ağırlık, itki/ağırlık, uçuş süresi, asılı kalma gazı, tam gaz akımı,
        uyum durum sayıları ve eksik zorunlu parçalar.
    """
    sayilar = {d.value: 0 for d in UyumDurumu}
    for u in sonuc.uyum:
        sayilar[u.durum.value] += 1
    return {
        "toplam_agirlik_g": {"deger": sonuc.agirlik.toplam_g, "tahmini": sonuc.agirlik.tahmini},
        "itki_agirlik_orani": _hesap_degeri(sonuc.ucus.itki_agirlik_orani),
        "ucus_suresi_dk": _hesap_degeri(sonuc.ucus.ucus_suresi_dk),
        "asili_gaz_yuzde": _hesap_degeri(sonuc.ucus.asili_gaz_yuzde),
        "toplam_maks_akim_a": _hesap_degeri(sonuc.ucus.toplam_maks_akim_a),
        "uyum": sayilar,
        "eksik_zorunlu_parcalar": [z.etiket for z in sonuc.zorunluluklar if z.durum is ZorunlulukDurumu.EKSIK],
    }


class SenaryoHesaplayici:
    """
    Değişikliklerin tasarıma etkisini kaydetmeden hesaplar.

    Parametreler:
        elektronik: Drone, parça ve katalog bilgisini veren ElektronikServisi.
    """

    def __init__(self, elektronik: ElektronikServisi) -> None:
        self._elektronik = elektronik
        self._tasarim = TasarimHesaplayici()

    def hesapla(self, drone_kimlik: int, degisiklikler: list[Degisiklik]) -> SenaryoSonucu:
        """
        Parametreler:
            drone_kimlik: Drone.
            degisiklikler: Sırayla uygulanacak değişiklikler.
        Dönüş:
            SenaryoSonucu.
        Hatalar:
            KayitBulunamadiHatasi: Drone yoksa.
            GecersizDegerHatasi: Bir değişiklik bu drone'a uygulanamıyorsa (açıklamalı).
        """
        ozet = self._elektronik.ozet(drone_kimlik)
        satirlar = [_Satir(bag.kimlik, parca, bag.adet) for bag, parca in ozet.kalemler]
        hedefler = ozet.hedefler
        aciklamalar: list[str] = []
        for sira, degisiklik in enumerate(degisiklikler, start=1):
            try:
                if degisiklik.islem is DegisiklikTuru.HEDEF_DEGISTIR:
                    hedefler, aciklama = self._hedefleri_degistir(hedefler, degisiklik)
                else:
                    aciklama = self._parcalari_degistir(satirlar, degisiklik)
            except (GecersizDegerHatasi, KayitBulunamadiHatasi) as hata:
                raise GecersizDegerHatasi(f"{sira}. değişiklik: {hata.mesaj}") from None
            aciklamalar.append(aciklama)

        once = TasarimSonucu(ozet.zorunluluklar, ozet.agirlik, ozet.uyum, ozet.ucus)
        sonra = self._tasarim.hesapla(ozet.drone, [(s.parca, s.adet) for s in satirlar], ozet.sasi_olculeri, hedefler)
        return SenaryoSonucu(aciklamalar, tasarim_ozeti(once), tasarim_ozeti(sonra), self._uyum_farki(once, sonra))

    def _parcalari_degistir(self, satirlar: list[_Satir], d: Degisiklik) -> str:
        """Parça değişikliğini bellekteki listeye uygular; açıklamasını döndürür."""
        if d.islem is DegisiklikTuru.PARCA_EKLE:
            parca = self._katalog_parcasi(d.parca_kimlik, satirlar)
            satirlar.append(_Satir(None, parca, d.adet or 1))
            return f"Ekle: {parca.gorunen_ad} ×{d.adet or 1}"
        satir = self._satir(satirlar, d.bag_kimlik)
        if d.islem is DegisiklikTuru.PARCA_DEGISTIR:
            yeni = self._katalog_parcasi(d.parca_kimlik, [s for s in satirlar if s is not satir])
            adet = d.adet or satir.adet
            # Değiştirilen satır senaryoda yeni satır sayılır; aynı öneride tekrar kullanılamaz.
            satirlar[satirlar.index(satir)] = _Satir(None, yeni, adet)
            return f"Değiştir: {satir.parca.gorunen_ad} ×{satir.adet} → {yeni.gorunen_ad} ×{adet}"
        if d.islem is DegisiklikTuru.ADET_DEGISTIR:
            eski = satir.adet
            satir.adet = d.adet
            return f"Adet: {satir.parca.gorunen_ad} ×{eski} → ×{d.adet}"
        satirlar.remove(satir)
        return f"Çıkar: {satir.parca.gorunen_ad} ×{satir.adet}"

    def _katalog_parcasi(self, parca_kimlik: int | None, satirlar: list[_Satir]) -> Parca:
        """Katalogdaki parçayı getirir; drone'da zaten varsa hata verir (adet değiştirilmeli)."""
        parca = self._elektronik.parca_getir(parca_kimlik)
        if any(s.parca.kimlik == parca.kimlik for s in satirlar):
            raise GecersizDegerHatasi(
                f"{parca.gorunen_ad} bu drone'da zaten var; eklemek yerine adet_degistir kullanın."
            )
        return parca

    @staticmethod
    def _satir(satirlar: list[_Satir], bag_kimlik: int | None) -> _Satir:
        """Drone'daki parça satırını bulur."""
        for satir in satirlar:
            if satir.bag_kimlik is not None and satir.bag_kimlik == bag_kimlik:
                return satir
        raise GecersizDegerHatasi(
            f"Drone'da {bag_kimlik} numaralı parça satırı yok (ya da bu öneride zaten değiştirildi). "
            "Satır numaraları için parca_listesi_getir kullanın."
        )

    @staticmethod
    def _hedefleri_degistir(hedefler: DroneHedefleri, d: Degisiklik) -> tuple[DroneHedefleri, str]:
        """Hedefleri değiştirir (verilmeyen aynı kalır); yeni hedefleri ve açıklamayı döndürür."""
        degerler = {alan: getattr(d, alan) for alan in HEDEF_ALANLARI if getattr(d, alan) is not None}
        yeni = replace(hedefler, **degerler)  # DroneHedefleri değerleri kendi denetler
        aciklama = ", ".join(f"{alan} → {sayi_yaz(deger)}" for alan, deger in degerler.items())
        return yeni, f"Hedef: {aciklama}"

    @staticmethod
    def _uyum_farki(once: TasarimSonucu, sonra: TasarimSonucu) -> list[dict[str, Any]]:
        """Sonucu değişen uyum kontrolleri."""
        onceki = {u.kod: u for u in once.uyum}
        farklar = []
        for u in sonra.uyum:
            eski = onceki.get(u.kod)
            if eski is None or eski.durum is not u.durum:
                farklar.append({
                    "kod": u.kod, "baslik": u.baslik,
                    "once": eski.durum.value if eski else None, "sonra": u.durum.value, "aciklama": u.aciklama,
                })
        return farklar
