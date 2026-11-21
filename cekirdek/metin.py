"""
Metin karşılaştırma yardımcısı.

Parça adları, protokol ve konnektör adları farklı yazımlarla girilebilir ("T-Motor" /
"tmotor", "DShot-600" / "dshot600", "İnce" / "ince"). Karşılaştırmadan önce hepsi aynı
kurala göre sadeleştirilir; kural tek yerde durur ki iki yerde farklı davranmasın.
"""

import re
from typing import Final
import unicodedata

# Sadeleştirilmiş metinde yalnızca küçük harf ve rakam kalır.
ALFANUMERIK_OLMAYAN: Final[re.Pattern[str]] = re.compile(r"[^a-z0-9]")


def metni_sadelestir(metin: str) -> str:
    """
    Metni karşılaştırma için sadeleştirir: aksanlar/Türkçe harfler sadeleşir,
    küçük harfe çevrilir, harf ve rakam dışındakiler atılır.

    Parametreler:
        metin: ör. "T-Motor F60 Pro V İnce"
    Dönüş:
        ör. "tmotorf60province"
    """
    # NFKD, "ç" gibi harfleri "c" + işaret olarak ayırır; işaretler sonra atılır.
    ayrik = unicodedata.normalize("NFKD", metin.replace("ı", "i").replace("İ", "I"))
    sade = "".join(h for h in ayrik if not unicodedata.combining(h)).lower()
    return ALFANUMERIK_OLMAYAN.sub("", sade)
