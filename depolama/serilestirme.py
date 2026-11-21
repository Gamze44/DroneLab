"""
Şasi verilerinin JSON'a çevrilmesi ve geri okunması.

dataclasses.asdict kullanılmaz: SasiGeometrisi içindeki trimesh ağı (ag)
JSON'a çevrilemez ve saklanması da gerekmez, çünkü şasi dosyası zaten
diskte duruyor; ağ gerektiğinde dosyadan yeniden okunur.
"""

import json
from typing import Any

from sasi.modeller import DingilKaynagi, GeometriTuru, SasiGeometrisi, SasiOlculeri


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
            "ozdes_govde_sayisi": geometri.ozdes_govde_sayisi,
            "tek_govde_olculeri": list(geometri.tek_govde_olculeri) if geometri.tek_govde_olculeri else None,
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
        # Eski kayıtlarda (sürüm 8 öncesi) bu alanlar yok; varsayılanlar tek gövdeli şasiye uyar.
        tek = s.get("tek_govde_olculeri")
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
            ozdes_govde_sayisi=s.get("ozdes_govde_sayisi", 1),
            tek_govde_olculeri=(tek[0], tek[1], tek[2]) if tek else None,
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
                "dingil_mm": olculer.dingil_mm,
                "dingil_kaynagi": olculer.dingil_kaynagi.value if olculer.dingil_kaynagi else None,
                "parca_sayisi": olculer.parca_sayisi,
                "tahmini": olculer.tahmini,
            },
            ensure_ascii=False,
        )

    @staticmethod
    def olculeri_oku(metin: str) -> SasiOlculeri:
        """JSON metninden SasiOlculeri nesnesini geri oluşturur (eski kayıtlarda yeni alanlar varsayılan)."""
        s = json.loads(metin)
        kaynak = s.get("dingil_kaynagi")
        return SasiOlculeri(
            birim=s["birim"],
            en_mm=s["en_mm"],
            boy_mm=s["boy_mm"],
            yukseklik_mm=s["yukseklik_mm"],
            hacim_mm3=s.get("hacim_mm3"),
            alan_mm2=s.get("alan_mm2"),
            uyarilar=list(s.get("uyarilar", [])),
            dingil_mm=s.get("dingil_mm"),
            dingil_kaynagi=DingilKaynagi(kaynak) if kaynak else None,
            parca_sayisi=s.get("parca_sayisi", 0),
            tahmini=s.get("tahmini", False),
        )
