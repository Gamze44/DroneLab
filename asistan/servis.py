"""
Asistan sohbetini yöneten servis.

Bir soru şöyle işlenir:
    1. Kullanıcının mesajı kaydedilir; bağlam (ekran + drone özeti) ve son mesajlar hazırlanır.
    2. Model çağrılır; metin parçaları arayüze akış olarak iletilir.
    3. Model araç isterse araç çalıştırılır, sonuç modele geri verilir ve model yeniden çağrılır
       (en çok EN_FAZLA_ARAC_TURU kez; son turda araç kullanımı kapatılır, model yanıt yazar).
    4. Yanıt ve yapılan öneriler kaydedilir.

Akış + araç + store=false birleşimi Gemini belgelerinde örneklenmediği için, akıştan yeniden
kurulan geçmiş bir sonraki istekte reddedilirse (400) soru baştan, akışsız modda işlenir ve bu
tercih program açık kaldıkça hatırlanır.
"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from http import HTTPStatus
import logging
from typing import Any, Final

from arastirma.istemci import YapayZekaIstemcisi
from arastirma.sohbet import (
    ARAC_SERBEST,
    ARAC_YASAK,
    OLAY_ARAC_CAGRISI,
    OLAY_BITTI,
    OLAY_METIN,
    AracCagrisi,
    arac_sonucu,
    kullanici_girdisi,
    model_ciktisi,
)
from asistan.araclar import ARAC_ACIKLAMALARI, AsistanAraclari
from asistan.ayarlar import (
    EN_FAZLA_ARAC_TURU,
    EN_UZUN_MESAJ,
    GECMIS_MESAJ_SINIRI,
    OZET_SORU_SAYISI,
    OZET_SORU_UZUNLUGU,
    SISTEM_TALIMATI,
)
from asistan.baglam import BaglamToplayici
from asistan.gecmis import MesajRolu, SohbetGecmisi, SohbetMesaji
from asistan.oneriler import OneriDeposu, OneriUygulayici
from cekirdek.hatalar import DroneProgramHatasi, GecersizDegerHatasi, YapayZekaHatasi
from elektronik.servis import ElektronikServisi

# Arayüze giden olay türleri.
OLAY_UI_METIN: Final[str] = "metin"
OLAY_UI_ARAC: Final[str] = "arac"
OLAY_UI_ONERI: Final[str] = "oneri"
OLAY_UI_SIFIRLA: Final[str] = "sifirla"
OLAY_UI_HATA: Final[str] = "hata"
OLAY_UI_BITTI: Final[str] = "bitti"

BOS_YANIT_MESAJI: Final[str] = "Model bir yanıt üretmedi. Soruyu farklı biçimde sormayı deneyin."
ONERI_YANITI: Final[str] = "Önerimi aşağıdaki kartta inceleyebilirsiniz."
DURDURULDU_EKI: Final[str] = " (yanıt durduruldu)"
YARIM_KALDI_EKI: Final[str] = " (yanıt yarıda kesildi)"
BEKLENMEYEN_HATA_MESAJI: Final[str] = "Asistan beklenmeyen bir hatayla karşılaştı. Tekrar deneyin."

gunluk = logging.getLogger(__name__)

UiOlayi = dict[str, Any]


@dataclass
class _TurDurumu:
    """Bir sorunun işlenmesi sırasında biriken bilgiler."""

    parcalar: list[str] = field(default_factory=list)
    oneriler: list[int] = field(default_factory=list)
    model: str = ""
    bugun_kullanilan: int = 0
    gunluk_sinir: int = 0
    istek_sayisi: int = 0

    @property
    def metin(self) -> str:
        return "".join(self.parcalar).strip()


class AsistanServisi:
    """
    Parametreler:
        yapay_zeka: Anahtar, günlük sınır ve model seçimiyle istek gönderen istemci.
        gecmis: Sohbet geçmişi.
        oneriler: Öneri deposu.
        uygulayici: Öneriyi uygulayan/reddeden sınıf.
        araclar: Asistan araçları.
        baglam: Bağlam toplayıcı.
        elektronik: Drone var mı denetimi için ElektronikServisi.
    """

    def __init__(
        self,
        yapay_zeka: YapayZekaIstemcisi,
        gecmis: SohbetGecmisi,
        oneriler: OneriDeposu,
        uygulayici: OneriUygulayici,
        araclar: AsistanAraclari,
        baglam: BaglamToplayici,
        elektronik: ElektronikServisi,
    ) -> None:
        self._yz = yapay_zeka
        self._gecmis = gecmis
        self._oneriler = oneriler
        self._uygulayici = uygulayici
        self._araclar = araclar
        self._baglam = baglam
        self._elektronik = elektronik
        # Akış + araç birleşimi reddedilirse False olur (program açık kaldıkça).
        self._akis_kullan = True

    # ---------- Sohbet ----------

    def baslat(self, drone_kimlik: int | None, ekran: str, mesaj: str) -> Iterator[UiOlayi]:
        """
        Soruyu denetler ve yanıt akışını hazırlar.

        Denetimler akış başlamadan yapılır; böylece anahtar yokluğu, günlük sınır gibi hatalar
        arayüze normal JSON hata olarak döner.

        Parametreler:
            drone_kimlik: Açık drone; ana sayfa/ayarlarda None.
            ekran: Arayüzdeki ekran anahtarı.
            mesaj: Kullanıcının sorusu.
        Dönüş:
            Arayüz olayları akışı (metin, arac, oneri, sifirla, hata, bitti).
        Hatalar:
            GecersizDegerHatasi, KayitBulunamadiHatasi, YapayZekaHatasi (401/429).
        """
        mesaj = mesaj.strip()
        if not mesaj:
            raise GecersizDegerHatasi("Bir soru yazın.")
        if len(mesaj) > EN_UZUN_MESAJ:
            raise GecersizDegerHatasi(f"Mesaj en çok {EN_UZUN_MESAJ} karakter olabilir.")
        if drone_kimlik is not None:
            self._elektronik.drone_getir(drone_kimlik)
        self._yz.on_denetle()
        return self._yanitla(drone_kimlik, ekran, mesaj)

    def _yanitla(self, drone_kimlik: int | None, ekran: str, mesaj: str) -> Iterator[UiOlayi]:
        """Soruyu işler ve arayüz olaylarını üretir (bkz. modül açıklaması)."""
        onceki = self._gecmis.listele(drone_kimlik)
        self._gecmis.ekle(drone_kimlik, MesajRolu.KULLANICI, mesaj)
        durum = _TurDurumu()
        kaydedildi = False
        try:
            sistem = self._sistem_talimati(ekran, drone_kimlik, onceki)
            girdiler = self._girdiler(onceki, mesaj)
            araclar = self._araclar.tanimlar(drone_kimlik is not None)
            try:
                yield from self._turlar(sistem, girdiler, araclar, drone_kimlik, durum, self._akis_kullan)
            except YapayZekaHatasi as hata:
                if not self._akissiz_denenmeli(hata, durum):
                    raise
                gunluk.warning("Akıştan kurulan geçmiş reddedildi; asistan akışsız moda geçiyor.")
                self._akis_kullan = False
                self._oneriler.sil(durum.oneriler)
                durum = _TurDurumu()
                yield {"tur": OLAY_UI_SIFIRLA}
                yield from self._turlar(sistem, girdiler, araclar, drone_kimlik, durum, akis=False)
            kayit = self._yaniti_kaydet(drone_kimlik, durum, "")
            kaydedildi = True
            yield {
                "tur": OLAY_UI_BITTI, "mesaj_kimlik": kayit.kimlik, "model": durum.model,
                "bugun_kullanilan": durum.bugun_kullanilan, "gunluk_sinir": durum.gunluk_sinir,
            }
        except DroneProgramHatasi as hata:
            if durum.metin or durum.oneriler:
                self._yaniti_kaydet(drone_kimlik, durum, YARIM_KALDI_EKI)
            kaydedildi = True
            kod = hata.http_kodu if isinstance(hata, YapayZekaHatasi) else HTTPStatus.BAD_REQUEST
            yield {"tur": OLAY_UI_HATA, "hata": hata.mesaj, "kod": int(kod)}
        except Exception:
            gunluk.exception("Asistan yanıtı üretilemedi")
            kaydedildi = True
            yield {"tur": OLAY_UI_HATA, "hata": BEKLENMEYEN_HATA_MESAJI, "kod": int(HTTPStatus.INTERNAL_SERVER_ERROR)}
        finally:
            # Kullanıcı "Durdur"a bastıysa (bağlantı kapandı) gelen kısım kaybolmasın.
            if not kaydedildi and (durum.metin or durum.oneriler):
                self._yaniti_kaydet(drone_kimlik, durum, DURDURULDU_EKI)

    def _turlar(
        self,
        sistem: str,
        temel_girdiler: list[dict[str, Any]],
        araclar: list[Any],
        drone_kimlik: int | None,
        durum: _TurDurumu,
        akis: bool,
    ) -> Iterator[UiOlayi]:
        """Model ↔ araç döngüsü; olayları üretir ve `durum`u doldurur."""
        girdiler = list(temel_girdiler)
        for tur_no in range(EN_FAZLA_ARAC_TURU + 1):
            # Son turda araç kullanımı kapatılır: model eldeki sonuçlarla yanıt yazmak zorundadır.
            kullanim = ARAC_YASAK if tur_no == EN_FAZLA_ARAC_TURU else ARAC_SERBEST
            cagrilar: list[AracCagrisi] = []
            for olay in self._yz.sohbet(sistem, girdiler, araclar, akis, kullanim):
                if olay.tur == OLAY_METIN:
                    durum.parcalar.append(olay.metin)
                    yield {"tur": OLAY_UI_METIN, "metin": olay.metin}
                elif olay.tur == OLAY_ARAC_CAGRISI and olay.cagri is not None:
                    cagrilar.append(olay.cagri)
                elif olay.tur == OLAY_BITTI:
                    durum.model, durum.bugun_kullanilan, durum.gunluk_sinir = olay.model, olay.bugun_kullanilan, olay.gunluk_sinir
                    girdiler.extend(olay.adimlar)
            durum.istek_sayisi += 1
            if not cagrilar or kullanim == ARAC_YASAK:
                return
            for cagri in cagrilar:
                yield {"tur": OLAY_UI_ARAC, "ad": cagri.ad, "aciklama": ARAC_ACIKLAMALARI.get(cagri.ad, cagri.ad)}
                sonuc = self._araclar.calistir(cagri.ad, cagri.argumanlar, drone_kimlik)
                if sonuc.oneri is not None:
                    durum.oneriler.append(sonuc.oneri.kimlik)
                    yield {"tur": OLAY_UI_ONERI, "oneri": sonuc.oneri.sozluk()}
                girdiler.append(arac_sonucu(cagri, sonuc.veri, sonuc.hata_mi))

    def _akissiz_denenmeli(self, hata: YapayZekaHatasi, durum: _TurDurumu) -> bool:
        """Akıştan kurulan geçmiş (ilk turdan sonraki istek) reddedildiyse True."""
        return self._akis_kullan and hata.http_kodu == HTTPStatus.BAD_REQUEST and durum.istek_sayisi > 0

    def _yaniti_kaydet(self, drone_kimlik: int | None, durum: _TurDurumu, ek: str) -> SohbetMesaji:
        """Asistanın yanıtını kaydeder ve turdaki önerileri mesaja bağlar."""
        metin = durum.metin or (ONERI_YANITI if durum.oneriler else BOS_YANIT_MESAJI)
        kayit = self._gecmis.ekle(drone_kimlik, MesajRolu.ASISTAN, metin + ek, durum.model or None)
        if durum.oneriler:
            self._oneriler.mesaja_bagla(durum.oneriler, kayit.kimlik)
        return kayit

    def _sistem_talimati(self, ekran: str, drone_kimlik: int | None, onceki: list[SohbetMesaji]) -> str:
        """Sistem talimatı + bağlam + (varsa) eski konuşmanın kısa özeti."""
        metin = f"{SISTEM_TALIMATI}\n# Bağlam\n{self._baglam.topla(ekran, drone_kimlik)}"
        eskiler = onceki[:-GECMIS_MESAJ_SINIRI] if len(onceki) > GECMIS_MESAJ_SINIRI else []
        sorular = [m.metin for m in eskiler if m.rol is MesajRolu.KULLANICI][-OZET_SORU_SAYISI:]
        if sorular:
            # Özet için ayrıca model çağrılmaz (kota harcamasın); eski sorular kısaltılarak listelenir.
            metin += "\n\n# Daha önceki konuşmada sorulanlar\n" + "\n".join(f"- {s[:OZET_SORU_UZUNLUGU]}" for s in sorular)
        return metin

    @staticmethod
    def _girdiler(onceki: list[SohbetMesaji], mesaj: str) -> list[dict[str, Any]]:
        """Son mesajlar + yeni soru, model girdisi olarak."""
        girdiler = [
            kullanici_girdisi(m.metin) if m.rol is MesajRolu.KULLANICI else model_ciktisi(m.metin)
            for m in onceki[-GECMIS_MESAJ_SINIRI:]
        ]
        return girdiler + [kullanici_girdisi(mesaj)]

    # ---------- Geçmiş ve öneriler ----------

    def gecmis(self, drone_kimlik: int | None) -> list[dict[str, Any]]:
        """
        Sohbetin mesajları ve her yanıttaki öneri kartları.

        Hatalar:
            KayitBulunamadiHatasi: Drone verilmiş ama yoksa.
        """
        if drone_kimlik is not None:
            self._elektronik.drone_getir(drone_kimlik)
        mesajlar = self._gecmis.listele(drone_kimlik)
        oneriler = self._oneriler.mesajlarin_onerileri([m.kimlik for m in mesajlar if m.rol is MesajRolu.ASISTAN])
        return [
            {
                "kimlik": m.kimlik, "rol": m.rol.value, "metin": m.metin, "model": m.model, "zaman": m.zaman,
                "oneriler": [o.sozluk() for o in oneriler.get(m.kimlik, [])],
            }
            for m in mesajlar
        ]

    def temizle(self, drone_kimlik: int | None) -> None:
        """"Yeni sohbet": sohbetin mesajlarını ve önerilerini siler."""
        if drone_kimlik is not None:
            self._elektronik.drone_getir(drone_kimlik)
            self._oneriler.baglanmamislari_sil(drone_kimlik)
        self._gecmis.temizle(drone_kimlik)

    def oneriyi_uygula(self, kimlik: int) -> dict[str, Any]:
        """Kullanıcı "Uygula"ya bastı. Hatalar: KayitBulunamadiHatasi, GecersizDegerHatasi."""
        return self._uygulayici.uygula(kimlik).sozluk()

    def oneriden_vazgec(self, kimlik: int) -> dict[str, Any]:
        """Kullanıcı "Vazgeç"e bastı. Hatalar: KayitBulunamadiHatasi, GecersizDegerHatasi."""
        return self._uygulayici.vazgec(kimlik).sozluk()
