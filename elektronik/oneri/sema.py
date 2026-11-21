"""
Öneri yanıtının JSON şeması.

Teknik alanlar parça sınıfının alan tanımlarından (formla aynı kaynak) üretilir;
böylece parça sınıfına yeni alan eklenince şema da kendiliğinden güncellenir.
Teknik alanların hiçbiri zorunlu değildir: model emin olmadığı değeri yazmaz.
"""

from typing import Any, Final

from elektronik.parcalar.alan_tanimlari import SECIM, alan_tanimlari
from elektronik.parcalar.denetim import AlanCinsi
from elektronik.parcalar.parca import Parca

# alan_tanimlari'ndaki "cins" -> JSON şeması türü.
CINS_SEMALARI: Final[dict[str, dict[str, Any]]] = {
    AlanCinsi.TAMSAYI: {"type": "integer"},
    AlanCinsi.SAYI: {"type": "number"},
    AlanCinsi.METIN: {"type": "string"},
    AlanCinsi.MANTIKSAL: {"type": "boolean"},
    AlanCinsi.METIN_LISTESI: {"type": "array", "items": {"type": "string"}},
    AlanCinsi.SAYI_LISTESI: {"type": "array", "items": {"type": "number"}},
}


class OneriSemasiOlusturucu:
    """Bir parça türü için aday listesi şemasını oluşturur."""

    @staticmethod
    def teknik_sema(sinif: type[Parca]) -> dict[str, Any]:
        """Parça sınıfının teknik alanlarının şeması (hepsi isteğe bağlı)."""
        ozellikler: dict[str, Any] = {}
        for alan in alan_tanimlari(sinif):
            if alan["cins"] == SECIM:
                sema: dict[str, Any] = {"type": "string", "enum": [s["deger"] for s in alan["secenekler"]]}
            else:
                sema = dict(CINS_SEMALARI[alan["cins"]])
            sema["description"] = alan["etiket"]
            ozellikler[alan["ad"]] = sema
        return {"type": "object", "properties": ozellikler}

    def olustur(self, sinif: type[Parca]) -> dict[str, Any]:
        """
        Yanıt şeması: {"adaylar": [{uretici, model, agirlik_g?, gerekce, teknik{...}}]}.

        Parametreler:
            sinif: Önerilecek parçanın sınıfı.
        Dönüş:
            JSON şeması (sözlük).
        """
        aday = {
            "type": "object",
            "properties": {
                "uretici": {"type": "string", "description": "Marka"},
                "model": {"type": "string", "description": "Tam model adı (satıştaki adıyla)"},
                "agirlik_g": {"type": "number", "description": "Bir adetin ağırlığı, gram; emin değilsen yazma"},
                "gerekce": {"type": "string", "description": "Türkçe, 1-3 cümle: neden bu drone'a uygun"},
                "teknik": self.teknik_sema(sinif),
            },
            "required": ["uretici", "model", "gerekce"],
        }
        return {"type": "object", "properties": {"adaylar": {"type": "array", "items": aday}}, "required": ["adaylar"]}
