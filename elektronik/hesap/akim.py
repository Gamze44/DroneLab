"""
Toplam en büyük akımın hesabı (pil deşarj kontrolü K7 ve uçuş özeti kullanır).

Toplam en büyük akım = motor sayısı × motorun en büyük akımı. Kamera, VTX gibi
diğer tüketicilerin akımı motorların yanında çok küçük kaldığı ve çoğu zaman
bilinmediği için katılmaz; bu durum açıklamada yazılır.
"""

from dataclasses import dataclass

from elektronik.parcalar.cekirdek_parcalar import Motor
from elektronik.parcalar.parca import Parca


@dataclass(frozen=True)
class AkimSonucu:
    """
    Toplam en büyük akım hesabının sonucu.

    Alanlar:
        toplam_a: Toplam en büyük akım, A; hesaplanamadıysa None.
        eksik: Hesaplanamadıysa nedeni (Türkçe).
    """

    toplam_a: float | None
    eksik: str | None = None


class EnBuyukAkimHesaplayici:
    """Drone'daki motorların toplam en büyük akımını (A) hesaplar."""

    def hesapla(self, kalemler: list[tuple[Parca, int]], motor_sayisi: int) -> AkimSonucu:
        """
        Toplam en büyük akımı hesaplar.

        Farklı motor modelleri varsa her biri kendi adediyle sayılır. Drone'daki motor
        sayısı türün gerektirdiğinden azsa toplam eksik çıkacağı için hesaplanmaz.

        Parametreler:
            kalemler: (parça, adet) listesi.
            motor_sayisi: Drone türüne göre motor sayısı.
        Dönüş:
            AkimSonucu.
        """
        motorlar = [(p, adet) for p, adet in kalemler if isinstance(p, Motor)]
        if not motorlar:
            return AkimSonucu(None, "motor eklenmedi")
        eksikler = [p.gorunen_ad for p, _ in motorlar if p.maks_akim_a is None]
        if eksikler:
            return AkimSonucu(None, f"{', '.join(eksikler)}: en büyük akım girilmemiş")
        adet = sum(a for _, a in motorlar)
        if adet < motor_sayisi:
            return AkimSonucu(None, f"{motor_sayisi} motor gerekiyor, {adet} eklendi")
        if len(motorlar) == 1:
            # Tek model varsa fazladan eklenen (yedek) motorlar uçuşta akım çekmez.
            return AkimSonucu(motorlar[0][0].maks_akim_a * motor_sayisi)
        return AkimSonucu(sum(p.maks_akim_a * a for p, a in motorlar))
