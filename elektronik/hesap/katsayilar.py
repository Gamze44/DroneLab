"""
Uyum kontrolleri ve uçuş hesaplarının tüm eşik ve katsayıları.

Değerler docs/elektronik_plani.md bölüm 5'teki varsayılanlardır. Hepsi tek
dosyada durur ki proje sahibi hesabı kodun içine girmeden ayarlayabilsin.
"""

from typing import Final

from elektronik.parcalar.turler import PilKimyasi

# ---------- Pil hücre gerilimleri (V / hücre) ----------

# DEĞİŞTİRİLEBİLİR: Tam dolu hücre gerilimi; FC/PDB'nin en yüksek giriş gerilimiyle karşılaştırılır (K3).
DOLU_HUCRE_GERILIMI_V: Final[dict[PilKimyasi, float]] = {
    PilKimyasi.LIPO: 4.20,
    PilKimyasi.LIHV: 4.35,
    PilKimyasi.LIION: 4.20,
}

# DEĞİŞTİRİLEBİLİR: Nominal (ortalama) hücre gerilimi; en düşük giriş gerilimi ve hesaplarda kullanılır.
NOMINAL_HUCRE_GERILIMI_V: Final[dict[PilKimyasi, float]] = {
    PilKimyasi.LIPO: 3.70,
    PilKimyasi.LIHV: 3.80,
    PilKimyasi.LIION: 3.60,
}

# DEĞİŞTİRİLEBİLİR: Kimyası girilmemiş pil için UÇUŞ HESABINDA kullanılan nominal hücre gerilimi.
# Kimyalar arası fark %5'ten az olduğu için tahmini hesapta bu kabul edilir ve ekranda yazılır.
# Uyum kontrollerinde (K3) bu kabul YAPILMAZ; orada bütün kimyalar denenir.
VARSAYILAN_NOMINAL_HUCRE_GERILIMI_V: Final[float] = 3.70

# ---------- Güvenlik payları ----------

# DEĞİŞTİRİLEBİLİR: ESC sürekli akımı, motorun en büyük akımından bu oran kadar fazla olmalı (K6).
ESC_AKIM_PAYI: Final[float] = 0.20

# DEĞİŞTİRİLEBİLİR: Pilin sürekli akımı (Ah × C), toplam en büyük akımdan bu oran kadar fazla olmalı (K7).
PIL_AKIM_PAYI: Final[float] = 0.20

# ---------- Karşılaştırma toleransları ----------

# DEĞİŞTİRİLEBİLİR: FC ve ESC montaj ölçüsü bu kadar farklıysa aynı sayılır (30,5 ile 30 gibi yazım farkları için).
MONTAJ_TOLERANSI_MM: Final[float] = 0.6

# DEĞİŞTİRİLEBİLİR: Bir parçanın besleme gerilimi bir BEC çıkışına bu kadar yakınsa uyumlu sayılır.
GERILIM_TOLERANSI_V: Final[float] = 0.3

# DEĞİŞTİRİLEBİLİR: Bu bağlantı adları kartta boş bir UART ister (K10).
UART_ISTEYEN_BAGLANTILAR: Final[frozenset[str]] = frozenset({"uart", "crsf", "elrs", "ibus", "fport"})

# ---------- Şasiden en büyük pervane tahmini (bölüm 5.4, K5) ----------

# DEĞİŞTİRİLEBİLİR: Sınır kutusu köşegeninin motor merkezleri arasına düşen oranı
# (kol uçları motor merkezinden biraz taşar).
DINGIL_KATSAYISI: Final[float] = 0.9

# DEĞİŞTİRİLEBİLİR: Komşu pervane uçları arasında bırakılacak boşluk, mm.
PERVANE_UC_BOSLUGU_MM: Final[float] = 6.0

# DEĞİŞTİRİLEBİLİR: Tahmini sınıra bu kadar yakın pervanelerde ✗ yerine ⚠ verilir (tahmin kaba olduğu için), inç.
PERVANE_SINIR_YAKINLIGI_INC: Final[float] = 0.5

# DEĞİŞTİRİLEBİLİR: Tahmin edilen en büyük pervane bu adıma aşağı yuvarlanır, inç.
PERVANE_YUVARLAMA_ADIMI_INC: Final[float] = 0.1

# ---------- Uçuş hesabı (bölüm 5.2) ----------

# DEĞİŞTİRİLEBİLİR: Pil kapasitesinin kullanılabilir kısmı (pili tamamen boşaltmak ömrünü kısaltır).
KULLANILABILIR_PIL_ORANI: Final[float] = 0.80

# DEĞİŞTİRİLEBİLİR: Amaca göre hedef itki/ağırlık oranı. Anahtarlar drone.modeller.KULLANIM_AMACLARI ile aynı olmalı.
HEDEF_ITKI_AGIRLIK: Final[dict[str, float]] = {
    "FPV yarış": 7.0,
    "Serbest uçuş (freestyle)": 5.0,
    "Hava fotoğrafı / video çekimi": 2.0,
    "Yük taşıma": 2.0,
}
# DEĞİŞTİRİLEBİLİR: Listede olmayan amaçlar için hedef (güvenli kalkış için en az 2 önerilir).
VARSAYILAN_HEDEF_ITKI_AGIRLIK: Final[float] = 2.0

# DEĞİŞTİRİLEBİLİR: Ortalama akım = asılı kalma akımı × bu katsayı (uçuş tarzı ne kadar sertse o kadar büyük).
UCUS_TARZI_KATSAYILARI: Final[dict[str, float]] = {
    "FPV yarış": 3.0,
    "Serbest uçuş (freestyle)": 2.0,
    "Hava fotoğrafı / video çekimi": 1.1,
    "Yük taşıma": 1.1,
}
# DEĞİŞTİRİLEBİLİR: Listede olmayan amaçlar için uçuş tarzı katsayısı.
VARSAYILAN_UCUS_TARZI_KATSAYISI: Final[float] = 2.0

# ---------- Tahmini itki ve güç (bölüm 5.3) ----------

# DEĞİŞTİRİLEBİLİR: Deniz seviyesinde hava yoğunluğu, kg/m3.
HAVA_YOGUNLUGU_KG_M3: Final[float] = 1.225

# DEĞİŞTİRİLEBİLİR: Yük altında motor devrinin, boştaki devre (KV × gerilim) oranı.
YUK_ALTINDA_DEVIR_ORANI: Final[float] = 0.80

# DEĞİŞTİRİLEBİLİR: Pervane itki katsayısı C_T, hatve/çap oranına göre (ara değerler doğrusal bulunur,
# tablonun dışı en yakın uca sabitlenir). Gerçek değer pervane biçimine göre değişir; sonuç tahminidir.
ITKI_KATSAYISI_TABLOSU: Final[tuple[tuple[float, float], ...]] = (
    (0.5, 0.08),
    (0.7, 0.10),
    (0.9, 0.12),
    (1.1, 0.14),
    (1.3, 0.15),
)

# DEĞİŞTİRİLEBİLİR: Pervane verim katsayısı (figure of merit); ideal pervanede 1.
PERVANE_VERIM_KATSAYISI: Final[float] = 0.65

# DEĞİŞTİRİLEBİLİR: Motor + ESC birlikte verimi.
MOTOR_ESC_VERIMI: Final[float] = 0.80

# Yüzde gösterimi için çarpan. Fizik sabitleri ve birim dönüşümleri (yerçekimi, mAh→Ah,
# saat→dakika, gram-kuvvet→newton) cekirdek/birimler.py'dedir.
YUZDE: Final[float] = 100.0
