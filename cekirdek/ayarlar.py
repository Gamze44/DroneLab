"""
Programın genel ayarları ve sabitleri.

Klasör yolları, yerel sunucu adresi ve program bilgileri burada tek yerde durur;
böylece kodun içinde sihirli sayı veya sabit yol kalmaz.
"""

from pathlib import Path
from typing import Final

# Proje kökü bu dosyanın iki üst klasörüdür; çalışma dizininden bağımsız olsun diye
# yollar her zaman bu kökten türetilir.
PROJE_KOKU: Final[Path] = Path(__file__).resolve().parent.parent
STATIK_KLASORU: Final[Path] = PROJE_KOKU / "arayuz" / "statik"
VERI_KLASORU: Final[Path] = PROJE_KOKU / "veri"

# DEĞİŞTİRİLEBİLİR: Programın adı. Sayfalardaki başlık, sekme ve pencere adı, masaüstü
# kısayolu, simge ve günlük dosyasının adı buradan gelir. Değiştirdikten sonra:
#   1) programı kapatıp yeniden aç,
#   2) simge ve kısayol için: python -m araclar.simge_olustur ve python -m araclar.kisayol_olustur
PROGRAM_ADI: Final[str] = "DroneLab"
# Dosya adlarında kullanılan küçük harfli, boşluksuz biçim (ör. "dronelab").
PROGRAM_DOSYA_ADI: Final[str] = PROGRAM_ADI.lower().replace(" ", "")
PROGRAM_SURUMU: Final[str] = "0.1.0"

# DEĞİŞTİRİLEBİLİR: 127.0.0.1 sunucuyu yalnızca bu bilgisayardan erişilebilir yapar.
# Ağdaki başka cihazlardan erişim gerekmedikçe değiştirme.
SUNUCU_ADRESI: Final[str] = "127.0.0.1"

# DEĞİŞTİRİLEBİLİR: Port başka bir program tarafından kullanılıyorsa farklı bir sayı ver.
SUNUCU_PORTU: Final[int] = 8000

# DEĞİŞTİRİLEBİLİR: Sunucunun kabul ettiği adres adları (Host başlığı). Başka bir web
# sitesinin kendi alan adını 127.0.0.1'e yönlendirip programa erişmesini (DNS rebinding)
# engeller. SUNUCU_ADRESI değiştirilirse buraya da eklenmeli.
IZINLI_HOSTLAR: Final[tuple[str, ...]] = ("127.0.0.1", "localhost")

# DEĞİŞTİRİLEBİLİR: Program açılınca tarayıcının kendiliğinden açılıp açılmayacağı
# (sunucu hazır olunca açılır; port doluysa açılmaz).
TARAYICIYI_OTOMATIK_AC: Final[bool] = True

# ---------- Masaüstü penceresi (masaustu.py) ----------

# DEĞİŞTİRİLEBİLİR: Pencerenin açılış boyutu ve en küçük boyutu (piksel).
PENCERE_GENISLIGI: Final[int] = 1440
PENCERE_YUKSEKLIGI: Final[int] = 920
PENCERE_EN_KUCUK: Final[tuple[int, int]] = (1000, 680)
# Pencere içeriği yüklenene kadar görünen zemin rengi (koyu temayla aynı, beyaz parlama olmasın).
PENCERE_ZEMIN_RENGI: Final[str] = "#0a0e16"
# DEĞİŞTİRİLEBİLİR: Windows başlık çubuğunun zemin, yazı ve pencere kenarlığı renkleri.
# Sayfanın üst kısmıyla aynı tonda olsun ki çubuk tasarımın parçası gibi görünsün
# (Windows 11 gerekir; daha eski Windows'ta varsayılan çubuk görünür).
BASLIK_CUBUGU_RENGI: Final[str] = "#0b111c"
BASLIK_YAZI_RENGI: Final[str] = "#22d3ee"
PENCERE_KENAR_RENGI: Final[str] = "#1c2a3f"
# Sunucunun hazır olması için en çok bekleme süresi, saniye.
SUNUCU_HAZIR_BEKLEME_SN: Final[float] = 20.0
# Konsolsuz çalışırken hatalar bu dosyaya yazılır (veri/ klasöründe).
GUNLUK_DOSYA_ADI: Final[str] = f"{PROGRAM_DOSYA_ADI}.log"
# Program simgesi (masaüstü kısayolu, pencere ve tarayıcı sekmesi).
SIMGE_YOLU: Final[Path] = STATIK_KLASORU / f"{PROGRAM_DOSYA_ADI}.ico"

# DEĞİŞTİRİLEBİLİR: Yüklenebilecek en büyük dosya (MB). STL boyutu parçanın fiziksel
# büyüklüğüne değil üçgen sayısına bağlıdır; çok ayrıntılı modeller için artırılabilir.
EN_BUYUK_YUKLEME_MB: Final[int] = 200

# Kayıtlı dronelar bu veritabanı dosyasında, şasi dosyalarının kopyaları da
# veri klasöründeki bu alt klasörde tutulur. Yedek almak için veri/ klasörünü kopyalamak yeterli.
VERITABANI_DOSYA_ADI: Final[str] = "dronelar.sqlite3"
SASI_DOSYALARI_KLASOR_ADI: Final[str] = "sasi_dosyalari"
SARTNAME_DOSYALARI_KLASOR_ADI: Final[str] = "sartname_dosyalari"

# DEĞİŞTİRİLEBİLİR: Yüklenebilecek en büyük şartname belgesi (MB).
EN_BUYUK_SARTNAME_MB: Final[int] = 30

# DEĞİŞTİRİLEBİLİR: Şartname belgesinin en çok sayfa sayısı (PDF ve Word).
EN_FAZLA_SARTNAME_SAYFASI: Final[int] = 50
# DEĞİŞTİRİLEBİLİR: Word belgesinde Word'ün kaydettiği sayfa sayısı yoksa sayfa, kelime
# sayısından bu oranla tahmin edilir (sonuç "tahmini" diye gösterilir).
SAYFA_BASINA_KELIME: Final[int] = 500

# DEĞİŞTİRİLEBİLİR: Dosya içermeyen isteklerin (JSON) en büyük boyutu (MB).
EN_BUYUK_ISTEK_MB: Final[int] = 5

# ---------- Zip tabanlı dosyalar (Word .docx, 3MF) ----------
# Bu dosyalar aslında sıkıştırılmış arşivdir. Kötü amaçlı bir arşiv küçük görünüp açılınca
# gigabaytlarca büyüyebilir ("zip bombası"); açmadan önce bu sınırlar denetlenir.
# DEĞİŞTİRİLEBİLİR: Arşivin içindekilerin açılmış toplam boyutu (MB).
EN_BUYUK_ACIK_ARSIV_MB: Final[int] = 1024
# DEĞİŞTİRİLEBİLİR: Bir arşiv üyesinin en çok sıkıştırma oranı (açık boyut / sıkışık boyut).
# Gerçek belgelerde 5–20 kat görülür; zip bombalarında binlerce kattır.
EN_BUYUK_SIKISTIRMA_ORANI: Final[int] = 100
# Oran yalnızca bu boyuttan (MB) büyük üyelerde denetlenir; küçük ve tekrarlı XML'ler
# yüksek oranla sıkışabilir ama zararsızdır.
ORAN_DENETIM_ESIGI_MB: Final[int] = 1
# DEĞİŞTİRİLEBİLİR: Arşivdeki en çok dosya sayısı.
EN_FAZLA_ARSIV_UYESI: Final[int] = 10_000

# Yerel ayar dosyası ve Gemini anahtar dosyası veri/ klasöründe durur (kodun içinde değil).
# DİKKAT: veri/ klasörü başkasıyla paylaşılacaksa önce anahtar dosyası çıkarılmalı.
YEREL_AYAR_DOSYA_ADI: Final[str] = "ayarlar_yerel.json"
ANAHTAR_DOSYA_ADI: Final[str] = "gemini_anahtari.txt"
# Anahtar önce bu ortam değişkenlerinde aranır (uzay-koc projesiyle aynı adlar).
ANAHTAR_ORTAM_DEGISKENLERI: Final[tuple[str, ...]] = ("GEMINI_API_KEY", "GOOGLE_API_KEY")
