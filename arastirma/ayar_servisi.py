"""
Yapay zeka ayarları: anahtarın varlığı, model, günlük sınır ve bugünkü kullanım.

Ayarlar sayfası bu servisi kullanır. Öneri servisinden ayrıdır: ayarlar yalnızca
öneriye değil şartname madde çıkarımına da aittir.

Güvenlik: anahtarın kendisi hiçbir dönüşte yer almaz; yalnızca var/yok ve kaynağı.
"""

from dataclasses import dataclass, field

from arastirma.anahtar import AnahtarDeposu
from arastirma.ayarlar import EN_BUYUK_GUNLUK_SINIR, YapayZekaAyarDeposu
from arastirma.gemini import MODELLER
from arastirma.kullanim import GunlukKullanimSayaci


@dataclass(frozen=True)
class YapayZekaAyarDurumu:
    """
    Alanlar:
        anahtar_var: Anahtar bulunduysa True.
        anahtar_kaynagi: Anahtarın nereden okunduğu (ortam değişkeni / dosya); yoksa None.
        model: Seçili model.
        gunluk_sinir: Günlük en çok istek.
        bugun_kullanilan: Bugün yapılan istek sayısı.
        modeller: Seçilebilen modeller.
        en_buyuk_gunluk_sinir: Günlük sınırın üst sınırı.
    """

    anahtar_var: bool
    anahtar_kaynagi: str | None
    model: str
    gunluk_sinir: int
    bugun_kullanilan: int
    modeller: list[str] = field(default_factory=lambda: list(MODELLER))
    en_buyuk_gunluk_sinir: int = EN_BUYUK_GUNLUK_SINIR


class YapayZekaAyarServisi:
    """
    Yapay zeka ayarlarını okur ve değiştirir.

    Parametreler:
        anahtar: Anahtar deposu.
        ayarlar: Model ve günlük sınır deposu.
        sayac: Günlük kullanım sayacı.
    """

    def __init__(self, anahtar: AnahtarDeposu, ayarlar: YapayZekaAyarDeposu, sayac: GunlukKullanimSayaci) -> None:
        self._anahtar = anahtar
        self._ayarlar = ayarlar
        self._sayac = sayac

    def durum(self) -> YapayZekaAyarDurumu:
        """Ayarlar sayfası bilgisi (anahtarın kendisi yok)."""
        ayarlar = self._ayarlar.oku()
        kaynak = self._anahtar.kaynak()
        return YapayZekaAyarDurumu(
            anahtar_var=kaynak is not None,
            anahtar_kaynagi=kaynak,
            model=ayarlar.model,
            gunluk_sinir=ayarlar.gunluk_sinir,
            bugun_kullanilan=self._sayac.bugun(),
        )

    def guncelle(self, model: str | None, gunluk_sinir: int | None, anahtar: str | None) -> YapayZekaAyarDurumu:
        """
        Model, günlük sınır ve/veya anahtarı değiştirir; verilmeyenler aynı kalır.

        Hatalar:
            GecersizDegerHatasi: Değer geçersizse.
        """
        ayarlar = self._ayarlar.oku()
        if model is not None:
            ayarlar.model = model
        if gunluk_sinir is not None:
            ayarlar.gunluk_sinir = gunluk_sinir
        self._ayarlar.kaydet(ayarlar)
        if anahtar:
            self._anahtar.kaydet(anahtar)
        return self.durum()

    def anahtari_sil(self) -> YapayZekaAyarDurumu:
        """Anahtar dosyasını siler (ortam değişkenindeki anahtar etkilenmez)."""
        self._anahtar.sil()
        return self.durum()
