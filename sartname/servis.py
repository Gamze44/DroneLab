"""
Şartname işlemlerini yöneten servis: belge yükleme, kütüphane, madde düzenleme,
Gemini ile madde çıkarımı, drone'a bağlama ve uyum raporu.
"""

from dataclasses import dataclass, field
from pathlib import Path
import shutil
from typing import Any
import uuid

from arastirma.istemci import YapayZekaIstemcisi
from cekirdek.arsiv_denetimi import ArsivDenetleyici
from cekirdek.ayarlar import SARTNAME_DOSYALARI_KLASOR_ADI, VERITABANI_DOSYA_ADI
from cekirdek.hatalar import GecersizDegerHatasi, YapayZekaHatasi
from depolama.veritabani import Veritabani
from elektronik.servis import ElektronikServisi
from maliyet.servis import MaliyetServisi
from sartname.cikarim import SISTEM_TALIMATI, MaddeDonusturucu, istem_olustur, madde_semasi
from sartname.depo import SartnameDeposu
from sartname.kontrol import MaddeSonucu, SartnameBaglami, SartnameKontrolcusu
from sartname.metin_cikarici import WORD_UZANTISI, SartnameMetinCikarici
from sartname.sayfa_sayisi import SayfaSiniriDenetleyici
from sartname.modeller import Buyukluk, Madde, MaddeSinifi, Sartname


@dataclass
class CikarimRaporu:
    """
    Alanlar:
        maddeler: Kaydedilen (onaylanmamış) maddeler.
        atlanan: Geçersiz olduğu için alınmayan madde sayısı.
        bugun_kullanilan / gunluk_sinir: Günlük yapay zeka kullanımı.
    """

    maddeler: list[Madde]
    atlanan: int
    bugun_kullanilan: int
    gunluk_sinir: int


@dataclass
class DroneSartnameRaporu:
    """
    Alanlar:
        sartname: Drone'a bağlı şartname; yoksa None.
        sonuclar: Her madde için uyum sonucu.
    """

    sartname: Sartname | None
    sonuclar: list[MaddeSonucu] = field(default_factory=list)


class SartnameServisi:
    """
    Parametreler:
        veri_klasoru: veri/ klasörü (veritabanı ve belge kopyaları).
        elektronik: Tasarım bilgilerini veren ElektronikServisi.
        maliyet: Maliyet maddeleri için MaliyetServisi.
        yapay_zeka: Madde çıkarımı için YapayZekaIstemcisi.
        veritabani: Ortak Veritabani; verilmezse veri klasöründeki dosya açılır.
    """

    def __init__(
        self,
        veri_klasoru: Path,
        elektronik: ElektronikServisi,
        maliyet: MaliyetServisi,
        yapay_zeka: YapayZekaIstemcisi,
        veritabani: Veritabani | None = None,
    ) -> None:
        self._veri_klasoru = veri_klasoru
        self._depo = SartnameDeposu(veritabani or Veritabani(veri_klasoru / VERITABANI_DOSYA_ADI))
        self._elektronik = elektronik
        self._maliyet = maliyet
        self._yz = yapay_zeka
        self._metin = SartnameMetinCikarici()
        self._arsiv = ArsivDenetleyici()
        self._sayfa_siniri = SayfaSiniriDenetleyici()
        self._donusturucu = MaddeDonusturucu()
        self._kontrol = SartnameKontrolcusu()

    # ---------- Kütüphane ----------

    def dosya_turunu_denetle(self, dosya_adi: str) -> None:
        """Hatalar: DesteklenmeyenDosyaHatasi (.pdf / .docx değilse)."""
        self._metin.uzantiyi_denetle(dosya_adi)

    def yukle(self, gecici_yol: Path, dosya_adi: str, ad: str, drone_kimlik: int | None = None) -> Sartname:
        """
        Belgeyi kütüphaneye ekler; drone verilirse ona da bağlar.

        Belgeden metin çıkarılır (taranmış belgede boş kalabilir) ve sayfa sınırı
        denetlenir; maddeler ayrıca "Gemini ile çıkar" veya elle eklenir.

        Hatalar:
            DesteklenmeyenDosyaHatasi, DosyaOkumaHatasi, GecersizDegerHatasi, KayitBulunamadiHatasi.
        """
        uzanti = self._metin.uzantiyi_denetle(dosya_adi)
        if drone_kimlik is not None:
            self._elektronik.drone_getir(drone_kimlik)
        if not ad.strip():
            raise GecersizDegerHatasi("Şartnameye bir ad verin (ör. yarışmanın adı ve yılı).")
        if uzanti == WORD_UZANTISI:
            # Word belgesi bir zip arşividir; açılmadan önce zip bombasına karşı denetlenir.
            self._arsiv.denetle(gecici_yol)
        # Sayfa sınırı kopyalamadan önce denetlenir: reddedilen belge kütüphanede iz bırakmasın.
        # Kesin sayfa sayısı biliniyorsa metin çıkarmadan önce denetlenir (500 sayfalık
        # bir belge boşuna işlenmesin); bilinmiyorsa metinden tahmin edilir.
        sayfa = self._sayfa_siniri.on_denetle(gecici_yol)
        metin = self._metin.cikar(gecici_yol)
        if sayfa is None:
            self._sayfa_siniri.tahmini_denetle(metin)
        goreli =Path(SARTNAME_DOSYALARI_KLASOR_ADI) / f"{uuid.uuid4().hex}{uzanti}"
        hedef = self._veri_klasoru / goreli
        hedef.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(gecici_yol, hedef)
        try:
            sartname = self._depo.ekle(ad, dosya_adi, goreli.as_posix(), metin)
        except Exception:
            hedef.unlink(missing_ok=True)  # kayıt olmadıysa yetim dosya kalmasın
            raise
        if drone_kimlik is not None:
            self._depo.bagla(drone_kimlik, sartname.kimlik)
            sartname = self._depo.getir(sartname.kimlik)
        return sartname

    def listele(self) -> list[Sartname]:
        """Önceden yüklenmiş şartnameler."""
        return self._depo.listele()

    def getir(self, kimlik: int) -> tuple[Sartname, list[Madde]]:
        """Şartname ve maddeleri. Hatalar: KayitBulunamadiHatasi."""
        return self._depo.getir(kimlik), self._depo.maddeler(kimlik)

    def sil(self, kimlik: int) -> None:
        """
        Hiçbir drone'un kullanmadığı şartnameyi ve belge kopyasını siler.

        Hatalar:
            KayitBulunamadiHatasi; GecersizDegerHatasi: kullanılıyorsa.
        """
        silinen = self._depo.sil(kimlik)
        (self._veri_klasoru / silinen.saklanan_dosya).unlink(missing_ok=True)

    # ---------- Maddeler ----------

    def maddeleri_kaydet(self, kimlik: int, ham_maddeler: list[dict[str, Any]]) -> list[Madde]:
        """
        Düzenlenen madde tablosunu kaydeder (eskilerin yerine geçer).

        Hatalar:
            GecersizDegerHatasi: Bir satır geçersizse (satır numarasıyla).
            KayitBulunamadiHatasi: Şartname yoksa.
        """
        maddeler = []
        for sira, ham in enumerate(ham_maddeler, start=1):
            try:
                maddeler.append(Madde(**{k: ham.get(k) for k in (
                    "aciklama", "buyukluk", "sinir_turu", "deger", "madde_no", "sayfa")},
                    sinif=ham.get("sinif") or MaddeSinifi.KESIN, onaylandi=bool(ham.get("onaylandi"))))
            except GecersizDegerHatasi as hata:
                raise GecersizDegerHatasi(f"{sira}. madde: {hata.mesaj}") from None
        return self._depo.maddeleri_degistir(kimlik, maddeler)

    def maddeleri_cikar(self, kimlik: int) -> CikarimRaporu:
        """
        Gemini ile belgeden maddeleri çıkarır ve mevcut maddelerin YERİNE kaydeder (hepsi onaylanmamış).

        Hatalar:
            GecersizDegerHatasi: Belgeden metin çıkmadıysa (taranmış belge).
            YapayZekaHatasi: Anahtar yok, sınır doldu veya istek başarısız.
        """
        self._depo.getir(kimlik)
        metin = self._depo.metin(kimlik)
        if not metin:
            raise GecersizDegerHatasi(
                "Bu belgeden metin okunamadı (taranmış/resim PDF olabilir). Maddeleri tabloya elle ekleyin."
            )
        yanit = self._yz.istek(SISTEM_TALIMATI, istem_olustur(metin), madde_semasi())
        if not isinstance(yanit.veri.get("maddeler"), list):
            raise YapayZekaHatasi("Gemini beklenen biçimde madde listesi döndürmedi. Tekrar deneyin.")
        sonuc = self._donusturucu.donustur(yanit.veri["maddeler"])
        kaydedilen = self._depo.maddeleri_degistir(kimlik, sonuc.maddeler)
        return CikarimRaporu(kaydedilen, sonuc.atlanan, yanit.bugun_kullanilan, yanit.gunluk_sinir)

    # ---------- Drone ----------

    def bagla(self, drone_kimlik: int, sartname_kimlik: int) -> Sartname:
        """Kütüphanedeki şartnameyi drone'a bağlar (öncekinin yerine)."""
        self._elektronik.drone_getir(drone_kimlik)
        self._depo.bagla(drone_kimlik, sartname_kimlik)
        return self._depo.getir(sartname_kimlik)

    def bagi_kaldir(self, drone_kimlik: int) -> None:
        """Drone'un şartnamesini kaldırır; şartname kütüphanede kalır."""
        self._elektronik.drone_getir(drone_kimlik)
        self._depo.bagi_kaldir(drone_kimlik)

    def rapor(self, drone_kimlik: int) -> DroneSartnameRaporu:
        """
        Drone'un şartnamesine göre madde madde uyum raporu.

        Hatalar:
            KayitBulunamadiHatasi: Drone yoksa.
        """
        self._elektronik.drone_getir(drone_kimlik)
        sartname = self._depo.drone_sartnamesi(drone_kimlik)
        if sartname is None:
            return DroneSartnameRaporu(None)
        maddeler = self._depo.maddeler(sartname.kimlik)
        return DroneSartnameRaporu(sartname, self._kontrol.kontrol_et(maddeler, self._baglam(drone_kimlik, maddeler)))

    def oneri_maddeleri(self, drone_kimlik: int) -> list[Madde]:
        """Öneride kullanılacak maddeler: drone'un şartnamesindeki onaylı kesin kurallar."""
        sartname = self._depo.drone_sartnamesi(drone_kimlik)
        if sartname is None:
            return []
        return [m for m in self._depo.maddeler(sartname.kimlik) if m.onaylandi and m.sinif is MaddeSinifi.KESIN]

    def _baglam(self, drone_kimlik: int, maddeler: list[Madde]) -> SartnameBaglami:
        ozet = self._elektronik.ozet(drone_kimlik)
        baglam = SartnameBaglami(
            kalemler=ozet.parca_adetleri, motor_sayisi=ozet.drone.motor_sayisi, sasi_olculeri=ozet.sasi_olculeri,
            agirlik=ozet.agirlik, ucus=ozet.ucus, hedefler=ozet.hedefler,
        )
        # Maliyet yalnızca gerekiyorsa hesaplanır; yabancı fiyat varsa kur için internete çıkabilir.
        if any(m.buyukluk is Buyukluk.MALIYET for m in maddeler):
            toplam = self._maliyet.ozet(drone_kimlik).ozet.toplamlar["toplam"]
            baglam.maliyet_tl = toplam.tl
            baglam.maliyet_eksik = toplam.eksik_kalem_sayisi > 0
            baglam.maliyet_tahmini = toplam.tahmini
        return baglam
