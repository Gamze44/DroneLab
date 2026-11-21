"""
API uçlarında ortak kullanılan parametre türleri.

SQLite tam sayıları 64 bitliktir. Python 2**63'ten büyük bir sayıyı sorunsuz kabul eder
ama veritabanına sorulurken OverflowError verir ve kullanıcı "beklenmeyen hata" (500)
görürdü. Sınırlar FastAPI'ye bildirildiği için böyle istekler 422 ile reddedilir.
"""

from typing import Annotated, Final

from fastapi import Path as YolParametresi
from fastapi import Query as SorguParametresi
from pydantic import Field

EN_KUCUK_KIMLIK: Final[int] = 1
# SQLite'ın saklayabildiği en büyük tam sayı.
EN_BUYUK_KIMLIK: Final[int] = 2**63 - 1

# Adresin içindeki kimlik (ör. /api/dronelar/{kimlik}).
Kimlik = Annotated[int, YolParametresi(ge=EN_KUCUK_KIMLIK, le=EN_BUYUK_KIMLIK)]
# İstek gövdesindeki veya formdaki kimlik alanı.
GovdeKimligi = Annotated[int, Field(ge=EN_KUCUK_KIMLIK, le=EN_BUYUK_KIMLIK)]
# Adresin sorgu kısmındaki isteğe bağlı kimlik (ör. ?drone_kimlik=3).
SorguKimligi = Annotated[int | None, SorguParametresi(ge=EN_KUCUK_KIMLIK, le=EN_BUYUK_KIMLIK)]
