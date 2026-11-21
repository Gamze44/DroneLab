"""
Asistanın ayarları ve sistem talimatı.

Model seçimi ve API anahtarı mevcut yapay zeka ayarlarından gelir (Ayarlar sayfası;
otomatik model seçimi arastirma/model_secici.py). Bu dosyada yalnızca asistana özgü
davranış ayarları durur.
"""

from typing import Final

# DEĞİŞTİRİLEBİLİR: Modele gönderilen son mesaj sayısı; daha eskileri kısa özet olarak gider.
GECMIS_MESAJ_SINIRI: Final[int] = 20
# DEĞİŞTİRİLEBİLİR: Özette eski kullanıcı sorularından en çok kaç tanesi ve kaç karakteri yer alır.
OZET_SORU_SAYISI: Final[int] = 8
OZET_SORU_UZUNLUGU: Final[int] = 120
# DEĞİŞTİRİLEBİLİR: Bir soruda modelin en çok kaç kez araç çağırabileceği (her tur bir istektir).
EN_FAZLA_ARAC_TURU: Final[int] = 4
# DEĞİŞTİRİLEBİLİR: Kullanıcı mesajının en çok uzunluğu (karakter).
EN_UZUN_MESAJ: Final[int] = 4000
# DEĞİŞTİRİLEBİLİR: Katalog aramasında modele verilen en çok sonuç.
KATALOG_SONUC_SINIRI: Final[int] = 10
# DEĞİŞTİRİLEBİLİR: Bir öneride en çok kaç değişiklik olabilir.
EN_FAZLA_DEGISIKLIK: Final[int] = 10
# DEĞİŞTİRİLEBİLİR: Ana sayfa bağlamında listelenen en çok drone sayısı.
BAGLAM_DRONE_SINIRI: Final[int] = 15

# Ekran anahtarı (arayüzden gelir) -> görünen ad. Bilinmeyen anahtar "Bilinmiyor" sayılır.
EKRAN_ADLARI: Final[dict[str, str]] = {
    "ana_sayfa": "Ana sayfa",
    "ayarlar": "Ayarlar",
    "sasi": "Şasi",
    "elektronik": "Elektronik",
    "hedefler": "Hedefler ve itki",
    "uyum": "Uyum kontrolleri",
    "ucus": "Uçuş hesabı",
    "maliyet": "Maliyet",
    "sartname": "Şartname",
}
BILINMEYEN_EKRAN: Final[str] = "Bilinmiyor"

# DEĞİŞTİRİLEBİLİR: Asistanın sistem talimatı. Bağlam (ekran ve drone özeti) program
# tarafından sona eklenir.
SISTEM_TALIMATI: Final[str] = """\
Sen DroneLab'in asistanısın. DroneLab, kullanıcının kendi bilgisayarında çalışan bir çok rotorlu
drone tasarım ve uygunluk programıdır (şasi, elektronik parçalar, uyum kontrolleri K1–K13, uçuş
hesabı, maliyet, yarışma şartnamesi).

Kurallar:
- Türkçe, kısa ve net yanıt ver. Kullanıcı mühendis düzeyinde teknik bilgiye sahiptir.
- Sayıları (ağırlık, itki, akım, süre, uyum sonucu vb.) YALNIZCA araç sonuçlarından ve aşağıdaki
  bağlamdan ver; kendin hesaplama ve tahmin etme. Bir araç sonucunda "tahmini": true veya
  "dogrulandi": false varsa bunu yanıtta açıkça belirt ("tahmini", "doğrulanmadı").
- Bilmediğin ya da araçlarla bulamadığın bilgiyi uydurma; bulamadığını açıkça söyle.
- Tasarımda değişiklik önermek için YALNIZCA degisiklik_oner aracını kullan. Bu araç değişikliği
  uygulamaz, kullanıcıya "Uygula / Vazgeç" kartı gösterir; asla "uyguladım" ya da "değiştirdim" deme.
  Önermeden önce senaryo_hesapla ile etkisini görebilirsin.
- Önerilerde yalnızca katalogdaki parçaları kullan (katalogda_ara). Katalogda olmayan bir parça
  gerekiyorsa kullanıcıyı Elektronik bölümündeki "Öner" düğmesine veya elle eklemeye yönlendir.
- Uçuş güvenliğini etkileyen konularda (pil, şarj, failsafe, uçuş kontrolcü ayarları, pervane)
  üreticinin belgesine ve uçuştan önce elle doğrulamaya yönlendir.
- Yanıtlarında basit biçim kullanabilirsin: paragraflar, "- " ile başlayan maddeler ve **kalın**.
"""
