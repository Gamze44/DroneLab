# DroneLab – Mevcut Durum Envanteri (G0)

> 21 Kasım 2026, `gelistirme` dalı (commit `ae787f8`) üzerinde hazırlandı. Kod değiştirilmedi.
> Kanıtlar `dosya:satır` biçimindedir. Ayrıntılı geliştirme geçmişi için `docs/gelistirme_ozeti.md`.

## 1. Genel yapı

**Çalışma biçimi**

- Yerel FastAPI sunucusu, arayüz tarayıcıda ya da kendi penceresinde açılır.
  - Tarayıcı sürümü: `uygulama.py`.
  - Masaüstü sürümü: `masaustu.py` (pywebview + Edge WebView2).
- Sunucu yalnızca bu bilgisayardan erişilebilir (`127.0.0.1`).

**Paketler ve ana sınıflar**

| Paket | Görev | Ana sınıflar |
|---|---|---|
| `cekirdek/` | Ayarlar, hatalar, birimler | `BirimDonusturucu`, `DroneProgramHatasi` ve alt sınıfları |
| `depolama/` | SQLite ve dosya depoları | `Veritabani` (`depolama/veritabani.py:163`), `DroneDeposu`, `SasiKayitDeposu`, `SasiDosyaDeposu`, `HedefDeposu` |
| `drone/` | Drone kaydı ve hedefler | `Drone`, `DroneHedefleri`, `DroneServisi` |
| `sasi/` | Şasi dosyası okuma | `OkuyucuSecici`, `AgOkuyucu` (STL/OBJ/3MF), `DxfOkuyucu`, `BirimDogrulayici` |
| `elektronik/parcalar/` | Parça modelleri | `Parca`, `Motor`, `Pervane`, `Esc`, `Pil`, `UcusKarti`, `Alici`, `GucDagitim`, `DigerParca`, `ItkiNoktasi` |
| `elektronik/` | Katalog ve drone–parça bağı | `ParcaKatalogu`, `DroneParcaDeposu`, `ZorunluParcaDenetleyici`, `ElektronikServisi` |
| `elektronik/hesap/` | Hesaplar | aşağıdaki tablo |
| `elektronik/oneri/` | Gemini parça önerisi | `OneriServisi`, `AdayDegerlendirici`, `AdayDonusturucu` |
| `arastirma/` | Yapay zeka istemcisi | `GeminiSaglayicisi`, `YapayZekaIstemcisi`, `AnahtarDeposu`, `GunlukKullanimSayaci` |
| `maliyet/` | Fiyat ve kur | `MaliyetHesaplayici`, `MaliyetServisi`, `KurServisi` (TCMB) |
| `sartname/` | Şartname | `SartnameServisi`, `SartnameKontrolcusu`, `SayfaSiniriDenetleyici`, `MaddeDonusturucu` |
| `arayuz/` | API uçları ve statik arayüz | `sunucu_olustur`, `*_rotalari.py` |
| `araclar/` | Kurulum yardımcıları | simge ve masaüstü kısayolu |

**Hesap sınıflarının gerçek adları** (plandaki "uçuş hesabı, uyumluluk kontrolü, ağırlık hesabı"):

| Plandaki ad | Koddaki sınıf |
|---|---|
| Ağırlık hesabı | `AgirlikHesaplayici` (`elektronik/hesap/agirlik.py:49`) |
| Uçuş hesabı | `UcusHesaplayici` (`elektronik/hesap/ucus.py:108`) |
| Uyumluluk kontrolü | `UyumlulukKontrolcusu` (`elektronik/hesap/uyumluluk.py:45`); her kontrol ayrı bir `UyumKontrolu` alt sınıfı (K1–K13, `elektronik/hesap/uyum_kontrolleri.py`) |
| Tahmini itki ve güç | `TahminiItkiHesaplayici` (`elektronik/hesap/tahmini_itki.py:48`) |
| İtki tablosu ara değeri | `ItkiTablosuOkuyucu` (`elektronik/hesap/itki_tablosu.py:35`) |
| Toplam akım | `EnBuyukAkimHesaplayici` (`elektronik/hesap/akim.py:29`) |
| Pervane–şasi tahmini | `EnBuyukPervaneTahmincisi` (`elektronik/hesap/sasi_pervane.py:22`) |
| Maliyet | `MaliyetHesaplayici` (`maliyet/hesap.py:96`) |
| Şartname uyumu | `SartnameKontrolcusu` (`sartname/kontrol.py:125`) |

Bütün katsayılar tek bir dosyada duruyor: `elektronik/hesap/katsayilar.py`.

**Arayüz yapısı**

- Kütüphane kullanılmıyor; düz HTML, CSS ve JavaScript (`arayuz/statik/`).
- Sayfalar:
  - Ana sayfa (`index.html`).
  - Drone sayfası (`drone.html`): solda 7 adımlı menü, üstte özet şeridi.
  - Ayarlar (`ayarlar.html`).
- Program adı ve bazı sınırlar HTML'e sunucu tarafından yer tutucularla yazılıyor (`arayuz/sunucu.py`, `sayfa_yaniti`).

**Grafik ve 3D kütüphaneleri**

- **Yok.** Bütün görseller SVG ile elle çiziliyor (`arayuz/statik/gorseller.js`): şasinin üstten görünüşü, göstergeler, ağırlık dağılımı, bağlantı şeması.
- 3D önizleme (Three.js) hiç eklenmedi.

**Proje verisinin tutulması**

- Tek bir SQLite dosyası: `veri/dronelar.sqlite3`, şema sürümü 6. Eksik sürümler sırayla uygulanıyor (`depolama/veritabani.py:159`).
- Yüklenen şasi ve şartname dosyalarının kopyaları `veri/` altında duruyor.
- Ayarlar `veri/ayarlar_yerel.json`, Gemini anahtarı `veri/gemini_anahtari.txt` dosyasında.
- Her değişiklik otomatik kaydediliyor. Taşınabilir bir "proje dosyası" yok.

## 2. Görev bazında durum

| Görev | Durum | Kanıt | Eksik olan |
|---|---|---|---|
| **G1** Proje kaydetme / açma / sürüm geçmişi | **Kısmen** | Otomatik kayıt ve kayıtlı drone listesi: `depolama/drone_deposu.py:23`, `depolama/drone_deposu.py:124`. Şema göçü: `depolama/veritabani.py:159` | `.droneproj` dışa ve içe aktarma, sürüm geçmişi, son açılanlar listesi |
| **G2** Malzeme listesi ve maliyet | **Kısmen** | Fiyat, para birimi, elimde/alınacak, bütçe ve toplamlar: `maliyet/hesap.py:96`, `maliyet/servis.py:45`, `arayuz/statik/maliyet.js:79`. Fiyat tarihi veritabanında tutuluyor (`parca_fiyatlari.guncelleme_zamani`) | `.xlsx` ve `.csv` dışa aktarma; tabloda ağırlık, kaynak ve doğrulandı sütunları; para birimine göre ayrı toplam. **Çelişki:** plan "program kur çekmez" diyor, program TCMB'den kur çekiyor (`maliyet/kur.py:124`, kullanıcı kararı) |
| **G3** Teknik rapor | **Yok** | Rapor üreten kod yok. Word kütüphanesi (`python-docx`) şartname okumak için zaten kurulu | Hepsi. PDF için yeni bir kütüphane gerekir |
| **A1** API harcama sayacı | **Kısmen** | Günlük istek sayacı ve sınırı: `arastirma/kullanim.py:16`, `arastirma/kullanim.py:37`, `arastirma/ayarlar.py:21` | Token ve maliyet kaydı, aylık sınır, özelliğe göre dağılım. Not: Gemini ücretsiz katmanda ve aramasız kullanılıyor |
| **A2** Hata günlüğü ve rapor | **Kısmen** | Boyutu sınırlı, dönen günlük (yalnızca masaüstü sürümünde): `masaustu.py:69`, `masaustu.py:72`. Yakalanmamış hatada Türkçe mesaj: `arayuz/sunucu.py:107` | Tarayıcı sürümünde dosyaya günlük yok; "Hata raporu oluştur" ZIP'i ve maskeleme yok; konum `kayitlar/` değil `veri/` |
| **G4** Senaryo karşılaştırma | **Yok** | — (Öneri panelindeki aday karşılaştırması benzer: `elektronik/oneri/degerlendirici.py:56`) | Hepsi |
| **G5** Pil optimizasyon grafiği | **Yok** | — | Hepsi; grafik mevcut SVG yardımcılarıyla çizilebilir |
| **G6** "Elimdeki drone" kolu | **Kısmen** | Ana sayfada seçenek var (`arayuz/statik/index.html:36`, `drone/modeller.py:17`) ama sıfırdan yapımla aynı akışa gidiyor. Öneri servisi var: `elektronik/oneri/servis.py:69` | Zayıf nokta analizi, hedefe göre yükseltme önerisi, ölçülmüş değer girişi |
| **G7** Bağlantı şeması | **Kısmen** | Uyum sonuçlarına göre renkli mantıksal SVG şema: `arayuz/statik/gorseller.js:258`. UART sayısı kontrolü: `elektronik/hesap/uyum_kontrolleri.py:413` | UART atama önerisi, gerilim hatları, kamera → VTX bağlantısı, SVG/PNG olarak kaydetme |
| **G8** İtki verisi içe aktarma | **Kısmen** | Elle tablo girişi: `arayuz/statik/hedefler.js:131`, `elektronik/servis.py:133`. Hesapta tablo ve ara değer kullanımı: `elektronik/hesap/itki_tablosu.py:35` | CSV içe aktarma ve şablon. Gerilim uyuşmazlığı uyarısı yok: en yakın gerilim sessizce seçiliyor (`elektronik/hesap/itki_tablosu.py:46`). "Ölçülmüş veriye dayalı" etiketi yok |
| **G9** Uçuş kaydı kalibrasyonu | **Yok** | — | Hepsi |
| **G10** Ortam koşulları | **Yok** | Hava yoğunluğu sabit: `elektronik/hesap/katsayilar.py:95` | Hepsi |
| **G11** Mevzuat kontrolü | **Yok** | — | Hepsi (SHGM araştırması gerekir) |
| **A3** Katalog paylaşma | **Yok** | Katalog var (`elektronik/katalog.py:27`), dışa ve içe aktarma yok | Hepsi |
| **A4** İngilizce arayüz | **Yok** | Bütün metinler HTML, JavaScript ve Python hata mesajlarında Türkçe ve sabit | Hepsi |
| **A5** GitHub Actions ve .exe | **Yok** | `.github/` klasörü yok. Depo yerel; GitHub'a ilk gönderim henüz yapılmadı | Hepsi |
| **A6** Güncelleme kontrolü | **Kısmen** | Sürüm tek yerde tanımlı: `cekirdek/ayarlar.py:24` (`PROGRAM_SURUMU`) | GitHub Releases kontrolü |
| **B1** 3D yerleşim | **Yok** | CLAUDE.md'de "sonraya bırakılan" | — |
| **B2** Sabit kanat / VTOL | **Yok** | CLAUDE.md'de "sonraya bırakılan"; yalnızca çok rotorlu (`drone/modeller.py:20`) | — |
| **B3** Onshape | **Yok** | CLAUDE.md'de "sonraya bırakılan" | — |
| **B4** Uçuş kartı ayarları | **Yok** | — | — |

Tamamen var olan görev yok; bu yüzden durum tablosunda hiçbir görev "zaten vardı" olarak işaretlenmedi.

## 3. Plan ile mevcut durum arasındaki uyuşmazlıklar

1. **Rapor dosyası:** Plan `docs/proje_raporu.md` dosyasına atıf yapıyor. Elimizdeki `docs/proje_raporu.pdf` ve kullanıcı kararıyla git dışında tutuluyor.
2. **Kur:** G2'deki "program kendisi kur çekmez" kuralı, çalışan TCMB kur özelliğiyle çelişiyor. Karar gerekiyor.
3. **Ad:** Plan "Drone Tasarım Programı" diyor; programın adı **DroneLab**.
4. **Kayıt yapısı:** G1 ayrı bir proje dosyası öneriyor; program şu an veritabanına otomatik kaydediyor. `.droneproj` veritabanının yerine mi geçecek, yanında bir dışa ve içe aktarma biçimi mi olacak, karar gerekiyor. Öneri: ikincisi.
5. **Sonraya bırakılanlar:** B1–B3, CLAUDE.md'deki "sonraya bırakılanlar" kuralıyla çelişiyor. Başlamadan önce CLAUDE.md'nin güncellenmesi gerekir.
6. **Şasi formatı:** Plan şasi için STEP desteği varsayıyor (`Proje bağlamı`). STEP okuma henüz yok (`cadquery` eklenmedi).
7. **Günlük konumu:** A2 günlükleri `kayitlar/` klasörüne istiyor; mevcut günlük `veri/dronelab.log` dosyasında.

## 4. Sıralama önerisi (tablo onaysız değiştirilmedi)

Önce bağımlılık ve karar gerektirmeyen, mevcut kodu tamamlayan küçük işler; sonra karar gerektiren büyük yapı işleri.

1. **G8, G10, A2, A3, G7:** Mevcut kodun eksiklerini kapatıyor; yeni bağımlılık yok.
2. **G1, ardından G4:** Kayıt yapısı kararından sonra. G4, G1'e dayanıyor.
3. **A1:** Gemini yanıtındaki kullanım bilgisinin biçimi doğrulandıktan sonra.
4. **G2:** Kur kararı ve `.xlsx` kütüphanesine onay verildikten sonra.
5. **G3:** PDF kütüphanesine onay verildikten sonra. G2'nin malzeme listesini kullanıyor.
6. **G5, G6:** Mevcut hesap sınıflarıyla yapılabilir. G6, G4'ün karşılaştırma bileşeninden yararlanıyor.
7. **G9, G11:** Örnek uçuş kaydı ve mevzuat araştırması gerekiyor.
8. **A5, A6:** GitHub'a gönderimden sonra. **A4** en büyük metin taşıma işi.
