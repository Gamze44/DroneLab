"""
SQLite tabanlı yerel parça kataloğu.

Katalog tüm dronelar arasında ortaktır ve veri/dronelar.sqlite3 dosyasındaki
'parcalar' tablosunda durur. Aynı parça (aynı tür + üretici + model) iki kez
kaydedilmez; böylece bir kez araştırılan parça tekrar internette aranmaz.

Bu sınıf yalnızca saklama işini yapar: hangi değerin doğru olduğuna, ne zaman
doğrulanmış sayılacağına karar vermez (o iş mantığı sonraki aşamada).
"""

import sqlite3
from typing import Final

from cekirdek.hatalar import GecersizDegerHatasi, KayitBulunamadiHatasi, KayitZatenVarHatasi
from cekirdek.zaman import simdi_iso
from depolama.veritabani import Veritabani
from elektronik.parcalar.diger_parca import DigerParca
from elektronik.parcalar.parca import Parca, metni_sadelestir
from elektronik.parcalar.serilestirme import ParcaSerilestirici
from elektronik.parcalar.turler import DigerAltTur, ParcaTuru

# DEĞİŞTİRİLEBİLİR: Aramada döndürülecek en fazla parça sayısı.
VARSAYILAN_ARAMA_SINIRI: Final[int] = 50


class ParcaKatalogu:
    """
    Parçaları ekler, getirir, arar, günceller ve doğrulandı olarak işaretler.

    Parametreler:
        veritabani: Bağlantı sağlayan Veritabani nesnesi (şema sürüm 2 ve üstü).
    """

    def __init__(self, veritabani: Veritabani) -> None:
        self._vt = veritabani
        self._serilestirici = ParcaSerilestirici()

    # ---------- Yardımcılar ----------

    def _satirdan_parca(self, satir: sqlite3.Row) -> Parca:
        """Veritabanı satırını uygun Parca alt sınıfına çevirir."""
        ortak = {
            "kimlik": satir["kimlik"],
            "uretici": satir["uretici"],
            "model": satir["model"],
            "ad": satir["ad"],
            "agirlik_g": satir["agirlik_g"],
            "dogrulandi": bool(satir["dogrulandi"]),
            "kaynak_url": satir["kaynak_url"],
            "notlar": satir["notlar"],
        }
        return self._serilestirici.parca_olustur(satir["tur"], ortak, satir["teknik_json"])

    @staticmethod
    def _alt_tur(parca: Parca) -> str | None:
        """DigerParca için alt türün değeri, diğerleri için None."""
        return parca.alt_tur.value if isinstance(parca, DigerParca) else None

    def _ayni_anahtarli_kimlik(self, bag: sqlite3.Connection, anahtar: str) -> int | None:
        """Aynı arama anahtarına sahip kaydın kimliği; yoksa None."""
        satir = bag.execute("SELECT kimlik FROM parcalar WHERE arama_anahtari = ?", (anahtar,)).fetchone()
        return int(satir["kimlik"]) if satir else None

    @staticmethod
    def _zaten_var_hatasi(parca: Parca, mevcut_kimlik: int) -> KayitZatenVarHatasi:
        """Tekrar kayıt hatasını kullanıcıya anlaşılır mesajla oluşturur."""
        return KayitZatenVarHatasi(
            f"'{parca.gorunen_ad}' katalogda zaten kayıtlı. Mevcut kaydı kullanabilir veya güncelleyebilirsiniz.",
            mevcut_kimlik,
        )

    # ---------- İşlemler ----------

    def ekle(self, parca: Parca) -> Parca:
        """
        Yeni parçayı kataloğa ekler.

        Parametreler:
            parca: Kimliği olmayan (henüz kaydedilmemiş) parça.
        Dönüş:
            Kimliği atanmış parça (veritabanından okunmuş hali).
        Hatalar:
            GecersizDegerHatasi: Parçanın zaten bir kimliği varsa.
            KayitZatenVarHatasi: Aynı tür, üretici ve modelde parça zaten varsa.
        """
        if parca.kimlik is not None:
            raise GecersizDegerHatasi("Bu parça zaten kayıtlı görünüyor; değiştirmek için güncelleme kullanın.")
        zaman = simdi_iso()
        with self._vt.baglanti() as bag:
            mevcut = self._ayni_anahtarli_kimlik(bag, parca.arama_anahtari)
            if mevcut is not None:
                raise self._zaten_var_hatasi(parca, mevcut)
            imlec = bag.execute(
                "INSERT INTO parcalar (tur, alt_tur, uretici, model, ad, arama_anahtari, arama_metni, agirlik_g, "
                "teknik_json, dogrulandi, kaynak_url, notlar, olusturma_zamani, guncelleme_zamani) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    parca.tur.value, self._alt_tur(parca), parca.uretici, parca.model, parca.ad,
                    parca.arama_anahtari, parca.arama_metni, parca.agirlik_g,
                    self._serilestirici.teknik_json(parca), int(parca.dogrulandi),
                    parca.kaynak_url, parca.notlar, zaman, zaman,
                ),
            )
            kimlik = int(imlec.lastrowid)
        return self.getir(kimlik)

    def getir(self, kimlik: int) -> Parca:
        """
        Kimliği verilen parçayı döndürür.

        Hatalar:
            KayitBulunamadiHatasi: Parça yoksa.
        """
        with self._vt.baglanti() as bag:
            satir = bag.execute("SELECT * FROM parcalar WHERE kimlik = ?", (kimlik,)).fetchone()
        if satir is None:
            raise KayitBulunamadiHatasi("Parça katalogda bulunamadı.")
        return self._satirdan_parca(satir)

    def ayni_parcayi_bul(self, parca: Parca) -> Parca | None:
        """
        Aynı tür, üretici ve modeldeki kayıtlı parçayı bulur (yazım farkları yok sayılır).

        Araştırmadan önce çağrılır: parça zaten varsa internette tekrar aranmaz.

        Parametreler:
            parca: Kimliği olsun olmasın, karşılaştırılacak parça.
        Dönüş:
            Kayıtlı parça veya None.
        """
        with self._vt.baglanti() as bag:
            kimlik = self._ayni_anahtarli_kimlik(bag, parca.arama_anahtari)
        return self.getir(kimlik) if kimlik is not None else None

    def ara(
        self,
        metin: str = "",
        tur: ParcaTuru | None = None,
        alt_tur: DigerAltTur | None = None,
        yalnizca_dogrulanmis: bool = False,
        sinir: int = VARSAYILAN_ARAMA_SINIRI,
    ) -> list[Parca]:
        """
        Parçaları serbest metin ve filtrelerle arar.

        Metin kelimelere bölünür; her kelime (sadeleştirilmiş hali) üretici, model
        veya adda geçmelidir. Örn. "tmotor 2207" -> T-Motor marka ve 2207 içeren parçalar.

        Parametreler:
            metin: Aranacak metin; boşsa yalnızca filtreler uygulanır.
            tur: Yalnızca bu türdeki parçalar.
            alt_tur: Yalnızca bu alt türdeki (ikinci grup) parçalar.
            yalnizca_dogrulanmis: True ise doğrulanmamış parçalar gelmez.
            sinir: En fazla kaç sonuç.
        Dönüş:
            Son güncellenen en üstte olacak şekilde parça listesi.
        """
        kosullar: list[str] = []
        parametreler: list[object] = []
        for kelime in metin.split():
            sade = metni_sadelestir(kelime)
            if sade:
                # sade yalnızca harf ve rakam içerdiği için LIKE'ın % ve _ işaretleri kaçırılmaya gerek yok.
                kosullar.append("arama_metni LIKE ?")
                parametreler.append(f"%{sade}%")
        if tur is not None:
            kosullar.append("tur = ?")
            parametreler.append(ParcaTuru(tur).value)
        if alt_tur is not None:
            kosullar.append("alt_tur = ?")
            parametreler.append(DigerAltTur(alt_tur).value)
        if yalnizca_dogrulanmis:
            kosullar.append("dogrulandi = 1")

        sorgu = "SELECT * FROM parcalar"
        if kosullar:
            sorgu += " WHERE " + " AND ".join(kosullar)
        sorgu += " ORDER BY guncelleme_zamani DESC, kimlik DESC LIMIT ?"
        parametreler.append(sinir)

        with self._vt.baglanti() as bag:
            satirlar = bag.execute(sorgu, parametreler).fetchall()
        return [self._satirdan_parca(s) for s in satirlar]

    def guncelle(self, parca: Parca) -> Parca:
        """
        Kayıtlı parçanın tüm alanlarını verilen nesnedeki değerlerle değiştirir.

        Parça türü değiştirilemez (motor kaydı ESC'ye dönüşemez). Doğrulama durumu
        da nesnede ne yazıyorsa o kaydedilir; değer değişince doğrulamanın
        kaldırılıp kaldırılmayacağına iş mantığı karar verir.

        Parametreler:
            parca: Kimliği olan parça.
        Dönüş:
            Güncellenmiş parça.
        Hatalar:
            GecersizDegerHatasi: Kimlik yoksa veya tür değiştirilmeye çalışılıyorsa.
            KayitBulunamadiHatasi: Parça yoksa.
            KayitZatenVarHatasi: Yeni üretici/model başka bir kayıtla çakışıyorsa.
        """
        if parca.kimlik is None:
            raise GecersizDegerHatasi("Güncellenecek parçanın kimliği yok; yeni parça için ekleme kullanın.")
        mevcut = self.getir(parca.kimlik)
        if mevcut.tur_anahtari != parca.tur_anahtari:
            raise GecersizDegerHatasi("Parçanın türü değiştirilemez. Yeni türde ayrı bir parça ekleyin.")
        with self._vt.baglanti() as bag:
            cakisan = self._ayni_anahtarli_kimlik(bag, parca.arama_anahtari)
            if cakisan is not None and cakisan != parca.kimlik:
                raise self._zaten_var_hatasi(parca, cakisan)
            bag.execute(
                "UPDATE parcalar SET uretici = ?, model = ?, ad = ?, arama_anahtari = ?, arama_metni = ?, "
                "agirlik_g = ?, teknik_json = ?, dogrulandi = ?, kaynak_url = ?, notlar = ?, guncelleme_zamani = ? "
                "WHERE kimlik = ?",
                (
                    parca.uretici, parca.model, parca.ad, parca.arama_anahtari, parca.arama_metni,
                    parca.agirlik_g, self._serilestirici.teknik_json(parca), int(parca.dogrulandi),
                    parca.kaynak_url, parca.notlar, simdi_iso(), parca.kimlik,
                ),
            )
        return self.getir(parca.kimlik)

    def dogrula(self, kimlik: int) -> Parca:
        """
        Parçayı "doğrulandı" olarak işaretler (kullanıcı teknik değerleri onayladı).

        Hatalar:
            KayitBulunamadiHatasi: Parça yoksa.
        """
        with self._vt.baglanti() as bag:
            imlec = bag.execute(
                "UPDATE parcalar SET dogrulandi = 1, guncelleme_zamani = ? WHERE kimlik = ?",
                (simdi_iso(), kimlik),
            )
        if imlec.rowcount == 0:
            raise KayitBulunamadiHatasi("Doğrulanacak parça katalogda bulunamadı.")
        return self.getir(kimlik)
