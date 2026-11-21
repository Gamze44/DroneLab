"""
Şartname metninden ölçülebilir maddelerin Gemini ile çıkarılması.

Model yalnızca TASLAK üretir: her madde programın Madde doğrulayıcısından geçer,
geçemeyen madde atlanır ve sayılır. Çıkarılan maddelerin hepsi "onaylanmadı"
olarak kaydedilir; kullanıcı tabloda kontrol edip onaylar (plan: onay zorunlu).
"""

from dataclasses import dataclass, field
from typing import Any, Final

from cekirdek.hatalar import GecersizDegerHatasi
from sartname.modeller import BUYUKLUK_TANIMLARI, Buyukluk, Madde, MaddeSinifi, SinirTuru

# DEĞİŞTİRİLEBİLİR: Modele gönderilecek en uzun metin (karakter). Gemini Flash'ın bağlamı
# çok daha büyüktür; sınır, yanlışlıkla yüklenen dev belgelerin kotayı tüketmemesi içindir.
EN_UZUN_GONDERILEN_METIN: Final[int] = 300_000
# DEĞİŞTİRİLEBİLİR: Bir şartnameden en çok kaç madde alınır.
EN_FAZLA_MADDE: Final[int] = 80

SISTEM_TALIMATI: Final[str] = (
    "Sen bir drone yarışması şartnamesini okuyan dikkatli bir teknik asistansın. Görevin, metindeki "
    "drone tasarımını sınırlayan ÖLÇÜLEBİLİR maddeleri çıkarmak.\n"
    "Kurallar:\n"
    "1. Yalnızca metinde gerçekten yazan sınırları al; tahmin etme, yorum ekleme.\n"
    "2. Değerleri şu birimlere çevir: ağırlık gram (2 kg → 2000), uzunluk mm (25 cm → 250), süre dakika, "
    "pervane inç, pil kapasitesi mAh, para TL.\n"
    "3. Her maddenin şartnamedeki madde numarasını ve '[Sayfa N]' işaretlerinden sayfasını yaz; yoksa boş bırak.\n"
    "4. 'aciklama' alanına maddenin şartnamedeki kısa ifadesini (en çok 2 cümle) yaz.\n"
    "5. Uyulmazsa diskalifiye/kabul edilmeme getiren madde 'kesin'; uzadıkça/azaldıkça puan veren madde 'puanlanan'dır.\n"
    "6. GPS, kamera, video verici, telemetri zorunluysa ilgili büyüklüğü 'zorunlu' sınırıyla ver.\n"
    "7. Failsafe, acil durdurma, irtifa, hız, malzeme gibi listede olmayan ama tasarımı sınırlayan maddeleri "
    "'diger' büyüklüğüyle ver (değer gerekmez).\n"
    "8. Takım, başvuru, takvim, rapor gibi tasarımla ilgisiz maddeleri ALMA.\n"
    "Yalnızca istenen JSON şemasında yanıt ver."
)


def _buyukluk_listesi() -> str:
    return "; ".join(
        f"{b.value} = {t.ad}" + (f" ({t.birim})" if t.birim else "") for b, t in BUYUKLUK_TANIMLARI.items()
    )


def madde_semasi() -> dict[str, Any]:
    """Modelin döndüreceği JSON şeması."""
    madde = {
        "type": "object",
        "properties": {
            "madde_no": {"type": "string", "description": "Şartnamedeki madde numarası, ör. 4.2"},
            "sayfa": {"type": "integer", "description": "Sayfa numarası"},
            "aciklama": {"type": "string", "description": "Maddenin kısa ifadesi"},
            "buyukluk": {"type": "string", "enum": [b.value for b in Buyukluk]},
            "sinir_turu": {"type": "string", "enum": [s.value for s in SinirTuru]},
            "deger": {"type": "number", "description": "Sınır değeri, istenen birimde"},
            "sinif": {"type": "string", "enum": [s.value for s in MaddeSinifi]},
        },
        "required": ["aciklama", "buyukluk", "sinir_turu", "sinif"],
    }
    return {"type": "object", "properties": {"maddeler": {"type": "array", "items": madde}}, "required": ["maddeler"]}


def istem_olustur(metin: str) -> str:
    """Modele gönderilecek istem; çok uzun metin kısaltılır ve bu söylenir."""
    kesildi = len(metin) > EN_UZUN_GONDERILEN_METIN
    return (
        f"Büyüklük seçenekleri: {_buyukluk_listesi()}.\n\n"
        + ("NOT: Belge çok uzun olduğu için yalnızca baş kısmı gönderildi.\n\n" if kesildi else "")
        + "ŞARTNAME METNİ:\n<<<\n"
        + metin[:EN_UZUN_GONDERILEN_METIN]
        + "\n>>>"
    )


@dataclass
class CikarimSonucu:
    """
    Alanlar:
        maddeler: Doğrulayıcıdan geçen maddeler (hepsi onaylanmamış).
        atlanan: Geçersiz olduğu için alınmayan madde sayısı.
    """

    maddeler: list[Madde] = field(default_factory=list)
    atlanan: int = 0


class MaddeDonusturucu:
    """Modelin ham madde listesini doğrulanmış Madde nesnelerine çevirir."""

    def donustur(self, ham_liste: Any) -> CikarimSonucu:
        """
        Parametreler:
            ham_liste: Modelden gelen "maddeler" listesi.
        Dönüş:
            CikarimSonucu.
        """
        sonuc = CikarimSonucu()
        if not isinstance(ham_liste, list):
            return sonuc
        for ham in ham_liste[:EN_FAZLA_MADDE]:
            madde = self._tek(ham)
            if madde is None:
                sonuc.atlanan += 1
            else:
                sonuc.maddeler.append(madde)
        sonuc.atlanan += max(0, len(ham_liste) - EN_FAZLA_MADDE)
        return sonuc

    @staticmethod
    def _tek(ham: Any) -> Madde | None:
        if not isinstance(ham, dict):
            return None
        sayfa = ham.get("sayfa")
        if isinstance(sayfa, float) and sayfa.is_integer():
            sayfa = int(sayfa)
        if not (isinstance(sayfa, int) and not isinstance(sayfa, bool) and sayfa >= 1):
            sayfa = None  # geçersiz sayfa maddeyi düşürmesin
        madde_no = ham.get("madde_no")
        try:
            return Madde(
                aciklama=ham.get("aciklama") if isinstance(ham.get("aciklama"), str) else "",
                buyukluk=ham.get("buyukluk"),
                sinir_turu=ham.get("sinir_turu"),
                deger=ham.get("deger"),
                sinif=ham.get("sinif") or MaddeSinifi.KESIN,
                madde_no=madde_no if isinstance(madde_no, (str, int, float)) and not isinstance(madde_no, bool) else None,
                sayfa=sayfa,
                onaylandi=False,
            )
        except GecersizDegerHatasi:
            return None
