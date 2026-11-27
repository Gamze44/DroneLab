# DroneLab

**Drone tasarla — Kontrol et — Harekete geç**

DroneLab, çok rotorlu drone (quadcopter, hexacopter, oktokopter) tasarlamak ve tasarımın uygun olup olmadığını kontrol etmek için yazılmış bir masaüstü programıdır. Windows'ta kullanıcının kendi bilgisayarında çalışır. Bir Ar-Ge çalışmasıdır; sürüm **0.1.0** (çalışan prototip).

Kullanıcı şasinin çizim dosyasını yükler ve parçalarını girer. Program şunları hesaplar:

- parçaların birbiriyle uyumu (13 kontrol),
- toplam ağırlık, itki/ağırlık oranı ve uçuş süresi,
- toplam maliyet,
- yarışma şartnamesine uygunluk.

## Özellikler

| Adım | Ne yapar |
|---|---|
| **Şasi** | STL, OBJ ve 3MF (3B model), DXF (levha şasi) ya da birden çok parçalı şasi için ZIP dosyası okur. Ölçüleri çıkarır, birimi kullanıcıya onaylatır. Dingil mesafesini ve şasiye sığacak en büyük pervaneyi bulur. |
| **Elektronik** | Motor, pervane, ESC, pil, uçuş kartı, alıcı, PDB, kamera, VTX ve GPS gibi parçalar girilir. Girilen parçalar ortak bir katalogda tutulur. Bağlantı şeması çizilir. |
| **Hedefler ve itki** | Uçuş süresi, yük, bütçe ve itki/ağırlık hedefi girilir. Motor itki tablosu girilebilir. |
| **Uyum kontrolleri** | Pil ↔ motor hücre sayısı, ESC akımı, pervane ↔ şasi, montaj ölçüsü, sinyal protokolü gibi 13 kontrol yapar. |
| **Uçuş hesabı** | Toplam ağırlığı, itki/ağırlık oranını, havada asılı kalma gazını ve uçuş süresini hesaplar. Her değerin nasıl hesaplandığı gösterilir. |
| **Maliyet** | Fiyatlar TL ya da döviz olarak girilebilir. Dövizler TCMB günlük kuruyla TL'ye çevrilir ve bütçeyle karşılaştırılır. |
| **Şartname** | PDF veya Word biçimindeki yarışma şartnamesinden maddeleri çıkarır (kullanıcı onaylar). Drone'u bu maddelere göre değerlendirir. |
| **Asistan** | Gemini tabanlı yardımcıdır. Açık drone'un verilerini programın kendi hesaplarından okur. Önerdiği değişiklikler ancak kullanıcı "Uygula"ya basınca yapılır. |

### Tasarım ilkeleri
- **Tahmin etmez.** Bilinmeyen bir değer boş kalır ve ilgili kontrol "?" olarak gösterilir. Bir varsayıma dayanan sonuçlar **"tahmini"** etiketiyle gösterilir.
- **Yerelde çalışır.** Tüm hesaplar kullanıcının bilgisayarında yapılır. Program internete yalnızca iki iş için çıkar:
  - TCMB döviz kurunu almak (günde en çok bir kez),
  - Gemini'yi kullanmak (yalnızca kullanıcı düğmeye bastığında).
- **Yapay zekâ isteğe bağlıdır.** Gemini anahtarı olmadan da asistan, parça önerisi ve şartname maddesi çıkarma dışındaki her şey çalışır.

## Kurulum

Gerekenler: Windows 10/11 ve **Python 3.11 veya üstü** (3.13 ile denendi).

```powershell
git clone https://github.com/Gamze44/DroneLab.git
cd DroneLab
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Çalıştırma

**Kendi penceresinde açmak için** (Windows'taki Edge WebView2 kullanılır):

```powershell
.\.venv\Scripts\pythonw.exe masaustu.py
```

**Tarayıcıda açmak için:**

```powershell
.\.venv\Scripts\python.exe uygulama.py
```

Program `http://127.0.0.1:8000` adresinde açılır. Bu adres yalnızca o bilgisayardan açılabilir.

**İsteğe bağlı masaüstü kısayolu:**

```powershell
.\.venv\Scripts\python.exe -m araclar.kisayol_olustur
```

İlk açılışta veritabanı `veri/` klasöründe kendiliğinden oluşturulur. Gemini'yi kullanmak için **Ayarlar** sayfasına bir Gemini API anahtarı girilir. Anahtar yalnızca o bilgisayarda saklanır, koda ve depoya yazılmaz.

## Testler

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Projede **430 otomatik test** vardır ve hepsi geçer; çalışmaları yaklaşık 40 saniye sürer.

- Testler gerçek Gemini'ye istek atmaz; sahte bir model kullanır.
- Gerçek veritabanına dokunmaz; her test kendi geçici klasöründe çalışır.

| Alan | Test |
|---|---:|
| Elektronik ve uçuş hesapları | 134 |
| Şasi dosyası okuma ve ölçü | 88 |
| Güvenlik ve sunucu | 78 |
| Yapay zekâ (asistan, parça önerisi) | 40 |
| Drone kaydı ve veritabanı | 36 |
| Genel yapı | 26 |
| Şartname | 17 |
| Maliyet | 11 |

## Proje yapısı

```
uygulama.py        Tarayıcıyla çalıştırma giriş noktası
masaustu.py        Kendi penceresinde çalıştırma giriş noktası
cekirdek/          Ortak ayarlar, birim dönüşümleri, hata sınıfları
sasi/              Şasi dosyası okuyucuları (STL/OBJ/3MF/DXF/ZIP), ölçü ve dingil hesabı
elektronik/        Parça katalogu, uyum kontrolleri, uçuş ve itki hesapları
drone/             Drone kaydı, hedefler, doğrulama
maliyet/           Fiyatlar, TCMB kurları, maliyet hesabı
sartname/          Şartname belgesi okuma, madde çıkarma ve uygunluk raporu
arastirma/         Gemini istemcisi ve otomatik model seçimi
asistan/           Asistanın araçları, senaryo hesabı ve öneri onayı
depolama/          SQLite veritabanı ve şema geçişleri
arayuz/            FastAPI sunucusu, güvenlik katmanları ve arayüz (HTML/CSS/JS)
araclar/           Masaüstü kısayolu ve simge oluşturma
testler/           pytest testleri
docs/              Geliştirme belgeleri ve kullanım kılavuzu
```

Kod nesne yönelimli ve modüler yazıldı; her sınıf tek bir işi yapar. Adlar ve açıklamalar Türkçedir. Programda kullanılan birimler: uzunluk mm, kütle gram.

## Belgeler

- [Kullanım kılavuzu (katlamalı broşür, PDF)](docs/kullanim_brosuru.pdf)
- [Geliştirme özeti](docs/gelistirme_ozeti.md)
- [Geliştirme planı](docs/gelistirme_plani.md)
- [Mevcut durum](docs/mevcut_durum.md)

## Kullanılan teknolojiler

| Alan | Kullanılan |
|---|---|
| Dil | Python |
| Sunucu | FastAPI, Uvicorn |
| Arayüz | HTML, CSS, JavaScript |
| Masaüstü penceresi | pywebview |
| Veritabanı | SQLite |
| Geometri | trimesh, ezdxf, numpy |
| Belge okuma | pypdf, python-docx |
| Yapay zekâ | Google Gemini API |
| Test | pytest |

## Sınırlamalar ve sonraki adımlar

Bu sürüm bir prototiptir. Şunlar sonraki aşamalara bırakıldı:

- STEP dosyası okuma,
- parçaların 3B yerleşimi ve ağırlık merkezi (denge) hesabı,
- sabit kanatlı dronelar,
- Onshape bağlantısı.

DroneLab bir tasarım yardımcısıdır. Uçuştan önce parçaların üretici belgeleri ve yerel uçuş kuralları kontrol edilmelidir.
