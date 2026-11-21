"""
Yapay zeka sohbetinin ortak veri türleri: araç tanımı, araç çağrısı ve akış olayları.

Sohbet geçmişi Gemini Interactions API'nin "adım" (step) biçiminde tutulur. Geçmiş
store=false ile her turda yeniden gönderildiği için modelin ürettiği adımlar (düşünce
imzaları dahil) DEĞİŞTİRİLMEDEN geri verilmelidir; bu yüzden geçmiş öğeleri sözlük olarak
taşınır ve yalnızca aşağıdaki yardımcılarla oluşturulur.
"""

from dataclasses import dataclass, field
import json
from typing import Any, Final

# Akış olaylarının türleri.
OLAY_METIN: Final[str] = "metin"
OLAY_ARAC_CAGRISI: Final[str] = "arac_cagrisi"
OLAY_BITTI: Final[str] = "bitti"

# Modelin araç kullanma serbestliği (Interactions API "tool_choice").
ARAC_SERBEST: Final[str] = "auto"
ARAC_YASAK: Final[str] = "none"

# Interactions API girdi/adım türleri.
KULLANICI_GIRDISI: Final[str] = "user_input"
MODEL_CIKTISI: Final[str] = "model_output"
ARAC_SONUCU: Final[str] = "function_result"
ARAC_CAGRISI: Final[str] = "function_call"
METIN_BLOGU: Final[str] = "text"


@dataclass(frozen=True)
class AracTanimi:
    """
    Modelin çağırabileceği bir araç (fonksiyon).

    Alanlar:
        ad: Aracın adı (ör. "proje_ozeti_getir").
        aciklama: Modele aracın ne işe yaradığını anlatan metin.
        parametreler: Parametrelerin JSON şeması (nesne).
    """

    ad: str
    aciklama: str
    parametreler: dict[str, Any] = field(default_factory=lambda: {"type": "object", "properties": {}})


@dataclass(frozen=True)
class AracCagrisi:
    """
    Modelin istediği araç çağrısı.

    Alanlar:
        kimlik: Çağrının kimliği (sonuç bu kimlikle geri verilir).
        ad: Aracın adı.
        argumanlar: Modelin verdiği argümanlar.
    """

    kimlik: str
    ad: str
    argumanlar: dict[str, Any]


@dataclass
class SohbetOlayi:
    """
    Model yanıtı akarken üretilen olay.

    Alanlar:
        tur: OLAY_METIN, OLAY_ARAC_CAGRISI veya OLAY_BITTI.
        metin: Gelen metin parçası (OLAY_METIN).
        cagri: Araç çağrısı (OLAY_ARAC_CAGRISI).
        adimlar: Modelin bu turdaki adımları, geçmişe olduğu gibi eklenecek (OLAY_BITTI).
        durum: Tur sonu durumu: "completed" veya araç bekleniyorsa "requires_action" (OLAY_BITTI).
        kullanim: Token kullanımı (sağlayıcı verdiyse, OLAY_BITTI).
        model: Yanıtı veren model (OLAY_BITTI; istemci doldurur).
        bugun_kullanilan / gunluk_sinir: Günlük kullanım (OLAY_BITTI; istemci doldurur).
    """

    tur: str
    metin: str = ""
    cagri: AracCagrisi | None = None
    adimlar: list[dict[str, Any]] = field(default_factory=list)
    durum: str = ""
    kullanim: dict[str, Any] | None = None
    model: str = ""
    bugun_kullanilan: int = 0
    gunluk_sinir: int = 0


def kullanici_girdisi(metin: str) -> dict[str, Any]:
    """Kullanıcının mesajını geçmiş öğesine çevirir."""
    return {"type": KULLANICI_GIRDISI, "content": [{"type": METIN_BLOGU, "text": metin}]}


def model_ciktisi(metin: str) -> dict[str, Any]:
    """Önceki bir asistan yanıtını (kayıttan okunan) geçmiş öğesine çevirir."""
    return {"type": MODEL_CIKTISI, "content": [{"type": METIN_BLOGU, "text": metin}]}


def arac_sonucu(cagri: AracCagrisi, sonuc: Any, hata_mi: bool = False) -> dict[str, Any]:
    """
    Araç sonucunu modele geri verilecek geçmiş öğesine çevirir.

    Parametreler:
        cagri: Yanıtlanan çağrı.
        sonuc: JSON'a çevrilebilir sonuç.
        hata_mi: Araç hata verdiyse True (model düzeltip yeniden deneyebilsin).
    """
    oge: dict[str, Any] = {
        "type": ARAC_SONUCU,
        "name": cagri.ad,
        "call_id": cagri.kimlik,
        "result": [{"type": METIN_BLOGU, "text": json.dumps(sonuc, ensure_ascii=False)}],
    }
    if hata_mi:
        oge["is_error"] = True
    return oge
