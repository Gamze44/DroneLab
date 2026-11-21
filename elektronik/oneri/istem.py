"""
Öneri isteğinin metni (sistem talimatı + drone bilgisi).

Gemini'ye yalnızca drone türü, amacı, şasi ölçüsü ve mevcut parçaların teknik
değerleri gönderilir; drone adı ve başka kişisel bilgi gönderilmez.
"""

from typing import Final

from drone.hedefler import DroneHedefleri
from drone.modeller import DRONE_TURU_ADLARI, Drone
from elektronik.parcalar.diger_parca import DigerParca
from elektronik.parcalar.parca import Parca
from elektronik.parcalar.serilestirme import ParcaSerilestirici
from elektronik.parcalar.turler import DIGER_ALT_TUR_ADLARI, PARCA_TURU_ADLARI, DigerAltTur, ParcaTuru, alan_etiketi
from sartname.modeller import BUYUKLUK_TANIMLARI, SINIR_TURU_ADLARI, Madde, SinirTuru
from sasi.modeller import SasiOlculeri


def madde_metni(m: Madde) -> str:
    """Maddeyi "Kalkış ağırlığı en çok 2000 g (madde 4.2)" biçiminde yazar."""
    tanim = BUYUKLUK_TANIMLARI[m.buyukluk]
    if m.sinir_turu is SinirTuru.ZORUNLU or m.deger is None:
        govde = f"{tanim.ad}: {m.aciklama}" if not tanim.parca_mi else f"{tanim.ad} zorunlu"
    else:
        govde = f"{tanim.ad} {SINIR_TURU_ADLARI[m.sinir_turu]} {m.deger:g} {tanim.birim}".rstrip()
    return govde + (f" (madde {m.madde_no})" if m.madde_no else "")

# DEĞİŞTİRİLEBİLİR: Modelin uyması gereken kurallar.
SISTEM_TALIMATI: Final[str] = (
    "Sen deneyimli bir drone yapımcısısın ve parça öneriyorsun. Kurallar:\n"
    "1. Yalnızca gerçekten üretilmiş ve satılmış ürünleri öner; model adı uydurma.\n"
    "2. Emin olmadığın hiçbir teknik değeri yazma, o alanı boş bırak. Tahmin etme.\n"
    "3. Birimler: ağırlık gram, akım amper, gerilim volt, ölçüler mm, pervane çapı ve hatvesi inç.\n"
    "4. Bağlantı (URL) ve fiyat yazma.\n"
    "5. Drone'daki diğer parçalarla uyumlu olanları seç (hücre sayısı, akım, montaj, protokol, konnektör).\n"
    "6. Gerekçeyi Türkçe ve kısa yaz.\n"
    "Yalnızca istenen JSON şemasında yanıt ver."
)

# DEĞİŞTİRİLEBİLİR: Bir istekte istenecek aday sayısı.
ADAY_SAYISI: Final[int] = 3


def _deger_yaz(deger: object) -> str:
    if isinstance(deger, list):
        return ", ".join(str(d) for d in deger)
    if isinstance(deger, bool):
        return "evet" if deger else "hayır"
    return str(deger)


def parca_satiri(parca: Parca, adet: int) -> str:
    """Parçayı "- Motor: T-Motor F60 ×4 (33,5 g) — KV: 1950; ..." biçiminde tek satır yazar."""
    tur = PARCA_TURU_ADLARI[parca.tur]
    if isinstance(parca, DigerParca):
        tur = DIGER_ALT_TUR_ADLARI[parca.alt_tur]
    agirlik = f" ({parca.agirlik_g} g)" if parca.agirlik_g is not None else ""
    teknik = [
        f"{alan_etiketi(ad)}: {_deger_yaz(deger)}"
        for ad, deger in ParcaSerilestirici.teknik_sozluk(parca).items()
        if deger is not None and ad not in ("alt_tur", "itki_tablosu")
    ]
    return f"- {tur}: {parca.uretici} {parca.model} ×{adet}{agirlik}" + (f" — {'; '.join(teknik)}" if teknik else "")


class OneriIstemiOlusturucu:
    """Drone bilgisinden öneri isteği metnini oluşturur."""

    def olustur(
        self,
        drone: Drone,
        kalemler: list[tuple[Parca, int]],
        sasi_olculeri: SasiOlculeri | None,
        tur: ParcaTuru,
        alt_tur: DigerAltTur | None,
        aday_sayisi: int = ADAY_SAYISI,
        hedefler: DroneHedefleri | None = None,
        sartname_maddeleri: list[Madde] | None = None,
    ) -> str:
        """
        Parametreler:
            drone: Drone kaydı (adı gönderilmez).
            kalemler: Mevcut (parça, adet) listesi.
            sasi_olculeri: Şasi ölçüleri (mm) veya None.
            tur, alt_tur: Önerilecek parça türü.
            aday_sayisi: İstenen aday sayısı.
            hedefler: Kullanıcının hedefleri (uçuş süresi, yük, bütçe); yoksa None.
            sartname_maddeleri: Uyulması gereken şartname maddeleri (onaylı kesin kurallar).
        Dönüş:
            İstem metni.
        """
        istenen = DIGER_ALT_TUR_ADLARI[alt_tur] if tur is ParcaTuru.DIGER and alt_tur else PARCA_TURU_ADLARI[tur]
        satirlar = [
            f"Drone türü: {DRONE_TURU_ADLARI[drone.drone_turu]}",
            f"Kullanım amacı: {drone.amac}",
        ]
        if sasi_olculeri is not None:
            satirlar.append(f"Şasi dış ölçüsü: {sasi_olculeri.en_mm:.0f} × {sasi_olculeri.boy_mm:.0f} mm")
        if drone.sasi_agirlik_g is not None:
            satirlar.append(f"Şasi ağırlığı: {drone.sasi_agirlik_g} g")
        if hedefler is not None:
            if hedefler.ucus_suresi_dk is not None:
                satirlar.append(f"Hedef uçuş süresi: en az {hedefler.ucus_suresi_dk:g} dakika")
            if hedefler.yuk_g:
                satirlar.append(f"Taşınacak yük: {hedefler.yuk_g:g} g")
            if hedefler.butce_tl is not None:
                satirlar.append(f"Toplam parça bütçesi: {hedefler.butce_tl:g} TL (fiyat yazma, yalnızca bütçeye uygun seç)")
        if sartname_maddeleri:
            satirlar.append("Yarışma şartnamesinin uyulması zorunlu kuralları:")
            satirlar += [f"- {madde_metni(m)}" for m in sartname_maddeleri]
        satirlar.append("Mevcut parçalar:")
        satirlar += [parca_satiri(p, a) for p, a in kalemler] or ["- (henüz parça yok)"]
        satirlar += [
            "",
            f"Bu drone için {aday_sayisi} farklı {istenen} öner.",
            "Mevcut parçalarla aynı ürünü önerme. Birbirinden farklı seçenekler ver (ör. hafif / dengeli / güçlü).",
        ]
        return "\n".join(satirlar)
