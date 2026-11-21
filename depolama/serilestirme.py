"""
Şasi verilerinin JSON'a çevrilmesi ve geri okunması.

dataclasses.asdict kullanılmaz: SasiGeometrisi içindeki trimesh ağı (ag)
JSON'a çevrilemez ve saklanması da gerekmez, çünkü şasi dosyası zaten
diskte duruyor; ağ gerektiğinde dosyadan yeniden okunur.
"""

import json
from typing import Any

from sasi.modeller import GeometriTuru, SasiGeometrisi, SasiOlculeri


class SasiSerilestirici:
    """SasiGeometrisi ve SasiOlculeri nesnelerini JSON metnine çevirir ve geri okur."""

    @staticmethod
    def geometriyi_yaz(geometri: SasiGeometrisi) -> str:
        """
        Geometriyi JSON metnine çevirir (ağ hariç).

        Parametreler:
            geometri: Şasi geometrisi.
        Dönüş:
            JSON metni.
        """
        sozluk: dict[str, Any] = {
            "dosya_adi": geometri.dosya_adi,
            "tur": geometri.tur.value,
            "olculer": list(geometri.olculer),
            "dosya_birimi": geometri.dosya_birimi,
            "hacim": geometri.hacim,
            "alan": geometri.alan,
            "ucgen_sayisi": geometri.ucgen_sayisi,
            "govde_sayisi": geometri.govde_sayisi,
            "kapali_mi": geometri.kapali_mi,
            "dis_kontur_sayisi": geometri.dis_kontur_sayisi,
            "delik_sayisi": geometri.delik_sayisi,
            "uyarilar": geometri.uyarilar,
        }
        return json.dumps(sozluk, ensure_ascii=False)

    @staticmethod
    def geometriyi_oku(metin: str) -> SasiGeometrisi:
        """
        JSON metninden geometriyi geri oluşturur.

        Parametreler:
            metin: geometriyi_yaz ile üretilmiş JSON.
        Dönüş:
            SasiGeometrisi (ag alanı None).
        """
        s = json.loads(metin)
        x, y, z = s["olculer"]
        return SasiGeometrisi(
            dosya_adi=s["dosya_adi"],
            tur=GeometriTuru(s["tur"]),
            olculer=(x, y, z),
            dosya_birimi=s.get("dosya_birimi"),
            hacim=s.get("hacim"),
            alan=s.get("alan"),
            ucgen_sayisi=s.get("ucgen_sayisi", 0),
            govde_sayisi=s.get("govde_sayisi", 0),
            kapali_mi=s.get("kapali_mi", True),
            dis_kontur_sayisi=s.get("dis_kontur_sayisi", 0),
            delik_sayisi=s.get("delik_sayisi", 0),
            uyarilar=list(s.get("uyarilar", [])),
        )

    @staticmethod
    def olculeri_yaz(olculer: SasiOlculeri) -> str:
        """SasiOlculeri nesnesini JSON metnine çevirir."""
        return json.dumps(
            {
                "birim": olculer.birim,
                "en_mm": olculer.en_mm,
                "boy_mm": olculer.boy_mm,
                "yukseklik_mm": olculer.yukseklik_mm,
                "hacim_mm3": olculer.hacim_mm3,
                "alan_mm2": olculer.alan_mm2,
                "uyarilar": olculer.uyarilar,
            },
            ensure_ascii=False,
        )

    @staticmethod
    def olculeri_oku(metin: str) -> SasiOlculeri:
        """JSON metninden SasiOlculeri nesnesini geri oluşturur."""
        s = json.loads(metin)
        return SasiOlculeri(
            birim=s["birim"],
            en_mm=s["en_mm"],
            boy_mm=s["boy_mm"],
            yukseklik_mm=s["yukseklik_mm"],
            hacim_mm3=s.get("hacim_mm3"),
            alan_mm2=s.get("alan_mm2"),
            uyarilar=list(s.get("uyarilar", [])),
        )
