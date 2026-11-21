"""
Yapay zeka sağlayıcılarının ortak arayüzü.

Program yalnızca bu arayüzü bilir; Gemini dışında bir sağlayıcı eklemek için
yeni bir alt sınıf yazmak yeterlidir. Testlerde gerçek istek yerine sahte bir
alt sınıf kullanılır.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from http import HTTPStatus
from typing import Any

from arastirma.sohbet import ARAC_SERBEST, AracTanimi, SohbetOlayi
from cekirdek.hatalar import YapayZekaHatasi


class ArastirmaSaglayicisi(ABC):
    """Yapay zekadan şemaya uyan JSON yanıtı alan (ve destekliyorsa sohbet eden) sağlayıcı."""

    def sohbet_et(
        self,
        sistem_talimati: str,
        girdiler: list[dict[str, Any]],
        araclar: list[AracTanimi],
        akis: bool = True,
        arac_kullanimi: str = ARAC_SERBEST,
    ) -> Iterator[SohbetOlayi]:
        """
        Sohbetin bir turunu çalıştırır; metin parçalarını, araç çağrılarını ve tur sonunu olay olarak üretir.

        Parametreler:
            sistem_talimati: Modelin rolü, kuralları ve bağlam.
            girdiler: Tüm geçmiş (arastirma/sohbet.py yardımcılarıyla oluşturulmuş öğeler).
            araclar: Modelin çağırabileceği araçlar.
            akis: True ise yanıt parça parça gelir; False ise tek seferde.
            arac_kullanimi: ARAC_SERBEST veya ARAC_YASAK (yalnızca metin yanıtı).
        Dönüş:
            SohbetOlayi akışı; en sonda tek bir OLAY_BITTI.
        Hatalar:
            YapayZekaHatasi: İstek yapılamazsa veya sağlayıcı sohbeti desteklemiyorsa.
        """
        raise YapayZekaHatasi("Bu yapay zeka sağlayıcısı sohbeti desteklemiyor.", HTTPStatus.NOT_IMPLEMENTED)

    @abstractmethod
    def json_uret(self, sistem_talimati: str, istem: str, sema: dict[str, Any]) -> dict[str, Any]:
        """
        Modelden verilen JSON şemasına uyan bir yanıt ister.

        Parametreler:
            sistem_talimati: Modelin rolünü ve kurallarını anlatan metin.
            istem: Asıl istek metni.
            sema: Yanıtın JSON şeması.
        Dönüş:
            Yanıtın sözlük hali (şemaya uyduğu yine de ayrıca denetlenmelidir).
        Hatalar:
            YapayZekaHatasi: İstek yapılamazsa veya yanıt JSON değilse.
        """
