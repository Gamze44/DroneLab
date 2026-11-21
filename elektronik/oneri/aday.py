"""
Modelden gelen ham aday sözlüğünü programın parça nesnesine çevirir.

Modelin yanıtına güvenilmez: her alan türüne göre denetlenir, sonra parça
sınıfının kendi doğrulayıcısından tek tek geçirilir. Geçersiz veya akla yatkın
olmayan bir değer bütün adayı düşürmez; yalnızca o alan silinir ve listelenir.
Üretici veya model adı yoksa aday tamamen atlanır.
"""

from dataclasses import dataclass, field
import math
from typing import Any, Final

from cekirdek.hatalar import GecersizDegerHatasi
from elektronik.parcalar.alan_tanimlari import alan_tanimlari
from elektronik.parcalar.kayit import parca_sinifi
from elektronik.parcalar.parca import Parca
from elektronik.parcalar.serilestirme import ParcaSerilestirici
from elektronik.parcalar.turler import DigerAltTur, ParcaTuru, alan_etiketi

# DEĞİŞTİRİLEBİLİR: Metin alanlarının en çok uzunluğu (modelin uzun metin döndürmesine karşı).
EN_UZUN_AD: Final[int] = 120
EN_UZUN_GEREKCE: Final[int] = 600
ONERI_NOTU: Final[str] = "Gemini önerisi (internette aranmadı); değerler doğrulanmadı."


@dataclass
class DonusturulenAday:
    """
    Alanlar:
        parca: Doğrulanmış parça nesnesi (dogrulandi=False, kaydedilmemiş).
        gerekce: Modelin Türkçe gerekçesi.
        silinen_alanlar: Geçersiz olduğu için silinen alanların etiketleri.
    """

    parca: Parca
    gerekce: str
    silinen_alanlar: list[str] = field(default_factory=list)


def _sayi_mi(deger: Any) -> bool:
    return isinstance(deger, (int, float)) and not isinstance(deger, bool) and math.isfinite(deger)


def _ture_uydur(cins: str, deger: Any, secenekler: set[str]) -> tuple[bool, Any]:
    """
    Değeri alanın cinsine uydurmaya çalışır.

    Dönüş:
        (uygun mu, uydurulmuş değer). 4.0 gibi tam sayılı ondalık, tam sayıya çevrilir.
    """
    if cins == "tamsayi":
        if _sayi_mi(deger) and float(deger).is_integer():
            return True, int(deger)
        return False, None
    if cins == "sayi":
        return (True, deger) if _sayi_mi(deger) else (False, None)
    if cins == "metin":
        return (True, deger.strip()[:EN_UZUN_AD]) if isinstance(deger, str) and deger.strip() else (False, None)
    if cins == "mantiksal":
        return (True, deger) if isinstance(deger, bool) else (False, None)
    if cins == "metin_listesi":
        if isinstance(deger, list) and deger and all(isinstance(d, str) and d.strip() for d in deger):
            return True, [d.strip()[:EN_UZUN_AD] for d in deger]
        return False, None
    if cins == "sayi_listesi":
        return (True, deger) if isinstance(deger, list) and deger and all(_sayi_mi(d) for d in deger) else (False, None)
    if cins == "secim":
        return (True, deger) if deger in secenekler else (False, None)
    return False, None


class AdayDonusturucu:
    """Ham aday sözlüğünü doğrulanmış parçaya çevirir."""

    def donustur(self, tur: ParcaTuru, alt_tur: DigerAltTur | None, ham: Any) -> DonusturulenAday | None:
        """
        Parametreler:
            tur, alt_tur: İstenen parça türü (modelin söylediği tür kullanılmaz).
            ham: Modelden gelen aday sözlüğü.
        Dönüş:
            DonusturulenAday; üretici/model yoksa None.
        """
        if not isinstance(ham, dict):
            return None
        uretici, model = ham.get("uretici"), ham.get("model")
        if not (isinstance(uretici, str) and uretici.strip() and isinstance(model, str) and model.strip()):
            return None
        silinen: list[str] = []
        agirlik = ham.get("agirlik_g")
        if agirlik is not None and not (_sayi_mi(agirlik) and agirlik > 0):
            silinen.append(alan_etiketi("agirlik_g"))
            agirlik = None
        gerekce = ham.get("gerekce") if isinstance(ham.get("gerekce"), str) else ""
        gerekce = gerekce.strip()[:EN_UZUN_GEREKCE]
        ortak = {
            "uretici": uretici.strip()[:EN_UZUN_AD],
            "model": model.strip()[:EN_UZUN_AD],
            "agirlik_g": agirlik,
            "dogrulandi": False,
            "notlar": f"{ONERI_NOTU} Gerekçe: {gerekce}" if gerekce else ONERI_NOTU,
        }
        sinif = parca_sinifi(tur)
        temel: dict[str, Any] = {"alt_tur": alt_tur.value} if tur is ParcaTuru.DIGER and alt_tur else {}
        try:
            ParcaSerilestirici.sozlukten_olustur(tur, ortak, temel)
        except GecersizDegerHatasi:
            return None  # ör. alt tür eksik: istem hatası, aday kullanılamaz

        ham_teknik = ham.get("teknik") if isinstance(ham.get("teknik"), dict) else {}
        teknik = dict(temel)
        for alan in alan_tanimlari(sinif):
            ad = alan["ad"]
            if ham_teknik.get(ad) is None:
                continue
            secenekler = {s["deger"] for s in alan.get("secenekler", [])}
            uygun, deger = _ture_uydur(alan["cins"], ham_teknik[ad], secenekler)
            if uygun:
                # Değeri ekleyip parça doğrulayıcısından geçir; aralık dışı/çelişkili değer (ör. en az > en çok) silinir.
                deneme = {**teknik, ad: deger}
                try:
                    ParcaSerilestirici.sozlukten_olustur(tur, ortak, deneme)
                    teknik = deneme
                    continue
                except GecersizDegerHatasi:
                    pass
            silinen.append(alan["etiket"])
        parca = ParcaSerilestirici.sozlukten_olustur(tur, ortak, teknik)
        return DonusturulenAday(parca=parca, gerekce=gerekce, silinen_alanlar=silinen)
