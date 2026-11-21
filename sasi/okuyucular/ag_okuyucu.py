"""
Üçgen ağ (mesh) tabanlı 3B dosyaların okuyucusu: STL, OBJ, 3MF.

trimesh ile okunur. STL ve OBJ birim bilgisi taşımaz; 3MF taşır.
Hacim yalnızca model kapalı (su geçirmez) ise güvenilirdir, bu yüzden
kapalı olmayan modeller için uyarı üretilir.
"""

import logging
from pathlib import Path
from typing import Final

import numpy as np
import trimesh
from trimesh.resolvers import Resolver

from cekirdek.arsiv_denetimi import ArsivDenetleyici
from cekirdek.birimler import BIRIM_CM, BIRIM_INC, BIRIM_M, BIRIM_MM
from cekirdek.hatalar import DosyaOkumaHatasi
from sasi.modeller import GeometriTuru, SasiGeometrisi
from sasi.okuyucular.temel import SasiOkuyucu

# Zip arşivi olan biçimler; açılmadan önce zip bombasına karşı denetlenir.
ARSIV_UZANTILARI: Final[frozenset[str]] = frozenset({".3mf"})

gunluk = logging.getLogger(__name__)

# trimesh'in döndürdüğü birim adları -> programın birim adları.
# Listede olmayan birimler (ör. mikron) "birim yok" sayılır ve kullanıcıya sorulur.
TRIMESH_BIRIMLERI: Final[dict[str, str]] = {
    "mm": BIRIM_MM,
    "millimeter": BIRIM_MM,
    "millimeters": BIRIM_MM,
    "cm": BIRIM_CM,
    "centimeter": BIRIM_CM,
    "centimeters": BIRIM_CM,
    "m": BIRIM_M,
    "meter": BIRIM_M,
    "meters": BIRIM_M,
    "in": BIRIM_INC,
    "inch": BIRIM_INC,
    "inches": BIRIM_INC,
}

# trimesh'in gövde sayımı varsayılan olarak scipy ister; scipy büyük bir bağımlılık
# olduğu için zaten kurulu olan networkx kullanılır.
GRAF_MOTORU: Final[str] = "networkx"


class DisDosyaEngelleyici(Resolver):
    """
    trimesh'in, okunan dosyanın başvurduğu başka dosyaları açmasını engeller.

    Neden: OBJ dosyası "mtllib \\\\sunucu\\paylasim\\a.mtl" gibi bir ağ yolu içerebilir.
    Windows böyle bir yolu açmaya çalışırken kullanıcının oturum bilgisini (NTLM özeti)
    o sunucuya gönderir; yani kötü amaçlı bir OBJ dosyasını yüklemek parolanın
    sızmasına yol açabilir. Şasi hesabı için malzeme (.mtl) ve doku resimleri gerekmediği
    için hiçbir dış dosya açılmaz; trimesh bu durumda modeli malzemesiz okur.
    """

    def __init__(self) -> None:
        # Temel sınıfın __init__'i bilerek hata fırlatır; burada kurulacak bir şey yok.
        pass

    def get(self, key: str) -> bytes:
        """Her dış dosya isteğini "bulunamadı" olarak yanıtlar (dosya sistemine dokunmaz)."""
        raise FileNotFoundError(f"Dış dosya açılmaz: {key}")

    def write(self, name: str, data: bytes) -> None:
        """Okuma sırasında dosya yazılmaz."""
        raise PermissionError("Dış dosya yazılmaz.")

    def namespaced(self, namespace: str) -> "DisDosyaEngelleyici":
        """Alt klasör istense de aynı engelleyici döner."""
        return self

    def keys(self) -> list[str]:
        """Erişilebilir dış dosya yok."""
        return []


class AgOkuyucu(SasiOkuyucu):
    """STL, OBJ ve 3MF dosyalarını okur."""

    UZANTILAR = (".stl", ".obj", ".3mf")

    def __init__(self) -> None:
        self._arsiv = ArsivDenetleyici()

    def oku(self, yol: Path) -> SasiGeometrisi:
        """
        Ağ dosyasını okur, ölçüleri, hacmi ve kalite uyarılarını çıkarır.

        Parametreler:
            yol: .stl, .obj veya .3mf dosyasının yolu.
        Dönüş:
            Tür KATI olan SasiGeometrisi (ölçüler dosya biriminde).
        Hatalar:
            DosyaOkumaHatasi: Dosya bozuksa veya içinde üçgen yoksa.
        """
        if yol.suffix.lower() in ARSIV_UZANTILARI:
            self._arsiv.denetle(yol)
        sahne = self._sahneyi_yukle(yol)
        if len(sahne.geometry) == 0:
            raise DosyaOkumaHatasi(f"'{yol.name}' dosyasında 3B geometri bulunamadı. Dosya boş olabilir.")

        # 3MF gibi formatlarda parçalar konum dönüşümleriyle gelir; to_mesh bunları
        # uygulayarak tek bir ağ verir, böylece ölçüler montajdaki gibi olur.
        ag = sahne.to_mesh()
        if len(ag.faces) == 0:
            raise DosyaOkumaHatasi(f"'{yol.name}' dosyasında üçgen bulunamadı. Dosya boş olabilir.")

        uyarilar: list[str] = []
        dosya_birimi = self._birimi_coz(sahne.units, uyarilar)

        kapali_mi = bool(ag.is_watertight)
        isaretli_hacim = float(ag.volume)
        if not kapali_mi:
            uyarilar.append(
                "Model kapalı (su geçirmez) değil; hacim ve ağırlık hesabı hatalı olabilir. "
                "Modeli CAD programında veya dilimleyicide onarıp tekrar dışa aktarın."
            )
        elif isaretli_hacim < 0:
            uyarilar.append("Modelin yüzey yönleri ters görünüyor; hacim mutlak değer alınarak hesaplandı.")

        govde_sayisi = self._govde_say(ag)
        if govde_sayisi > 1:
            uyarilar.append(
                f"Dosyada birbirine bağlı olmayan {govde_sayisi} ayrı parça var. "
                "Hepsinin şasiye ait olduğundan emin olun."
            )

        olculer = tuple(float(d) for d in ag.extents)
        return SasiGeometrisi(
            dosya_adi=yol.name,
            tur=GeometriTuru.KATI,
            olculer=(olculer[0], olculer[1], olculer[2]),
            dosya_birimi=dosya_birimi,
            hacim=abs(isaretli_hacim),
            ucgen_sayisi=len(ag.faces),
            govde_sayisi=govde_sayisi,
            kapali_mi=kapali_mi,
            uyarilar=uyarilar,
            ag=ag,
        )

    @staticmethod
    def _sahneyi_yukle(yol: Path) -> trimesh.Scene:
        """
        Dosyayı trimesh sahnesi olarak yükler.

        Parametreler:
            yol: Dosya yolu.
        Dönüş:
            trimesh.Scene.
        Hatalar:
            DosyaOkumaHatasi: trimesh dosyayı açamazsa.
        """
        try:
            return trimesh.load_scene(
                yol, file_type=yol.suffix.lower().lstrip("."), resolver=DisDosyaEngelleyici()
            )
        except Exception as hata:
            # trimesh bozuk dosyalarda çok farklı hata türleri fırlatabildiği için
            # hepsi kullanıcıya tek, anlaşılır bir mesajla iletilir. Kütüphanenin ham hata
            # metni (iç yollar içerebilir) kullanıcıya değil günlüğe gider.
            gunluk.warning("3B dosya okunamadı: %s", hata)
            raise DosyaOkumaHatasi(
                f"'{yol.name}' dosyası okunamadı. Dosya bozuk veya beklenen formatta olmayabilir."
            ) from hata

    @staticmethod
    def _birimi_coz(trimesh_birimi: str | None, uyarilar: list[str]) -> str | None:
        """
        trimesh'in birim adını programın birim adına çevirir.

        Parametreler:
            trimesh_birimi: Dosyadan okunan birim adı veya None.
            uyarilar: Tanınmayan birim olursa uyarı eklenecek liste.
        Dönüş:
            "mm", "cm", "m", "inch" veya None.
        """
        if not trimesh_birimi:
            return None
        birim = TRIMESH_BIRIMLERI.get(trimesh_birimi.strip().lower())
        if birim is None:
            uyarilar.append(f"Dosyadaki '{trimesh_birimi}' birimi tanınmadı; lütfen birimi elle seçin.")
        return birim

    @staticmethod
    def _govde_say(ag: trimesh.Trimesh) -> int:
        """
        Birbirine bağlı olmayan parça (gövde) sayısını bulur.

        Parametreler:
            ag: trimesh ağı.
        Dönüş:
            Gövde sayısı.
        """
        bilesenler = trimesh.graph.connected_components(
            ag.face_adjacency, nodes=np.arange(len(ag.faces)), engine=GRAF_MOTORU
        )
        return len(bilesenler)
