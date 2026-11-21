"""
Çekirdek uyum kontrolleri K1–K13 (docs/elektronik_plani.md bölüm 5.1).

Her kontrol ayrı bir sınıftır. Drone'da aynı türden birden çok model varsa
(ör. iki farklı pil) her çift ayrı denetlenir; sonuç en kötü çiftin sonucudur.
Eşikler elektronik/hesap/katsayilar.py dosyasındadır.
"""

from typing import Final

from elektronik.hesap.akim import EnBuyukAkimHesaplayici
from elektronik.hesap.katsayilar import (
    ESC_AKIM_PAYI,
    GERILIM_TOLERANSI_V,
    MAH_AH,
    MONTAJ_TOLERANSI_MM,
    PERVANE_SINIR_YAKINLIGI_INC,
    PIL_AKIM_PAYI,
    UART_ISTEYEN_BAGLANTILAR,
    YUZDE,
)
from elektronik.hesap.pil_gerilimi import PilGerilimiHesaplayici
from elektronik.hesap.sasi_pervane import EnBuyukPervaneTahmincisi
from elektronik.hesap.uyum import (
    AraSonuc,
    KontrolBaglami,
    UyumDurumu as D,
    UyumKontrolu,
    aralik_durumu,
    eksik_mesaji,
    metni_karsilastirmaya_hazirla as sade,
    sayi_yaz,
)
from elektronik.parcalar.cekirdek_parcalar import Alici, Esc, GucDagitim, Motor, Pervane, Pil, UcusKarti
from elektronik.parcalar.diger_parca import DigerParca
from elektronik.parcalar.parca import Parca
from elektronik.parcalar.turler import DigerAltTur

# DEĞİŞTİRİLEBİLİR: Bu alt türlerdeki parçalar uçuş kartında birer UART kullanır (K10'da alıcıyla birlikte sayılır).
UART_KULLANAN_ALT_TURLER: Final[frozenset[DigerAltTur]] = frozenset({DigerAltTur.GPS, DigerAltTur.TELEMETRI})


def _yuzde(oran: float) -> str:
    """0,2 → "%20"."""
    return f"%{sayi_yaz(oran * YUZDE)}"


def besleme_cikislari(baglam: KontrolBaglami) -> tuple[list[float], bool]:
    """
    Drone'daki regülatör (BEC) çıkış gerilimleri: uçuş kartı ve güç dağıtım kartı.

    Dönüş:
        (bilinen çıkışlar V, çıkışı girilmemiş kaynak var mı).
    """
    cikislar: list[float] = []
    bilinmeyen = False
    kaynaklar = [(fc, fc.bec_cikislari_v) for fc in baglam.parcalar(UcusKarti)]
    kaynaklar += [(pdb, pdb.cikis_gerilimleri_v) for pdb in baglam.parcalar(GucDagitim)]
    for _, liste in kaynaklar:
        if liste is None:
            bilinmeyen = True
        else:
            cikislar += liste
    return cikislar, bilinmeyen


def gerilim_beslenebilir_mi(gerilim_v: float, baglam: KontrolBaglami) -> AraSonuc:
    """Verilen besleme gerilimini sağlayan bir BEC çıkışı var mı (K10 ve K13 ortak)."""
    cikislar, bilinmeyen = besleme_cikislari(baglam)
    if any(abs(c - gerilim_v) <= GERILIM_TOLERANSI_V for c in cikislar):
        return AraSonuc(D.UYGUN, f"{sayi_yaz(gerilim_v)} V çıkış mevcut")
    if bilinmeyen or not cikislar:
        return AraSonuc(D.BILINMIYOR, f"{sayi_yaz(gerilim_v)} V gerekiyor; uçuş kartı / PDB çıkış gerilimleri girilmemiş")
    mevcut = "; ".join(sayi_yaz(c) for c in cikislar)
    return AraSonuc(D.UYGUNSUZ, f"{sayi_yaz(gerilim_v)} V çıkış yok (mevcut: {mevcut} V)")


# ---------- K1, K2: hücre sayısı ----------


class _HucreAraligiKontrolu(UyumKontrolu):
    """Pilin hücre sayısı hedef parçanın (motor/ESC) desteklediği aralıkta mı."""

    HEDEF: type[Motor] | type[Esc] = Motor
    HEDEF_ADI: str = ""

    def _kontrol_et(self, baglam: KontrolBaglami) -> list[AraSonuc]:
        piller, hedefler = baglam.parcalar(Pil), baglam.parcalar(self.HEDEF)
        if not piller or not hedefler:
            return self._eklenmedi("Pil", self.HEDEF_ADI)
        sonuclar = []
        for pil in piller:
            for hedef in hedefler:
                ilgili = (pil.gorunen_ad, hedef.gorunen_ad)
                durum = aralik_durumu(pil.hucre_sayisi_s, hedef.min_s, hedef.maks_s)
                aralik = f"{sayi_yaz(hedef.min_s)}–{sayi_yaz(hedef.maks_s)}S"
                if pil.hucre_sayisi_s is None:
                    mesaj = eksik_mesaji(pil, "hucre_sayisi_s")
                elif durum is D.UYGUNSUZ:
                    mesaj = f"{pil.hucre_sayisi_s}S pil, {hedef.gorunen_ad} yalnızca {aralik} destekliyor"
                elif durum is D.BILINMIYOR:
                    mesaj = eksik_mesaji(hedef, "min_s", "maks_s")
                else:
                    mesaj = f"{pil.hucre_sayisi_s}S pil, {hedef.gorunen_ad} aralığında ({aralik})"
                sonuclar.append(AraSonuc(durum, mesaj, ilgili))
        return sonuclar


class PilMotorHucreKontrolu(_HucreAraligiKontrolu):
    """K1: Pil hücre sayısı motorun desteklediği aralıkta."""

    KOD, BASLIK = "K1", "Pil ↔ motor (hücre sayısı)"
    HEDEF, HEDEF_ADI = Motor, "motor"


class PilEscHucreKontrolu(_HucreAraligiKontrolu):
    """K2: Pil hücre sayısı ESC'nin desteklediği aralıkta."""

    KOD, BASLIK = "K2", "Pil ↔ ESC (hücre sayısı)"
    HEDEF, HEDEF_ADI = Esc, "ESC"


# ---------- K3: pil gerilimi ↔ FC / PDB girişi ----------


class PilGirisGerilimiKontrolu(UyumKontrolu):
    """
    K3: Dolu pil gerilimi FC/PDB'nin en yüksek girişini aşmıyor; nominal gerilim FC'nin
    en düşük girişinin altında değil.

    Pil kimyası girilmemişse tahmin edilmez; olası bütün kimyalar denenir.
    """

    KOD, BASLIK = "K3", "Pil ↔ uçuş kartı / PDB (giriş gerilimi)"

    def __init__(self) -> None:
        self._gerilim = PilGerilimiHesaplayici()

    def _kontrol_et(self, baglam: KontrolBaglami) -> list[AraSonuc]:
        piller = baglam.parcalar(Pil)
        hedefler: list[UcusKarti | GucDagitim] = [*baglam.parcalar(UcusKarti), *baglam.parcalar(GucDagitim)]
        if not piller or not hedefler:
            return self._eklenmedi("Pil", "uçuş kartı veya PDB")
        sonuclar = []
        for pil in piller:
            for hedef in hedefler:
                sonuclar += self._cift(pil, hedef)
        return sonuclar

    def _cift(self, pil: Pil, hedef: UcusKarti | GucDagitim) -> list[AraSonuc]:
        ilgili = (pil.gorunen_ad, hedef.gorunen_ad)
        dolu, nominal = self._gerilim.dolu(pil), self._gerilim.nominal(pil)
        if dolu is None or nominal is None:
            return [AraSonuc(D.BILINMIYOR, eksik_mesaji(pil, "hucre_sayisi_s"), ilgili)]
        maks = hedef.giris_gerilimi_maks_v
        en_az = hedef.giris_gerilimi_min_v if isinstance(hedef, UcusKarti) else None
        sonuclar = []

        if maks is None:
            sonuclar.append(AraSonuc(D.BILINMIYOR, eksik_mesaji(hedef, "giris_gerilimi_maks_v"), ilgili))
        elif dolu.en_dusuk_v > maks:
            sonuclar.append(AraSonuc(
                D.UYGUNSUZ, f"Dolu pil {sayi_yaz(dolu.en_dusuk_v)} V, {hedef.gorunen_ad} en çok {sayi_yaz(maks)} V", ilgili
            ))
        elif dolu.en_yuksek_v > maks:
            sonuclar.append(AraSonuc(
                D.BILINMIYOR,
                f"Pil kimyası girilmemiş: LiHV ise dolu gerilim {sayi_yaz(dolu.en_yuksek_v)} V, "
                f"{hedef.gorunen_ad} en çok {sayi_yaz(maks)} V",
                ilgili,
            ))
        else:
            sonuclar.append(AraSonuc(
                D.UYGUN, f"Dolu pil en çok {sayi_yaz(dolu.en_yuksek_v)} V ≤ {sayi_yaz(maks)} V ({hedef.gorunen_ad})", ilgili
            ))

        if isinstance(hedef, UcusKarti):
            if en_az is None:
                sonuclar.append(AraSonuc(D.BILINMIYOR, eksik_mesaji(hedef, "giris_gerilimi_min_v"), ilgili))
            elif nominal.en_yuksek_v < en_az:
                sonuclar.append(AraSonuc(
                    D.UYGUNSUZ, f"Pil {sayi_yaz(nominal.en_yuksek_v)} V, {hedef.gorunen_ad} en az {sayi_yaz(en_az)} V istiyor", ilgili
                ))
            elif nominal.en_dusuk_v < en_az:
                sonuclar.append(AraSonuc(
                    D.BILINMIYOR, f"Pil kimyası girilmemiş: nominal gerilim {sayi_yaz(en_az)} V sınırına çok yakın", ilgili
                ))
        return sonuclar


# ---------- K4: motor ↔ pervane ----------


class MotorPervaneKontrolu(UyumKontrolu):
    """
    K4: Pervane çapı motorun önerilen pervane aralığında.

    Önerilen aralık girilmemişse stator boyutundan tahmin YAPILMAZ (kullanıcı kararı);
    sonuç "bilinmiyor" olur.
    """

    KOD, BASLIK = "K4", "Motor ↔ pervane (çap)"

    def _kontrol_et(self, baglam: KontrolBaglami) -> list[AraSonuc]:
        motorlar, pervaneler = baglam.parcalar(Motor), baglam.parcalar(Pervane)
        if not motorlar or not pervaneler:
            return self._eklenmedi("Motor", "pervane")
        sonuclar = []
        for motor in motorlar:
            for pervane in pervaneler:
                ilgili = (motor.gorunen_ad, pervane.gorunen_ad)
                alt, ust = motor.onerilen_pervane_min_inc, motor.onerilen_pervane_maks_inc
                durum = aralik_durumu(pervane.cap_inc, alt, ust)
                aralik = f"{sayi_yaz(alt)}–{sayi_yaz(ust)} inç"
                if pervane.cap_inc is None:
                    mesaj = eksik_mesaji(pervane, "cap_inc")
                elif durum is D.UYGUNSUZ:
                    mesaj = f"{sayi_yaz(pervane.cap_inc)} inç pervane, motor için önerilen {aralik}"
                elif durum is D.BILINMIYOR:
                    mesaj = eksik_mesaji(motor, "onerilen_pervane_min_inc", "onerilen_pervane_maks_inc")
                else:
                    mesaj = f"{sayi_yaz(pervane.cap_inc)} inç pervane önerilen aralıkta ({aralik})"
                sonuclar.append(AraSonuc(durum, mesaj, ilgili))
        return sonuclar


# ---------- K5: pervane ↔ şasi (tahmini) ----------


class PervaneSasiKontrolu(UyumKontrolu):
    """K5: Pervane, şasi ölçüsünden tahmin edilen en büyük pervaneyi aşmıyor. Sonuç her zaman tahminidir."""

    KOD, BASLIK = "K5", "Pervane ↔ şasi (tahmini)"
    TAHMINI = True

    def __init__(self, tahminci: EnBuyukPervaneTahmincisi | None = None) -> None:
        self._tahminci = tahminci or EnBuyukPervaneTahmincisi()

    def _kontrol_et(self, baglam: KontrolBaglami) -> list[AraSonuc]:
        pervaneler = baglam.parcalar(Pervane)
        if not pervaneler:
            return self._eklenmedi("Pervane")
        if baglam.sasi_olculeri is None:
            return [AraSonuc(D.BILINMIYOR, "Şasi dosyası yüklenmedi veya birimi onaylanmadı (Şasi sekmesi).")]
        sinir = self._tahminci.tahmin_et(baglam.sasi_olculeri, baglam.motor_sayisi)
        if sinir is None:
            return [AraSonuc(D.UYARI, "Şasi ölçüsü pervane sığdırmak için çok küçük görünüyor; ölçüleri kontrol edin.")]
        sonuclar = []
        for pervane in pervaneler:
            ilgili = (pervane.gorunen_ad,)
            cap = pervane.cap_inc
            if cap is None:
                sonuclar.append(AraSonuc(D.BILINMIYOR, eksik_mesaji(pervane, "cap_inc"), ilgili))
            elif cap > sinir + PERVANE_SINIR_YAKINLIGI_INC:
                sonuclar.append(AraSonuc(
                    D.UYGUNSUZ, f"{sayi_yaz(cap)} inç pervane, şasiye sığacak en büyük ≈ {sayi_yaz(sinir)} inç", ilgili
                ))
            elif cap > sinir - PERVANE_SINIR_YAKINLIGI_INC:
                sonuclar.append(AraSonuc(
                    D.UYARI,
                    f"{sayi_yaz(cap)} inç pervane, tahmini sınıra (≈ {sayi_yaz(sinir)} inç) çok yakın; şasi üzerinde ölçün",
                    ilgili,
                ))
            else:
                sonuclar.append(AraSonuc(D.UYGUN, f"{sayi_yaz(cap)} inç pervane, tahmini sınır ≈ {sayi_yaz(sinir)} inç", ilgili))
        return sonuclar


# ---------- K6, K7: akım ----------


def _akim_karsilastir(kapasite_a: float, gereken_a: float, pay: float, ad: str, ilgili: tuple[str, ...]) -> AraSonuc:
    """Akım kapasitesini güvenlik paylı gereken akımla karşılaştırır."""
    payli = gereken_a * (1 + pay)
    if kapasite_a >= payli:
        return AraSonuc(D.UYGUN, f"{ad} {sayi_yaz(kapasite_a)} A ≥ {sayi_yaz(payli)} A ({_yuzde(pay)} paylı)", ilgili)
    if kapasite_a >= gereken_a:
        return AraSonuc(
            D.UYARI,
            f"{ad} {sayi_yaz(kapasite_a)} A, gereken {sayi_yaz(gereken_a)} A'yı karşılıyor ama "
            f"{_yuzde(pay)} güvenlik payıyla {sayi_yaz(payli)} A olmalı",
            ilgili,
        )
    return AraSonuc(D.UYGUNSUZ, f"{ad} {sayi_yaz(kapasite_a)} A, gereken en az {sayi_yaz(gereken_a)} A", ilgili)


class EscAkimKontrolu(UyumKontrolu):
    """K6: ESC sürekli akımı ≥ motorun en büyük akımı × (1 + güvenlik payı)."""

    KOD, BASLIK = "K6", "ESC ↔ motor akımı"

    def __init__(self, pay: float = ESC_AKIM_PAYI) -> None:
        self.pay = pay

    def _kontrol_et(self, baglam: KontrolBaglami) -> list[AraSonuc]:
        escler, motorlar = baglam.parcalar(Esc), baglam.parcalar(Motor)
        if not escler or not motorlar:
            return self._eklenmedi("ESC", "motor")
        sonuclar = []
        for esc in escler:
            for motor in motorlar:
                ilgili = (esc.gorunen_ad, motor.gorunen_ad)
                eksik = eksik_mesaji(esc, "surekli_akim_a") or eksik_mesaji(motor, "maks_akim_a")
                if eksik:
                    sonuclar.append(AraSonuc(D.BILINMIYOR, eksik, ilgili))
                else:
                    sonuclar.append(_akim_karsilastir(esc.surekli_akim_a, motor.maks_akim_a, self.pay, "ESC kanal akımı", ilgili))
        return sonuclar


class PilAkimKontrolu(UyumKontrolu):
    """K7: Pilin sürekli akımı (Ah × C) ≥ toplam en büyük akım × (1 + güvenlik payı)."""

    KOD, BASLIK = "K7", "Pil ↔ toplam akım (deşarj)"

    def __init__(self, pay: float = PIL_AKIM_PAYI) -> None:
        self.pay = pay
        self._akim = EnBuyukAkimHesaplayici()

    def _kontrol_et(self, baglam: KontrolBaglami) -> list[AraSonuc]:
        piller = baglam.parcalar(Pil)
        if not piller:
            return self._eklenmedi("Pil")
        toplam = self._akim.hesapla(baglam.kalemler, baglam.motor_sayisi)
        if toplam.toplam_a is None:
            return [AraSonuc(D.BILINMIYOR, f"Toplam akım hesaplanamadı: {toplam.eksik}.")]
        sonuclar = []
        for pil in piller:
            ilgili = (pil.gorunen_ad,)
            eksik = eksik_mesaji(pil, "kapasite_mah", "desarj_c")
            if eksik:
                sonuclar.append(AraSonuc(D.BILINMIYOR, eksik, ilgili))
                continue
            pil_akimi = pil.kapasite_mah / MAH_AH * pil.desarj_c
            sonuclar.append(_akim_karsilastir(pil_akimi, toplam.toplam_a, self.pay, "Pil sürekli akımı", ilgili))
        return sonuclar


# ---------- K8, K9: FC ↔ ESC ----------


class FcEscMontajKontrolu(UyumKontrolu):
    """
    K8: 4'ü 1 arada ESC ile uçuş kartı aynı yığına (stack) takılıyorsa montaj ölçüleri aynı.

    Tekli ESC'ler kollara takıldığı için bu kontrol onlarda gerekmez.
    """

    KOD, BASLIK = "K8", "Uçuş kartı ↔ ESC (montaj ölçüsü)"

    def _kontrol_et(self, baglam: KontrolBaglami) -> list[AraSonuc]:
        fcler, escler = baglam.parcalar(UcusKarti), baglam.parcalar(Esc)
        if not fcler or not escler:
            return self._eklenmedi("Uçuş kartı", "ESC")
        sonuclar = []
        for fc in fcler:
            for esc in escler:
                ilgili = (fc.gorunen_ad, esc.gorunen_ad)
                if esc.kanal_sayisi == 1:
                    sonuclar.append(AraSonuc(D.UYGUN, "Tekli ESC kollara takılır; yığın montajı gerekmez", ilgili))
                    continue
                eksik = eksik_mesaji(fc, "montaj_olcusu_mm") or eksik_mesaji(esc, "montaj_olcusu_mm")
                if eksik:
                    sonuclar.append(AraSonuc(D.BILINMIYOR, eksik, ilgili))
                    continue
                olculer = f"{sayi_yaz(fc.montaj_olcusu_mm)} mm ve {sayi_yaz(esc.montaj_olcusu_mm)} mm"
                if abs(fc.montaj_olcusu_mm - esc.montaj_olcusu_mm) <= MONTAJ_TOLERANSI_MM:
                    sonuclar.append(AraSonuc(D.UYGUN, f"Montaj ölçüleri aynı ({sayi_yaz(fc.montaj_olcusu_mm)} mm)", ilgili))
                elif esc.kanal_sayisi is None:
                    sonuclar.append(AraSonuc(
                        D.BILINMIYOR, f"Montaj ölçüleri farklı ({olculer}); ESC tekli ise sorun yok, kanal sayısını girin", ilgili
                    ))
                else:
                    sonuclar.append(AraSonuc(
                        D.UYGUNSUZ, f"Montaj ölçüleri farklı ({olculer}); aynı yığına ancak ara plakayla takılır", ilgili
                    ))
        return sonuclar


class FcEscProtokolKontrolu(UyumKontrolu):
    """K9: ESC'nin desteklediği protokollerden en az biri uçuş kartında da destekleniyor."""

    KOD, BASLIK = "K9", "Uçuş kartı ↔ ESC (sinyal protokolü)"

    def _kontrol_et(self, baglam: KontrolBaglami) -> list[AraSonuc]:
        fcler, escler = baglam.parcalar(UcusKarti), baglam.parcalar(Esc)
        if not fcler or not escler:
            return self._eklenmedi("Uçuş kartı", "ESC")
        sonuclar = []
        for fc in fcler:
            for esc in escler:
                ilgili = (fc.gorunen_ad, esc.gorunen_ad)
                eksik = eksik_mesaji(fc, "esc_protokolleri") or eksik_mesaji(esc, "protokoller")
                if eksik:
                    sonuclar.append(AraSonuc(D.BILINMIYOR, eksik, ilgili))
                    continue
                fc_sade = {sade(p) for p in fc.esc_protokolleri}
                ortak = [p for p in esc.protokoller if sade(p) in fc_sade]
                if ortak:
                    sonuclar.append(AraSonuc(D.UYGUN, f"Ortak protokol: {', '.join(ortak)}", ilgili))
                else:
                    sonuclar.append(AraSonuc(
                        D.UYGUNSUZ,
                        f"Ortak protokol yok (ESC: {', '.join(esc.protokoller)}; kart: {', '.join(fc.esc_protokolleri)})",
                        ilgili,
                    ))
        return sonuclar


# ---------- K10: alıcı ↔ FC ----------


class AliciFcKontrolu(UyumKontrolu):
    """
    K10: Alıcı protokolü uçuş kartında destekleniyor, alıcı için boş UART var ve
    alıcının besleme gerilimi bir BEC çıkışıyla uyumlu.
    """

    KOD, BASLIK = "K10", "Alıcı ↔ uçuş kartı"

    def _kontrol_et(self, baglam: KontrolBaglami) -> list[AraSonuc]:
        alicilar, fcler = baglam.parcalar(Alici), baglam.parcalar(UcusKarti)
        if not alicilar or not fcler:
            return self._eklenmedi("Alıcı", "uçuş kartı")
        sonuclar = []
        for alici in alicilar:
            for fc in fcler:
                ilgili = (alici.gorunen_ad, fc.gorunen_ad)
                sonuclar += [
                    self._protokol(alici, fc, ilgili),
                    self._uart(alici, fc, baglam, ilgili),
                    self._besleme(alici, baglam, ilgili),
                ]
        return sonuclar

    @staticmethod
    def _protokol(alici: Alici, fc: UcusKarti, ilgili: tuple[str, ...]) -> AraSonuc:
        eksik = eksik_mesaji(alici, "protokol") or eksik_mesaji(fc, "alici_protokolleri")
        if eksik:
            return AraSonuc(D.BILINMIYOR, eksik, ilgili)
        if sade(alici.protokol) in {sade(p) for p in fc.alici_protokolleri}:
            return AraSonuc(D.UYGUN, f"{alici.protokol} protokolü kartta destekleniyor", ilgili)
        return AraSonuc(
            D.UYGUNSUZ, f"{alici.protokol} protokolü kartta yok (kart: {', '.join(fc.alici_protokolleri)})", ilgili
        )

    @staticmethod
    def _uart(alici: Alici, fc: UcusKarti, baglam: KontrolBaglami, ilgili: tuple[str, ...]) -> AraSonuc:
        # Bağlantı şekli girilmişse o, girilmemişse protokol adı UART gerekip gerekmediğini söyler (CRSF → UART).
        ipucu = alici.baglanti or alici.protokol
        if ipucu is None:
            return AraSonuc(D.BILINMIYOR, eksik_mesaji(alici, "baglanti"), ilgili)
        if sade(ipucu) not in UART_ISTEYEN_BAGLANTILAR:
            return AraSonuc(D.UYGUN, f"{ipucu} bağlantısı için ayrı UART gerekmiyor", ilgili)
        diger = sum(
            adet for p, adet in baglam.kalemler if isinstance(p, DigerParca) and p.alt_tur in UART_KULLANAN_ALT_TURLER
        )
        gereken = 1 + diger
        if fc.uart_sayisi is None:
            return AraSonuc(D.BILINMIYOR, eksik_mesaji(fc, "uart_sayisi"), ilgili)
        if fc.uart_sayisi >= gereken:
            return AraSonuc(D.UYGUN, f"UART yeterli ({gereken} gerekli, kartta {fc.uart_sayisi})", ilgili)
        return AraSonuc(
            D.UYGUNSUZ, f"Alıcı ve GPS/telemetri için {gereken} UART gerekli, kartta {fc.uart_sayisi} var", ilgili
        )

    @staticmethod
    def _besleme(alici: Alici, baglam: KontrolBaglami, ilgili: tuple[str, ...]) -> AraSonuc:
        if alici.besleme_gerilimi_v is None:
            return AraSonuc(D.BILINMIYOR, eksik_mesaji(alici, "besleme_gerilimi_v"), ilgili)
        sonuc = gerilim_beslenebilir_mi(alici.besleme_gerilimi_v, baglam)
        return AraSonuc(sonuc.durum, f"Alıcı beslemesi: {sonuc.aciklama}", ilgili)


# ---------- K11: motor sayısı ----------


class MotorSayisiKontrolu(UyumKontrolu):
    """K11: Eklenen motor sayısı drone türüyle uyumlu; farklı motor modelleri karışmamış."""

    KOD, BASLIK = "K11", "Motor sayısı"

    def _kontrol_et(self, baglam: KontrolBaglami) -> list[AraSonuc]:
        adet, gereken = baglam.adet(Motor), baglam.motor_sayisi
        modeller = baglam.parcalar(Motor)
        if adet < gereken:
            return [AraSonuc(D.UYGUNSUZ, f"{adet}/{gereken} motor – {gereken - adet} eksik")]
        sonuclar = []
        if adet > gereken:
            sonuclar.append(AraSonuc(D.UYARI, f"{adet} motor eklendi, drone türü {gereken} motor kullanır (yedekse sorun yok)"))
        if len(modeller) > 1:
            sonuclar.append(AraSonuc(
                D.UYARI,
                "Farklı motor modelleri karışık; dengeli uçuş için hepsi aynı model olmalı",
                tuple(m.gorunen_ad for m in modeller),
            ))
        return sonuclar or [AraSonuc(D.UYGUN, f"{adet}/{gereken} motor")]


# ---------- K12: konnektör ----------


class KonnektorKontrolu(UyumKontrolu):
    """
    K12: Pil konnektörü, pilin takıldığı parçanınkiyle aynı. Farklıysa ✗ değil ⚠,
    çünkü konnektör değiştirilebilir veya ara kablo kullanılabilir.

    Pil, PDB varsa PDB'ye; yoksa 4'ü 1 arada ESC'ye bağlanır.
    """

    KOD, BASLIK = "K12", "Pil konnektörü"

    def _kontrol_et(self, baglam: KontrolBaglami) -> list[AraSonuc]:
        piller = baglam.parcalar(Pil)
        hedefler: list[GucDagitim | Esc] = list(baglam.parcalar(GucDagitim))
        if not hedefler:
            escler = baglam.parcalar(Esc)
            # Tekli ESC'ler pile doğrudan değil, dağıtım üzerinden bağlanır; yalnızca onlar varsa hepsine bakılır.
            hedefler = [e for e in escler if e.kanal_sayisi != 1] or escler
        if not piller or not hedefler:
            return self._eklenmedi("Pil", "ESC veya PDB")
        sonuclar = []
        for pil in piller:
            for hedef in hedefler:
                ilgili = (pil.gorunen_ad, hedef.gorunen_ad)
                eksik = eksik_mesaji(pil, "konnektor") or eksik_mesaji(hedef, "konnektor")
                if eksik:
                    sonuclar.append(AraSonuc(D.BILINMIYOR, eksik, ilgili))
                elif sade(pil.konnektor) == sade(hedef.konnektor):
                    sonuclar.append(AraSonuc(D.UYGUN, f"İkisi de {pil.konnektor}", ilgili))
                else:
                    sonuclar.append(AraSonuc(
                        D.UYARI,
                        f"Pil {pil.konnektor}, {hedef.gorunen_ad} {hedef.konnektor}: konnektör değişimi veya ara kablo gerekir",
                        ilgili,
                    ))
        return sonuclar


# ---------- K13: ikinci grup gerilim ----------


class IkinciGrupGerilimKontrolu(UyumKontrolu):
    """K13: Kamera, VTX, GPS gibi parçaların besleme gerilimi bir BEC çıkışıyla uyumlu."""

    KOD, BASLIK = "K13", "Kamera / VTX / GPS besleme gerilimi"

    def _kontrol_et(self, baglam: KontrolBaglami) -> list[AraSonuc]:
        parcalar: list[Parca] = list(baglam.parcalar(DigerParca))
        if not parcalar:
            return [AraSonuc(D.UYGUN, "Kontrol edilecek ikinci grup parça (kamera, VTX, GPS…) yok")]
        sonuclar = []
        for parca in parcalar:
            ilgili = (parca.gorunen_ad,)
            if parca.besleme_gerilimi_v is None:
                sonuclar.append(AraSonuc(D.BILINMIYOR, eksik_mesaji(parca, "besleme_gerilimi_v"), ilgili))
                continue
            sonuc = gerilim_beslenebilir_mi(parca.besleme_gerilimi_v, baglam)
            sonuclar.append(AraSonuc(sonuc.durum, f"{parca.gorunen_ad}: {sonuc.aciklama}", ilgili))
        return sonuclar
