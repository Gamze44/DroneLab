"""
Yapay zekaya istek göndermenin ortak adımları: anahtar var mı, günlük sınır
aşıldı mı, hangi model kullanılacak. Öneri, şartname madde çıkarımı ve asistan
sohbeti bu sınıfı kullanır; böylece sınır, anahtar ve model seçimi kuralları tek yerde durur.

Model seçimi: ayarlarda "Otomatik" seçiliyse ModelSecici sırasıyla denenir; bir model kota
veya yoğunluk hatası verirse aynı istek sıradaki modelle tekrarlanır. Her deneme günlük
sayaca yazılır (gönderilmiş her istek kotadan düşebilir).
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from http import HTTPStatus
import logging
from pathlib import Path
import time
from typing import Any, Final

from arastirma.anahtar import AnahtarDeposu
from arastirma.ayarlar import YapayZekaAyarDeposu, YapayZekaAyarlari
from arastirma.gemini import GeminiSaglayicisi
from arastirma.kullanim import GunlukKullanimSayaci
from arastirma.model_secici import HEPSI_DOLU_MESAJI, ModelSecici
from arastirma.saglayici import ArastirmaSaglayicisi
from arastirma.sohbet import ARAC_SERBEST, OLAY_BITTI, AracTanimi, SohbetOlayi
from cekirdek.ayarlar import VERITABANI_DOSYA_ADI
from cekirdek.hatalar import YapayZekaHatasi
from depolama.veritabani import Veritabani

ANAHTAR_YOK_MESAJI: Final[str] = (
    "Gemini API anahtarı bulunamadı. Ana sayfadaki Ayarlar bölümünden anahtar girin; "
    "o zamana kadar bilgileri elle girebilirsiniz."
)
# Günlüğe yazılan kullanım alanları (A1 harcama sayacı gelene kadar en azından kayıt kalsın).
KULLANIM_ALANLARI: Final[tuple[str, ...]] = (
    "total_input_tokens", "total_output_tokens", "total_thought_tokens", "total_tokens",
)

gunluk = logging.getLogger(__name__)

SaglayiciUretici = Callable[[str, str], ArastirmaSaglayicisi]


def gemini_uret(anahtar: str, model: str) -> ArastirmaSaglayicisi:
    """Varsayılan sağlayıcı üretici (gerçek Gemini)."""
    return GeminiSaglayicisi(anahtar, model)


@dataclass
class YapayZekaYaniti:
    """
    Alanlar:
        veri: Modelin JSON yanıtı.
        bugun_kullanilan / gunluk_sinir: Günlük kullanım bilgisi.
        model: Kullanılan model.
    """

    veri: dict[str, Any]
    bugun_kullanilan: int
    gunluk_sinir: int
    model: str


class YapayZekaIstemcisi:
    """
    Anahtar ve günlük sınır kontrolüyle yapay zekaya şemalı istek gönderir.

    Parametreler:
        veri_klasoru: veri/ klasörü (anahtar, ayarlar, kullanım sayacı).
        saglayici_uretici: (anahtar, model) -> sağlayıcı; testlerde sahtesi verilir.
        veritabani: Ortak Veritabani; verilmezse veri klasöründeki dosya açılır.
        model_secici: Otomatik model seçimi; verilmezse yenisi oluşturulur (sunucu başına tek olmalı).
    """

    def __init__(
        self,
        veri_klasoru: Path,
        saglayici_uretici: SaglayiciUretici = gemini_uret,
        veritabani: Veritabani | None = None,
        model_secici: ModelSecici | None = None,
    ) -> None:
        self.anahtar = AnahtarDeposu(veri_klasoru)
        self.ayarlar = YapayZekaAyarDeposu(veri_klasoru)
        self.sayac = GunlukKullanimSayaci(veritabani or Veritabani(veri_klasoru / VERITABANI_DOSYA_ADI))
        self.model_secici = model_secici or ModelSecici()
        self._uretici = saglayici_uretici

    def _hazirlik(self) -> tuple[str, YapayZekaAyarlari]:
        """
        Anahtarı ve ayarları okur.

        Hatalar:
            YapayZekaHatasi: Anahtar yoksa (401).
        """
        anahtar = self.anahtar.oku()
        if not anahtar:
            raise YapayZekaHatasi(ANAHTAR_YOK_MESAJI, HTTPStatus.UNAUTHORIZED)
        return anahtar, self.ayarlar.oku()

    def on_denetle(self) -> None:
        """
        İstek göndermeden önce anahtarın varlığını ve günlük sınırı denetler (sayaç artmaz).

        Akışlı yanıt başlamadan hatayı normal JSON hata olarak döndürebilmek için kullanılır.

        Hatalar:
            YapayZekaHatasi: Anahtar yoksa (401) veya bugünkü sınır dolduysa (429).
        """
        _, ayarlar = self._hazirlik()
        if self.sayac.bugun() >= ayarlar.gunluk_sinir:
            raise YapayZekaHatasi(self.sayac.sinir_mesaji(ayarlar.gunluk_sinir), HTTPStatus.TOO_MANY_REQUESTS)

    def _adaylar(self, ayarlar: YapayZekaAyarlari) -> list[str]:
        """
        Denenecek modeller.

        Hatalar:
            YapayZekaHatasi: Otomatik modda bütün modeller bugün dinlenmedeyse (429).
        """
        adaylar = self.model_secici.adaylar(ayarlar.model)
        if not adaylar:
            raise YapayZekaHatasi(HEPSI_DOLU_MESAJI, HTTPStatus.TOO_MANY_REQUESTS)
        return adaylar

    def istek(self, sistem_talimati: str, istem: str, sema: dict[str, Any]) -> YapayZekaYaniti:
        """
        Şemalı JSON isteği gönderir; gerekirse sıradaki modele geçer.

        Hatalar:
            YapayZekaHatasi: Anahtar yoksa, günlük sınır dolduysa veya istek (bütün modellerde) başarısızsa.
        """
        anahtar, ayarlar = self._hazirlik()
        son_hata: YapayZekaHatasi | None = None
        for model in self._adaylar(ayarlar):
            kullanilan = self.sayac.harca(ayarlar.gunluk_sinir)
            baslangic = time.monotonic()
            try:
                veri = self._uretici(anahtar, model).json_uret(sistem_talimati, istem, sema)
                self.model_secici.sure_bildir(model, time.monotonic() - baslangic)
            except YapayZekaHatasi as hata:
                if not self.model_secici.basarisiz(model, hata):
                    raise
                gunluk.info("Gemini modeli %s kullanılamadı (%s); sıradaki model denenecek.", model, hata.http_kodu)
                son_hata = hata
                continue
            return YapayZekaYaniti(veri, kullanilan, ayarlar.gunluk_sinir, model)
        raise son_hata or YapayZekaHatasi(HEPSI_DOLU_MESAJI, HTTPStatus.TOO_MANY_REQUESTS)

    def sohbet(
        self,
        sistem_talimati: str,
        girdiler: list[dict[str, Any]],
        araclar: list[AracTanimi],
        akis: bool = True,
        arac_kullanimi: str = ARAC_SERBEST,
    ) -> Iterator[SohbetOlayi]:
        """
        Sohbetin bir turunu çalıştırır (bkz. ArastirmaSaglayicisi.sohbet_et).

        Bir model henüz hiçbir şey göndermeden kota/yoğunluk hatası verirse tur sıradaki
        modelle yeniden başlar; yanıt akmaya başladıktan sonraki hata olduğu gibi iletilir.
        Son olayda (OLAY_BITTI) kullanılan model ve günlük kullanım doldurulur.

        Hatalar:
            YapayZekaHatasi: Anahtar yoksa, sınır dolduysa veya istek başarısızsa.
        """
        anahtar, ayarlar = self._hazirlik()
        son_hata: YapayZekaHatasi | None = None
        for model in self._adaylar(ayarlar):
            kullanilan = self.sayac.harca(ayarlar.gunluk_sinir)
            olay_verildi = False
            baslangic = time.monotonic()
            try:
                saglayici = self._uretici(anahtar, model)
                for olay in saglayici.sohbet_et(sistem_talimati, girdiler, araclar, akis, arac_kullanimi):
                    if olay.tur == OLAY_BITTI:
                        olay.model, olay.bugun_kullanilan, olay.gunluk_sinir = model, kullanilan, ayarlar.gunluk_sinir
                        self._kullanimi_kaydet(model, olay.kullanim)
                        sure = time.monotonic() - baslangic
                        self.model_secici.sure_bildir(model, sure)
                        gunluk.info("Gemini yanıtı (%s) %.1f sn sürdü.", model, sure)
                    olay_verildi = True
                    yield olay
                return
            except YapayZekaHatasi as hata:
                if olay_verildi or not self.model_secici.basarisiz(model, hata):
                    raise
                gunluk.info("Gemini modeli %s kullanılamadı (%s); sıradaki model denenecek.", model, hata.http_kodu)
                son_hata = hata
        raise son_hata or YapayZekaHatasi(HEPSI_DOLU_MESAJI, HTTPStatus.TOO_MANY_REQUESTS)

    @staticmethod
    def _kullanimi_kaydet(model: str, kullanim: dict[str, Any] | None) -> None:
        """Token kullanımını günlüğe yazar (anahtar ve içerik yazılmaz)."""
        if kullanim:
            gunluk.info("Gemini kullanımı (%s): %s", model, {k: kullanim.get(k) for k in KULLANIM_ALANLARI if k in kullanim})
