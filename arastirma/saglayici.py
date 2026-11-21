"""
Yapay zeka sağlayıcılarının ortak arayüzü.

Program yalnızca bu arayüzü bilir; Gemini dışında bir sağlayıcı eklemek için
yeni bir alt sınıf yazmak yeterlidir. Testlerde gerçek istek yerine sahte bir
alt sınıf kullanılır.
"""

from abc import ABC, abstractmethod
from typing import Any


class ArastirmaSaglayicisi(ABC):
    """Yapay zekadan şemaya uyan JSON yanıtı alan sağlayıcı."""

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
