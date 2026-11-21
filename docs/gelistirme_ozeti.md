# DroneLab – Geliştirme Özeti

> **Drone tasarla — Kontrol et — Harekete geç**

Bu belge, DroneLab'ın 15 Kasım 2026'daki geliştirme oturumunda yapılan her şeyi
özetler: alınan kararlar, eklenen özellikler, kodun yapısı, hesap kuralları, güvenlik
önlemleri ve açık işler. Ayrıntılı plan için [proje_raporu.pdf](proje_raporu.pdf) ve
[elektronik_plani.md](elektronik_plani.md) belgelerine bakın.

---

## 1. Program nedir?

DroneLab, Windows'ta **kullanıcının kendi bilgisayarında** çalışan bir drone tasarım ve
uygunluk programıdır. Sunucu, alan adı veya barındırma gerekmez; arayüz tarayıcıda açılır.

Kullanıcı:

- şasi dosyasını yükler veya ağırlığını elle girer,
- elektronik parçaları ekler (ya da Gemini'den öneri ister),
- hedeflerini (uçuş süresi, yük, bütçe) ve motor itki tablosunu girer,
- uyum kontrollerini, uçuş hesabını ve maliyeti görür,
- isterse bir yarışma şartnamesi yükleyip madde madde uygunluk raporu alır.

## 2. Kurulum ve çalıştırma

| İş | Komut |
|---|---|
| **Masaüstünden aç** | Masaüstündeki **DroneLab** simgesine çift tıkla (kendi penceresinde açılır) |
| Kendi penceresinde başlat | `.\.venv\Scripts\pythonw.exe masaustu.py` |
| Tarayıcıda başlat | `.\.venv\Scripts\python.exe uygulama.py` → `http://127.0.0.1:8000` |
| Masaüstü kısayolunu (yeniden) oluştur | `.\.venv\Scripts\python.exe -m araclar.kisayol_olustur` |
| Program simgesini yeniden üret | `.\.venv\Scripts\python.exe -m araclar.simge_olustur` |
| Testleri çalıştır | `.\.venv\Scripts\python.exe -m pytest` |
| Bağımlılıkları kur | `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` |

**Ortam notu:** PATH'teki `python` MSYS2 Python'udur ve paket kuramaz. Sanal ortam
standart Windows Python 3.13 ile kuruldu (`py -3.13 -m venv .venv`); komutlar her zaman
`.\.venv\Scripts\python.exe` ile çalıştırılır.

Sunucu yalnızca `127.0.0.1` adresinden erişilebilir (ağdaki diğer cihazlar göremez).

**Masaüstü penceresi (masaustu.py):**

- Program konsol penceresi olmadan, kendi penceresinde açılır (pywebview + Windows'taki
  Edge WebView2). Yerel sunucu boş bir portta arka planda başlar.
- Pencere kapanınca sunucu da kapanır; program aynı anda yalnızca bir kez açılabilir.
- Hatalar Türkçe bir uyarı kutusuyla gösterilir ve `veri/dronelab.log` dosyasına yazılır.
- Proje klasörü taşınırsa kısayol komutu yeniden çalıştırılmalıdır.

## 3. Geliştirme süreci (aşama aşama)

| # | Aşama | Ne yapıldı |
|---|---|---|
| 1 | Proje iskeleti | Klasör yapısı, FastAPI sunucusu, `requirements.txt`, ortak hata sınıfları, birim dönüştürücü |
| 2 | Şasi yükleme | STL/OBJ/3MF (trimesh) ve DXF (ezdxf) okuma; birim önerisi ve onayı; SolidWorks/Fusion gibi okunamayan dosyalar için dışa aktarma rehberi |
| 3 | Ana sayfa ve kayıt | Üç başlangıç seçeneği, drone kaydı (ad, tür, amaç), SQLite veritabanı, şasi dosyasının saklanması, elle şasi ağırlığı |
| 4 | Elektronik planı | `docs/elektronik_plani.md`: parça türleri, uyum kuralları, hesaplar, yapay zekanın rolü |
| 5 | Parça kataloğu | Parça veri modelleri, ortak katalog, drone–parça bağı (adet, durum) |
| 6 | Parça ekleme ekranı | Türe göre değişen form, katalogdan öneri, zorunlu parça çipleri, ağırlık özeti |
| 7 | Uyum ve uçuş hesabı | K1–K13 uyum kontrolleri; itki, itki/ağırlık, asılı kalma gazı ve akımı, uçuş süresi |
| 8 | Gemini önerisi | "Öner" düğmesi; ayarlar sayfası; anahtar yönetimi; günlük istek sınırı |
| 9 | Maliyet | Elle girilen fiyatlar, TCMB kuruyla TL'ye çevirme, alınacak/elimdeki ayrımı |
| 10 | Bölümlerin ayrılması | Uyum ve uçuş hesabı ayrı sekmelere; "Hedefler ve itki" sekmesi (hedefler + itki tablosu) |
| 11 | Şartname | PDF/Word yükleme, Gemini ile madde çıkarımı, kullanıcı onayı, şartname kütüphanesi, madde bazlı uyum raporu |
| 12 | Tasarım | Sol adım menüsü, üst özet şeridi, şasi üstten görünüş, uçuş göstergeleri, bağlantı şeması, uçuşan dronelar |
| 13 | Taktik görünüm | Radar, hedef izleme çerçeveleri, köşe parantezleri, sistem saati, türe göre (4/6/8 rotor) drone çizimleri |
| 14 | Son dokunuşlar | Ad **DroneLab**, slogan, saydam üst çubuk, bu özet belgesi |
| 15 | Masaüstü uygulaması | Birim onaylanınca doğrulama kartı kapanır; kendi penceresinde açılan masaüstü sürümü, program simgesi, masaüstü kısayolu, başlık çubuğu renkleri |
| 16 | Ad: DroneLab | Program adı tek ayara bağlandı (`PROGRAM_ADI`); sayfalar adı sunucudan alır |

## 4. Alınan kararlar

**Kapsam**

- İlk sürüm yalnızca çok rotorlu dronelar (quad / hexa / okto). Sabit kanat, 3D yerleşim ve
  denge, Onshape API sonraya bırakıldı.
- STEP okuma (cadquery) sonraya bırakıldı; şasi için STL, OBJ, 3MF ve DXF destekleniyor.
- 3D önizleme (Three.js) şimdilik yok; yerine 2D üstten görünüş çiziliyor.

**Elektronik ve hesap**

- Araştırmayı yapay zeka, kontrolleri ve hesapları programın kendi kodu yapar.
- Eksik değer tahmin edilmez: `None` kalır ve ilgili kontrol "doğrulanamıyor" olur.
- Pervane uyumu için stator boyutuna göre tahmin **yapılmaz**.
- Pervanenin şasiye sığması (K5) şasi ölçüsünden tahmin edilir ve her zaman "tahmini" yazılır.
- Elle girilen parçalar "doğrulandı", Gemini'nin önerdikleri "doğrulanmadı" sayılır.

**Yapay zeka**

- Sağlayıcı: **Google Gemini** (Anthropic değil).
- Gemini yalnızca kullanıcı "Öner" veya "Gemini ile maddeleri çıkar" dediğinde çalışır.
- **Ücretli bir boyut eklenmedi:** Google Arama ile araştırma ücretsiz kotada olmadığı için
  kullanılmıyor; Gemini kendi bilgisinden yanıt verir. Günde en çok 20 istek (ayarlanabilir).
- API anahtarı uzay-koc projesinden bu projeye kopyalandı (`veri/gemini_anahtari.txt`).

**Maliyet**

- Fiyatlar **elle** girilir (Gemini fiyat aramaz).
- Parça fiyatı katalogda saklanır; o parçayı kullanan tüm dronelarda geçerlidir.
- Yabancı para birimi TCMB döviz satış kuruyla TL'ye çevrilir (günde bir kez, "tahmini").
- "Elimde" olan parçalar ayrı toplanır; bütçe yalnızca alınacaklarla karşılaştırılır.

**Şartname**

- Şartname yalnızca PDF veya Word (.docx) dosyası olarak yüklenir; internetten aranmaz.
- Yüklenen şartnameler bir kütüphanede durur. Başka bir drone'a "Önceden yüklenmiş
  şartnameler" listesinden eklenebilir; maddeler şartnameye aittir ve ortaktır.
- Gemini'nin çıkardığı her madde kullanıcı onayı bekler; onaysız madde sonuca katılmaz.
- Puanlanan kriterler yalnızca bilgi olarak gösterilir.
- Şartname, drone oluşturulurken isteğe bağlı sorulur ve sonra "Şartname" sekmesinden yönetilir.

**Arayüz**

- Koyu tema, solda adım menüsü, üstte her adımda görünen özet şeridi.
- Görseller ek kütüphane olmadan SVG ile çizilir; program internetsiz çalışır.
- Savunma sanayi havası veren taktik görünüm (radar, izleme çerçeveleri, sabit genişlikli yazı).

## 5. Ekranlar

| Sayfa / sekme | İçerik |
|---|---|
| **Ana sayfa** | Slogan, radar, uçuşan dronelar, üç başlangıç seçeneği, kayıtlı drone kartları (türe göre çizim), yeni drone formu (isteğe bağlı şartname) |
| **Ayarlar** | Gemini anahtarı (yalnızca var/yok gösterilir), model, günlük sınır, bugünkü kullanım; şartname kütüphanesi |
| 01 Şasi | Dosya yükleme, birim onayı, ölçüler, **üstten görünüş** (motor yerleri, pervaneler, sığabilecek en büyük pervane), elle ağırlık |
| 02 Elektronik | Zorunlu parça çipleri, ağırlık özeti, parça listesi (adet / durum), parça formu, **✨ Öner** paneli |
| 03 Hedefler ve itki | Uçuş süresi, yük ve bütçe hedefleri; motor itki tablosu girişi |
| 04 Uyum kontrolleri | **Bağlantı şeması** (renkli çizgiler) ve K1–K13 listesi |
| 05 Uçuş hesabı | **Göstergeler** (itki/ağırlık, uçuş süresi, asılı gaz), **ağırlık dağılımı**, hesap tablosu |
| 06 Maliyet | Toplamlar, bütçe karşılaştırması, kur bilgisi, fiyat tablosu |
| 07 Şartname | Şartname ekleme (kütüphane / yeni belge), uyum raporu, madde tablosu |

Üstteki **özet şeridi** her sekmede toplam ağırlığı, itki/ağırlığı, uçuş süresini,
maliyeti ve uyumu gösterir. Sol menüdeki her adımın yanında durum işareti bulunur
(✓, "6 eksik", "2 ⚠", "bütçe aşıldı" gibi).

## 6. Kod yapısı

```
masaustu.py                Masaüstü sürümü: kendi penceresinde açar (masaüstü kısayolu bunu çalıştırır)
uygulama.py                Tarayıcı sürümü: yerel sunucu + tarayıcı
araclar/                   Program simgesi ve masaüstü kısayolu oluşturma
cekirdek/                  Ayarlar, hata sınıfları, birim dönüşümleri, zaman, SSL (ag.py)
sasi/                      Şasi okuyucuları (STL/OBJ/3MF, DXF), birim doğrulama, dışa aktarma rehberi
drone/                     Drone modeli, hedefler, doğrulama, servis
depolama/                  SQLite veritabanı ve göçleri, drone/şasi/hedef depoları
elektronik/
  parcalar/                Parça türleri ve veri modelleri, denetim, serileştirme, form alanları
  hesap/                   katsayilar.py, uyum kontrolleri (K1–K13), ağırlık, akım, uçuş, tahmini itki,
                           itki tablosu, şasiden pervane tahmini, pil gerilimi
  oneri/                   Gemini önerisi: şema, istem, aday dönüştürme, değerlendirme, servis
  katalog.py, drone_parca_deposu.py, zorunlu_parcalar.py, servis.py
arastirma/                 Gemini istemcisi, ortak istek adımları, anahtar, ayarlar, günlük sayaç
maliyet/                   Para birimleri, fiyat depoları, TCMB kurları, hesap, servis
sartname/                  Madde modeli, PDF/Word metni, Gemini çıkarımı, kütüphane, uyum kontrolü, servis
arayuz/                    FastAPI sunucusu ve API uçları (drone, elektronik, öneri, maliyet, şartname)
  statik/                  HTML / CSS / JavaScript arayüzü
testler/                   pytest testleri
docs/                      Proje raporu, elektronik planı, bu özet
veri/                      Veritabanı, şasi ve şartname dosyaları, anahtar, yerel ayarlar (kullanıcı verisi)
```

**Kodlama kuralları (CLAUDE.md):**

- Python, OOP; her sınıf tek iş yapar.
- Türkçe ama Türkçe karakter içermeyen adlar; Türkçe docstring ve hata mesajları.
- Değiştirilebilir sabitler `# DEĞİŞTİRİLEBİLİR:` etiketiyle işaretlidir.
- Birimler: mm, gram, g/cm3.
- Tahmine dayalı her sonuç "tahmini" etiketlidir.

## 7. Hesap ve kontrol kuralları

**Uyum kontrolleri** – sonuç ✓ uygun, ⚠ dikkat, ✗ uyumsuz ya da ? doğrulanamıyor:

| Kod | Kontrol |
|---|---|
| K1 / K2 | Pil hücre sayısı motorun / ESC'nin aralığında |
| K3 | Dolu pil gerilimi FC/PDB girişini aşmıyor (kimya bilinmiyorsa bütün kimyalar denenir) |
| K4 | Pervane çapı motorun önerilen aralığında |
| K5 | Pervane şasiye sığıyor (tahmini; sınıra ±0,5 inç yakınsa ⚠) |
| K6 | ESC akımı ≥ motor akımı × 1,2 |
| K7 | Pil sürekli akımı (Ah × C) ≥ toplam akım × 1,2 |
| K8 / K9 | FC–ESC montaj ölçüsü ve sinyal protokolü |
| K10 | Alıcı protokolü, boş UART, besleme gerilimi |
| K11 | Motor sayısı drone türüyle uyumlu |
| K12 | Pil konnektörü (farklıysa yalnızca ⚠) |
| K13 | Kamera / VTX / GPS besleme gerilimi bir BEC çıkışıyla uyumlu |

**Uçuş hesabı**

- Toplam ağırlık = şasi + parçalar + %5 kablo payı + yük.
- Motorun itki tablosu varsa değerler tablodan okunur; pilin gerilimine en yakın satırlar seçilir.
- Tablo yoksa itki T = C_T·ρ·n²·D⁴ ile, asılı kalma gücü momentum teorisiyle tahmin edilir.
- Uçuş süresi = kapasitenin %80'i / (asılı akım × uçuş tarzı katsayısı); her zaman tahminidir.

**Şasiden pervane tahmini**

- Dingil mesafesi ≈ şasi köşegeni × 0,9.
- Komşu motorlar arası mesafe = dingil × sin(π / motor sayısı).
- Sığabilecek en büyük pervane = bu mesafe − 6 mm.

Bütün eşik ve katsayılar tek dosyadadır: `elektronik/hesap/katsayilar.py`.

**Şartname raporu**

- Toplam eksikse (ör. bir parçanın ağırlığı girilmemiş) bilinen değer bir alt sınırdır:
  "en çok" sınırını şimdiden aşıyorsa ✗, aşmıyorsa ? gösterilir.
- Failsafe, irtifa, hız gibi ölçülemeyen maddeler ölçülmüş gibi gösterilmez.

## 8. Güvenlik ve gizlilik

- **Anahtar dosyası:** Gemini API anahtarı kodun içinde değildir. Önce `GEMINI_API_KEY` /
  `GOOGLE_API_KEY` ortam değişkenlerinde, sonra `veri/gemini_anahtari.txt` dosyasında aranır.
- **Anahtarın gizliliği:** Anahtar hiçbir ekranda, API yanıtında veya logda gösterilmez; yalnızca
  "var / yok" bilgisi döner. Testler bunu ayrıca denetler.
- **Paylaşım:** `veri/` klasörü yedeklenip paylaşılacaksa önce anahtar dosyası çıkarılmalıdır.
- **Gemini'ye giden bilgi:** Gemini'ye drone türü, amacı, ölçüleri, parça değerleri ve şartname
  metni gider; **drone adı gönderilmez**. İstekler `store: false` ile yapılır.
- **Ücret:** Ücret çıkmaması için Google hesabında anahtarın projesinde faturalandırma kapalı
  olmalıdır.
- **Model yanıtı:** Modelden gelen hiçbir metin kod olarak çalıştırılmaz. Her değer programın
  doğrulayıcısından geçer; geçersiz değer silinir.
- **Arayüz:** Kullanıcı verisi her zaman `textContent` ile yazılır (HTML olarak yorumlanmaz).
  Bağlantılar yalnızca `http(s)` olabilir.

## 9. Veritabanı sürümleri

Dosya: `veri/dronelar.sqlite3`. Eski bir dosya açıldığında yalnızca eksik sürümler sırayla
uygulanır; kayıtlı dronelar kaybolmaz.

| Sürüm | Eklenen |
|---|---|
| 1 | Dronelar, şasiler |
| 2 | Parça kataloğu, drone–parça bağları |
| 3 | Yapay zeka günlük kullanım sayacı |
| 4 | Parça fiyatları, şasi maliyeti, döviz kurları |
| 5 | Drone hedefleri (uçuş süresi, yük, bütçe) |
| 6 | Şartnameler, maddeleri, drone–şartname bağı |

## 10. Bağımlılıklar

`numpy`, `trimesh`, `networkx`, `lxml` (3D dosyalar), `ezdxf` (DXF), `fastapi`, `uvicorn`,
`python-multipart` (sunucu ve dosya yükleme), `pypdf`, `python-docx` (şartname belgeleri),
`pywebview` (masaüstü penceresi), `pytest`, `httpx` (testler).

Gemini ve TCMB bağlantıları yalnızca Python'un standart kütüphanesiyle yapılır.

## 11. Testler

Oturum sonunda **260 test** geçiyor.

Testlerde gerçek Gemini veya TCMB isteği yapılmaz; sahte sağlayıcılar ve test içinde üretilen
PDF/Word belgeleri kullanılır. Testler kullanıcının gerçek veritabanına yazmaz (geçici klasör).

## 12. Açık işler ve sınırlar

- **Henüz yapılmayanlar:**
  - STEP dosyası okuma.
  - Malzemeden şasi ağırlığı hesabı.
  - Gerçek 3D önizleme.
  - Taranmış PDF'ler için OCR.
- **Henüz denenmeyenler:** Gerçek Gemini yanıtıyla "Öner" ve "maddeleri çıkar" henüz denenmedi;
  ilk denemede istek biçimi gerçek yanıta göre düzeltilebilir.
- **Şasi tahmini:** Şasinin üstten görünüşü ve K5 tahminidir; gerçek kol uzunluğu bilinmez.
- **Şartname boyutu:** Şartname "boyut" maddesi şasi dosyasının en/boy ölçüsüyle karşılaştırılır;
  şartname boyutu çapraz motor mesafesiyle tanımlıyorsa sonuç farklı olabilir.
- **Sonraya bırakılanlar:** 3D yerleşim ve denge, sabit kanat desteği, Onshape API bağlantısı,
  Windows için tek `.exe` paketleme.

## 13. Kendin değiştirmek istersen

| Ne | Nerede |
|---|---|
| **Programın adı** (sayfalar, pencere, kısayol, simge ve günlük dosyası adı) | `cekirdek/ayarlar.py` → `PROGRAM_ADI`. Sonra programı yeniden aç; simge ve kısayol için `python -m araclar.simge_olustur` ve `python -m araclar.kisayol_olustur` çalıştır |
| Güvenlik payları, hedef itki/ağırlık, uçuş tarzı katsayıları, fizik katsayıları | `elektronik/hesap/katsayilar.py` |
| Kablo/vida payı (%5) | `elektronik/hesap/agirlik.py` |
| Kullanım amaçları | `drone/modeller.py` |
| Gemini modelleri, günlük sınır | `arastirma/gemini.py`, `arastirma/ayarlar.py` (ya da Ayarlar sayfası) |
| Para birimleri, kur türü | `maliyet/para.py`, `maliyet/kur.py` |
| Şartname büyüklükleri | `sartname/modeller.py` |
| Renkler ve taktik görünüm | `arayuz/statik/stil.css` (taktik bölüm silinirse sade görünüme dönülür) |
| Uçuşan dronelar | `arayuz/statik/ucan_droneler.js` |
| Sunucu portu | `cekirdek/ayarlar.py` |
