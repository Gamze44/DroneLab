# Şartname yüklemesi: desteklenen dosyalar ve boyut sınırları

> Durum: 21 Kasım 2026, `gelistirme` dalı (commit `d738ae3`). Bu belge yalnızca mevcut durumu
> raporlar; kod değiştirilmedi. Satır numaraları `gelistirme` dalındaki dosyalara aittir.
> Kurulu sürümler: FastAPI 0.163.0, Starlette 1.10.0, uvicorn 0.54.0, python-multipart 0.0.33,
> pypdf 7.1.0, python-docx 1.2.0.

## Akış özeti

1. **Arayüz:** Kullanıcı dosyayı iki yerden seçer:
   - Şartname sekmesi: `arayuz/statik/drone.html:333`, gönderim `arayuz/statik/sartname.js:72-91`
   - Ana sayfadaki yeni drone formu: `arayuz/statik/index.html:71`, gönderim `arayuz/statik/ana_sayfa.js:51-52`

   Dosya `multipart/form-data` ile `POST /api/sartnameler` ucuna gider. Arayüzde boyut veya
   tür için hiçbir JavaScript kontrolü yoktur.
2. **Starlette:** İstek gövdesini çözer. Dosya parçası 1 MB'a kadar bellekte, sonrası diskte
   geçici bir dosyada (`SpooledTemporaryFile`) tutulur. Dosya parçasına boyut sınırı uygulanmaz.
   Bu adım, uygulama koduna gelmeden önce **bütün dosya alınarak** tamamlanır.
3. **Sunucu ucu:** `arayuz/sartname_rotalari.py:97-106`.
   - Uzantı yalnızca dosya adından kontrol edilir (`:100`).
   - Dosya 1 MB'lık parçalarla geçici klasöre kopyalanırken boyut sayılır (`:103` →
     `arayuz/drone_rotalari.py:123-145`).
4. **Servis:** `sartname/servis.py:79-107`.
   - Belgeden metin çıkarılır (`sartname/metin_cikarici.py`).
   - Belge `veri/sartname_dosyalari/` klasörüne kopyalanır, metin veritabanına yazılır.
5. **Model API'si:** Kullanıcı "Gemini ile maddeleri çıkar" derse
   (`sartname/servis.py:147-166`), **dosya değil, çıkarılmış metin** Gemini'ye gönderilir
   (`sartname/cikarim.py:63-72`, `arastirma/gemini.py`).

> **Not – Anthropic API:** Bu akışta Anthropic (Claude) API'si kullanılmıyor. Program yalnızca
> Google Gemini'ye istek gönderiyor (kullanıcı kararı). Bu yüzden Anthropic API sınırları bu
> programa uygulanmaz ve kontrol edilmedi. "API sınırı" sütunundaki değerler Gemini
> belgelerinden alındı.

## Tablo

"MB" kodda 1024 × 1024 bayttır (`arayuz/drone_rotalari.py:40`); 30 MB = **31.457.280 bayt**.

| Dosya türü | Uzantı ve MIME | Arayüz sınırı | Sunucu sınırı | API sınırı | Minimum | Maksimum (fiilen geçerli) | Kaynak |
|---|---|---|---|---|---|---|---|
| **PDF** | `.pdf`. MIME **kontrol edilmiyor**; yalnızca uzantıya bakılıyor | Tür: `accept=".pdf,.docx"` yalnızca dosya seçicide bir filtre, zorlayıcı değil. Boyut: **tanımsız** (JS kontrolü yok) | Kod: en çok 30 MB; 0 bayt reddedilir; parolalı PDF reddedilir; okunamayan PDF reddedilir. Starlette: dosya parçasına **tanımsız** (sınır yok) | Dosya gönderilmez. Metnin ilk **300.000 karakteri** gönderilir (kod). Gemini 3.6 Flash giriş sınırı **1.048.576 token**. Sayfa sayısı sınırı: kodda **tanımsız** (pypdf her sayfayı okur) | **1 bayt** (0 bayt reddedilir). Metni olmayan (taranmış) PDF kabul edilir ama madde çıkarımı yapılamaz | **30 MB (31.457.280 bayt)**. Ancak bu sınır dosya tamamen alındıktan sonra uygulanır; ağ aktarımı ve geçici disk kullanımı fiilen **sınırsız** | `cekirdek/ayarlar.py:71`; `arayuz/drone_rotalari.py:134-145`; `sartname/metin_cikarici.py:16,61,68-72`; `sartname/cikarim.py:17,65-70`; `starlette/formparsers.py:135,171-176,218`; [Gemini 3.6 Flash](https://aistudio.google.com/docs/models/gemini-3.6-flash) |
| **Word** | `.docx`. MIME **kontrol edilmiyor** | PDF ile aynı | Kod: en çok 30 MB; 0 bayt reddedilir; açılamayan dosya reddedilir. Açılmış (sıkıştırılmamış) içerik boyutu: **tanımsız** | PDF ile aynı (metnin ilk 300.000 karakteri) | **1 bayt** | **30 MB (31.457.280 bayt)**. Aynı uyarı: sınır alım bittikten sonra uygulanır | `sartname/metin_cikarici.py:16,82-92`; diğerleri PDF ile aynı |
| Eski Word | `.doc` | Seçicide görünmez ("Tüm dosyalar" seçilirse seçilebilir) | **Reddedilir** (415). Kullanıcıya ".docx olarak kaydet" rehberi gösterilir | — | — | Yüklenemez | `sartname/metin_cikarici.py:34-41` |
| Görsel ve diğerleri | `.jpg`, `.png`, `.txt`, `.odt` vb. | Seçicide görünmez | **Reddedilir** (415) | — | — | Yüklenemez (görsel işleme yok) | `sartname/metin_cikarici.py:34-41` |

**Aynı istekteki form alanları:**

| Alan | Arayüz | Sunucu |
|---|---|---|
| `ad` (şartname adı) | `maxlength="120"` | Boş olamaz (`sartname/servis.py:92-93`); uzunluk kodda tanımsız; Starlette alan sınırı **1 MB** (`starlette/formparsers.py:137,172-173`) |
| `drone_kimlik` | — | Tam sayı olmalı; drone yoksa 404 |

**Gemini tarafında doğrulanan ve doğrulanamayan değerler:**

| Konu | Değer | Kaynak |
|---|---|---|
| Giriş sınırı (gemini-3.6-flash, 3.8-flash, 3.5-flash-lite) | 1.048.576 token | [model sayfası](https://aistudio.google.com/docs/models/gemini-3.6-flash), [tokens](https://aistudio.google.com/docs/tokens) |
| Çıkış sınırı | 65.536 token | aynı sayfalar |
| Karakter / token oranı | "yaklaşık 4 karakter = 1 token". 300.000 karakter ≈ 75.000 token. Türkçe metinde oran farklı olabilir: **doğrulanamadı** | [tokens](https://aistudio.google.com/docs/tokens) |
| Toplam istek boyutu (satır içi) | 100 MB'a kadar (üstü için Files API). 300.000 karakter en çok yaklaşık 1,2 MB eder, sınırın çok altında | [files](https://aistudio.google.com/docs/files) |
| PDF dosya sınırı (50 MB) | **Uygulanmaz**: program PDF dosyası göndermiyor | [files](https://aistudio.google.com/docs/files) |
| Ücretsiz katman RPM / TPM / RPD (gemini-3.6-flash) | **doğrulanamadı** (belgede bu model için tablo yok) | [rate-limits](https://aistudio.google.com/docs/rate-limits) |
| İstek zaman aşımı | 90 sn (kod) | `arastirma/gemini.py:34` |
| Programın günlük istek sınırı | Varsayılan 20 (ayarlardan 1–200) | `arastirma/ayarlar.py` |

## Dikkat çeken noktalar

**Katmanlar arası çelişkiler**

1. **Arayüzde boyut kontrolü yok, sunucu 30 MB.** Kullanıcı örneğin 500 MB'lık bir dosya
   seçebilir. Dosya ilerleme göstergesi olmadan tamamen yüklenir; hata ancak yükleme bittikten
   sonra gelir.
2. **30 MB sınırı geç uygulanıyor.** Starlette dosyanın tamamını geçici diske yazdıktan sonra
   uygulama sayımı başlar (`starlette/formparsers.py:218`). Çok büyük bir yükleme geçici
   klasörü doldurabilir. uvicorn'da istek gövdesi sınırı yok (yapılandırmada böyle bir seçenek
   bulunmuyor).
3. **Metin iki kez sessizce kısaltılıyor.**
   - Saklanırken 1.000.000 karakterden sonrası atılıyor (`sartname/metin_cikarici.py:61`);
     kullanıcıya bildirilmiyor.
   - Gemini'ye yalnızca ilk 300.000 karakter gidiyor (`sartname/cikarim.py:65-70`). Modele
     "yalnızca baş kısmı gönderildi" notu ekleniyor ama kullanıcı bunu görmüyor. Uzun bir
     şartnamenin son bölümlerindeki maddeler kaçabilir.
4. **Hata mesajı yanıltıcı.** Boyut aşımı mesajı "sınırı ayarlardan artırın" diyor
   (`arayuz/drone_rotalari.py:140-142`). Ayarlar ekranında böyle bir seçenek yok; sınır yalnızca
   koddaki `EN_BUYUK_SARTNAME_MB` sabitinden değişiyor.

**Sınırsız bırakılmış yerler**

5. **Tür kontrolü:** MIME türüne ve dosya içeriğinin imzasına (`%PDF-`, ZIP başlığı) bakılmıyor.
   Uzantısı `.pdf` yapılmış başka bir dosya ayrıştırıcıda hata verir ve 400 "Belge okunamadı"
   döner. Güvenli bir sonuç ama nedeni belirsiz.
6. **Sayfa ve açılmış boyut:** PDF sayfa sayısı ve `.docx`'in açılmış (sıkıştırılmamış) boyutu
   için sınır yok. Çok sayfalı ya da kötü niyetli sıkıştırılmış (zip bombası) bir belge, işlemciyi
   ve belleği uzun süre meşgul edebilir. Yerel, tek kullanıcılı bir program için risk düşük.
7. **`ad` alanı:** Uzunluğu yalnızca arayüzde (120) sınırlı; sunucuda yalnızca Starlette'in
   1 MB alan sınırı var.

**Büyük dosyada olası hatalar**

8. **Yükleme süresi:** Metin çıkarma senkron yapılıyor. Büyük bir PDF'te istek uzun sürer; bu
   sırada arayüzde yalnızca "Belge okunuyor…" yazar.
9. **Gemini isteği:** 300.000 karakterlik bir istek ücretsiz katmanın dakikalık token sınırına
   takılabilir (sınır **doğrulanamadı**) ya da 90 saniyelik zaman aşımını geçebilir. Bu durumda
   kullanıcı 429 veya "Gemini'ye ulaşılamadı" hatası görür.
10. **Taranmış PDF:** Yükleme başarılı olur ama metin 0 karakterdir. Maddeler elle girilmelidir;
    arayüz bunu yükleme sonrasında uyarıyla bildiriyor.

## Değişiklik önerileri (uygulanmadı)

1. **Arayüzde erken kontrol:** Dosya seçilince `file.size` ve uzantı kontrol edilsin. 30 MB'ı
   aşan dosya gönderilmeden uyarı verilsin.
2. **Sunucuda erken red:** `Content-Length` başlığı uç noktaya gelmeden (ör. bir ara katmanla)
   kontrol edilsin; böylece büyük yüklemeler diske yazılmadan reddedilir.
3. **Kesilmeyi bildirme:** Metin 1.000.000 veya 300.000 karakterde kesildiğinde kullanıcıya
   bildirilsin. Uzun belgeler için metin parçalara bölünüp birden çok istekle işlenebilir.
4. **Hata mesajını düzeltme:** "Ayarlardan artırın" ifadesi düzeltilsin ya da sınır ayarlar
   ekranına taşınsın.
5. **İçerik imzası:** Dosyanın ilk baytlarına bakılsın (`%PDF-`, `PK`); uzantı ile içerik
   uyuşmazsa açık bir mesaj verilsin.
6. **İşleme sınırları:** PDF sayfa sayısına ve `.docx` açılmış boyutuna bir üst sınır konsun.
7. **Gemini isteği:** İsteğe bir çıkış sınırı (`max_output_tokens`) eklensin; ücretsiz katmanın
   güncel limitleri AI Studio'dan (https://aistudio.google.com/rate-limit) kontrol edilip
   gönderilen metin uzunluğu buna göre ayarlansın.
