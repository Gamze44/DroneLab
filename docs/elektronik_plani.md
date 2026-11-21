# Elektronik Bölümü – Plan

Durum: taslak, kod yazılmadı. Son güncelleme: 15.11.2026

Bu belge, drone çalışma sayfasındaki **2. Elektronik** sekmesinin tasarımını anlatır.
Belirsiz noktalar en sondaki "Açık sorular" bölümünde listelenmiştir; yanıtlara göre plan güncellenecek.

---

## 1. Temel ilke: araştırma ile kontrol ayrı

| İş | Kim yapar | Neden |
|---|---|---|
| Parçayı internette bulmak, teknik değerlerini çıkarmak, alternatif önermek | **Yapay zeka modeli** (web aramalı) | Sayısız ürün ve değişen katalog; elle veritabanı tutmak mümkün değil |
| Uyum kontrolü (gerilim, akım, montaj, protokol…) | **Kendi kodumuz** | Sonuç tekrarlanabilir, test edilebilir ve açıklanabilir olmalı |
| Hesaplar (toplam ağırlık, itki/ağırlık, uçuş süresi…) | **Kendi kodumuz** | Model hesap hatası yapabilir; formüller sabit ve denetlenebilir olmalı |

- Model yalnızca **veri** üretir; o veri şemaya göre doğrulanır, kullanıcıya gösterilir ve onaylanır.
- Modelin "uyumludur" demesi hiçbir yerde sonuç olarak kullanılmaz.
- **Program modelsiz de çalışır:** API anahtarı yoksa veya internet yoksa kullanıcı tüm teknik değerleri elle girer. Kontroller ve hesaplar aynen çalışır.

---

## 2. Parça türleri ve teknik alanlar

### 2.1 Çekirdek parçalar (ilk sürüm, tam uyum kontrolü)

Her parçada ortak alanlar bulunur: **marka, model, ağırlık (g), adet, kaynak bağlantıları, doğrulama durumu**.

| Tür | Türe özel teknik alanlar |
|---|---|
| **Motor** | stator boyutu (ör. 2207), KV (dev/dk/V), desteklenen hücre aralığı (S en az–en çok), en büyük akım (A), en büyük güç (W), montaj deseni (ör. 16×16 M3), mil çapı (mm), önerilen pervane çapı aralığı (inç), **itki tablosu** (isteğe bağlı, bkz. 2.3) |
| **Pervane** | çap (inç), adım/pitch (inç), kanat sayısı, göbek tipi / mil deliği (mm) |
| **ESC** | yapı (tekli / 4'ü 1 arada), sürekli akım (A), anlık akım (A), hücre aralığı, montaj deseni (30,5×30,5 / 20×20 / 25,5×25,5), desteklenen protokoller (PWM, OneShot, DShot300/600…), yazılım (BLHeli_S, BLHeli_32, AM32, Bluejay), akım sensörü var mı |
| **Pil** | hücre sayısı (S), kapasite (mAh), sürekli deşarj oranı (C), kimya (LiPo, LiHV, Li-ion), konnektör (XT30/XT60/XT90…) |
| **Uçuş kontrol kartı (FC)** | montaj deseni, giriş gerilimi aralığı (V veya S), işlemci (F4/F7/H7), UART sayısı, desteklenen ESC protokolleri, BEC çıkışları (gerilim + akım listesi), yazılım (Betaflight, INAV, ArduPilot), dahili PDB var mı |
| **Alıcı** | protokol (ELRS/CRSF, SBUS, IBUS, …), bağlantı türü (UART / SBUS girişi), çalışma gerilimi aralığı, frekans bandı |
| **Güç dağıtımı (PDB)** | sürekli akım (A), giriş gerilimi aralığı, BEC çıkışları, montaj deseni |

### 2.2 İkinci grup (aynı yapı, sınırlı kontrol)

Kamera, VTX (video verici), GPS, telemetri modülü, yük (payload).

- Alanlar: ortak alanlar + çalışma gerilimi aralığı + (varsa) çektiği akım + kısa açıklama.
- **İlk sürümde yalnızca iki kontrol yapılır:**
  - Ağırlık toplam ağırlığa eklenir.
  - Gerilim, beslendiği kaynağın (FC/PDB BEC çıkışı veya pil) gerilimiyle uyumlu olmalıdır.
- Protokol uyumu (ör. analog/dijital video sistemi) sonraki sürümde eklenir.

### 2.3 İtki tablosu

- Motor + pervane + gerilim üçlüsü için satırlar tutulur: gaz %, itki (g), akım (A), güç (W), devir.
- Kaynakları: üreticinin test verisi, model araştırması (kaynak bağlantısıyla) veya kullanıcının elle girdiği değerler.
- Tablo yoksa itki **yaklaşık fizik formülüyle** hesaplanır ve sonuç **"tahmini"** etiketiyle gösterilir (bkz. 5.3).

### 2.4 Değer kökeni

Her teknik değerin yanında nereden geldiği saklanır:

- `kaynak_url`: değerin bulunduğu sayfa.
- `koken`: `model` (yapay zeka buldu), `kullanici` (elle girildi) veya `hesap` (formülle türetildi).
- `guven`: model bulduysa yüksek / orta / düşük.

Ekranda modelin bulduğu değerler ayrı bir işaretle gösterilir. Kullanıcının elle girdiği değer her zaman önceliklidir.

---

## 3. Yerel parça kataloğu (SQLite)

Mevcut `veri/dronelar.sqlite3` dosyasına eklenecek tablolar:

| Tablo | Alanlar (özet) | Not |
|---|---|---|
| `parcalar` | kimlik, tur, marka, model, **arama_anahtari** (benzersiz), agirlik_g, teknik_json, kaynaklar_json, durum, olusturma/guncelleme zamanı | Tüm dronelar arasında paylaşılan katalog |
| `itki_kayitlari` | parca_kimlik (motor), pervane, gerilim_v, gaz_yuzde, itki_g, akim_a, guc_w, kaynak_url | Motor başına çok satır |
| `fiyat_kayitlari` | parca_kimlik, magaza, ulke, fiyat, para_birimi, stok_metni, url, bulunma_zamani | Her zaman "kontrol edilmedi" notuyla gösterilir |
| `doviz_kurlari` | para_birimi, tl_karsiligi, kur_tarihi, alinma_zamani | Günde bir kez TCMB'den alınır (bkz. 5.5) |
| `drone_parcalari` | drone_kimlik, parca_kimlik, adet, besleme_kaynagi (ikinci grup için), eklenme zamanı | Drone silinince CASCADE ile silinir |
| `drone_hedefleri` | drone_kimlik, ucus_suresi_dk, yuk_g, butce, para_birimi | Öneri için kullanıcı hedefleri |

Kurallar:

- **Arama anahtarı:** `tur + marka + model` küçük harfe çevrilir, boşluk ve noktalama sadeleştirilir. Böylece "T-Motor F60 Pro V" ile "tmotor f60pro v" aynı parça sayılır. Aynı anahtar katalogda varsa **internette tekrar aranmaz**; kullanıcı isterse "Yeniden araştır" düğmesiyle günceller.
- **Doğrulama durumu:**
  - Modelin bulduğu parça `dogrulanmadi` olarak kaydedilir.
  - Kullanıcı değerleri kontrol edip "Onayla" deyince `dogrulandi` olur.
  - Elle girilen parça doğrudan `dogrulandi` sayılır.
  - Doğrulanmamış parçalarla yapılan hesaplar ekranda uyarıyla gösterilir.
- **Şema sürümü 2'ye çıkar.** Mevcut sürüm 1 dosyalar, var olan veriye dokunmadan yeni tabloları ekleyen bir yükseltmeyle açılır.

---

## 4. Akışlar

### 4.1 Parça ekleme (elimdeki parça)

1. Kullanıcı türü seçer (motor, ESC…) ve **ad/marka, model, ağırlık** ile adedi girer.
2. Program önce yerel katalogda arar. Parça varsa formu hemen doldurur.
3. Katalogda yoksa ve API anahtarı varsa "Bilgileri bul" ile araştırma başlar. Bu birkaç saniye ile bir dakika arası sürebilir; ekranda ilerleme gösterilir.
4. Model, parçanın şemaya uygun JSON'unu döndürür. Program bu JSON'u doğrular:
   - Alan türleri doğru mu?
   - Değerler mantıklı aralıkta mı? Örneğin KV 100–10.000, ağırlık > 0, hücre sayısı 1–14.
   - Aralık dışı değerler boş bırakılır ve "bulunamadı / şüpheli" işaretlenir.
5. Form, değerler ve kaynak bağlantılarıyla dolu olarak açılır. Kullanıcı düzeltir ve **Onaylar**.
6. Kullanıcının girdiği ağırlık, modelin bulduğu ağırlıktan önceliklidir. İkisi %10'dan fazla farklıysa uyarı verilir.

### 4.2 Öneri ("Öner" düğmesi)

**Ön koşul:** Hedefler kartı doldurulmuş olmalı.

Hedefler kartının alanları:

| Alan | Nereden gelir |
|---|---|
| Uçuş süresi (dk) | Kullanıcı girer |
| Taşınacak yük (g) | Kullanıcı girer |
| Bütçe | Kullanıcı girer |
| Drone türü, motor sayısı | Drone kaydından gelir |
| Kullanım amacı | Drone kaydından gelir; itki/ağırlık hedefini belirler |

**Sıralı akış.** Her öneri önceki seçimlere bağlıdır:

1. Motor + pervane
2. ESC
3. Pil
4. Uçuş kontrol kartı
5. Diğer parçalar (alıcı, PDB, ikinci grup)

Bir adım atlanırsa sonraki adım daha az kısıtla çalışır ve bunu ekranda söyler.

**Her öneri adımında:**

1. Program bir kısıt paketi hazırlar ve modele gönderir:
   - Hedefler.
   - Şasi bilgisi (ağırlık, ölçüler, desteklenen en büyük pervane).
   - Seçilmiş parçaların teknik değerleri.
   - Kalan bütçe.
   - Şartname kısıtları (bkz. 4.3).
   - Türkiye mağaza önceliği ayarı.
2. Model 2–3 aday döndürür. Her aday için şunlar gelir:
   - Teknik değerler.
   - Kısa gerekçe.
   - Kaynak bağlantıları.
   - Varsa fiyat ve mağaza.
3. **Kendi kodumuz** her adayı mevcut seçimlerle birlikte uyum kontrolünden ve hesaplardan geçirir.
4. Ekranda her aday şu bilgilerle gösterilir:
   - Uyum sonucu (✓ / ✗ / ?).
   - Hesap özeti, ör. "bu motorla itki/ağırlık 4,2 (tahmini)".
   - Gerekçe ve kaynak bağlantısı.
   - Fiyat ("kontrol edilmedi" notuyla).
5. Kullanıcı bir adayı seçer. Aday katalogda `dogrulanmadi` olarak kaydedilir ve drone'a eklenir. Kullanıcı değerleri onaylayınca `dogrulandi` olur.

**Sıralama:** Uyumsuz (✗) adaylar en sona gelir. Uyumlu adaylar kendi aralarında hedefe yakınlığa göre sıralanır: uçuş süresi, bütçe ve itki/ağırlık. Modelin kendi sıralaması kullanılmaz.

### 4.3 Şartname bağlantısı (şimdilik boş)

- Kısıtlar ortak bir biçimde tanımlanır: büyüklük, sınır türü (en az / en çok / eşit / zorunlu), değer, birim, kaynak maddesi.
- Bir "kısıt kaynağı" arayüzü olur. Şimdilik **boş kaynak** kullanılır.
- Şartname modülü eklendiğinde kısıtları bu arayüzle verecek. Uyum kontrolü kısıtları aynı yolla okuduğu için elektronik koduna dokunmak gerekmeyecek.

### 4.4 Zorunlu parçalar

Drone türüne göre bir kural tablosu tutulur. Bu tablo değiştirilebilir (`# DEĞİŞTİRİLEBİLİR`).

**Çok rotorlu (ilk sürüm):**

| Parça | Zorunluluk |
|---|---|
| Motor | motor sayısı kadar |
| Pervane | motor sayısı kadar |
| ESC | motor sayısı kadar kanal (4'ü 1 arada ESC 4 kanal sayılır) |
| Pil, FC, alıcı | 1'er adet |
| Güç dağıtımı | ESC 4'ü 1 arada ise veya FC'de dahili PDB varsa zorunlu değil |
| GPS | amaç "Yük taşıma" veya "Hava çekimi" ise önerilir ama zorunlu değil |

- Eksik zorunlu parçalar listede "eksik" olarak işaretlenir. Hesaplar eksik parçalar varken de yapılır, ama sonuç "eksik parça var" uyarısıyla gösterilir.
- **Sabit kanat:** Kural tablosu yapısı buna hazır kurulur, ancak sabit kanat sonraki sürüme bırakıldığı için ilk sürümde kuralı yazılmaz.

### 4.5 Şasi ağırlığı

- Şasi sekmesindeki ağırlık toplam ağırlığa otomatik eklenir.
- Ağırlık girilmemişse toplam ağırlık "şasi ağırlığı eksik" uyarısıyla gösterilir.

---

## 5. Uyum kontrolleri ve hesaplar (kendi kodumuz)

Her kontrol üç sonuçtan birini verir:

- **✓ uygun**
- **✗ uyumsuz** (sebebi ve farkı yazılır)
- **? doğrulanamıyor** (gerekli değer eksik; hangi değerin eksik olduğu yazılır)

Eksik veri hiçbir zaman "uygun" sayılmaz.

### 5.1 Çekirdek uyum kontrolleri

| # | Kontrol | Kural (varsayılan eşikler değiştirilebilir) |
|---|---|---|
| K1 | Pil ↔ motor | Pil S, motorun hücre aralığında |
| K2 | Pil ↔ ESC | Pil S, ESC hücre aralığında |
| K3 | Pil ↔ FC / PDB | Pilin dolu gerilimi (S × 4,2 V; LiHV için 4,35 V) FC/PDB giriş aralığında |
| K4 | Motor ↔ pervane | Pervane çapı motorun önerilen aralığında; yoksa stator boyutuna göre sezgisel tablo (tahmini) |
| K5 | Pervane ↔ şasi | Pervane çapı, şasi ölçüsünden **tahmin edilen** en büyük pervaneyi aşmıyor (bkz. 5.4); sonuç her zaman "tahmini" |
| K6 | ESC ↔ motor akımı | ESC sürekli akımı ≥ motor en büyük akımı × (1 + güvenlik payı); varsayılan pay %20 |
| K7 | Pil ↔ toplam akım | Pil sürekli akımı (Ah × C) ≥ toplam en büyük akım × (1 + pay); varsayılan pay %20 |
| K8 | FC ↔ ESC montaj | Yığın (stack) kuruluyorsa montaj desenleri aynı |
| K9 | FC ↔ ESC protokol | ESC'nin desteklediği protokollerden en az biri FC'de destekleniyor |
| K10 | Alıcı ↔ FC | Alıcı protokolü FC yazılımınca destekleniyor; bağlantı için boş UART/SBUS girişi var; alıcı gerilimi bir BEC çıkışıyla uyumlu |
| K11 | Motor sayısı | Eklenen motor sayısı drone türüyle uyumlu |
| K12 | Konnektör | Pil konnektörü ile ESC/PDB konnektörü aynı; değilse uyarı (✗ değil, ⚠) |
| K13 | İkinci grup gerilim | Her parçanın gerilimi, seçilen besleme kaynağının çıkış gerilimiyle uyumlu |
| K14 | Şartname | Her şartname kısıtı için ✓ / ✗ / ? (şartname modülü gelince) |

### 5.2 Hesaplanan çıktılar

| Çıktı | Formül | Not |
|---|---|---|
| Toplam ağırlık (g) | şasi + Σ(parça ağırlığı × adet) + yük + kablo/vida payı | Pay varsayılan %5, tahmini |
| Toplam en büyük itki (g) | motor sayısı × motor başına en büyük itki | İtki tablosundan; yoksa tahmini |
| İtki/ağırlık oranı | toplam en büyük itki / toplam ağırlık | Hedef amaca göre değişir (bkz. aşağıdaki tablo) |
| Asılı kalma gaz oranı (%) | İtki tablosunda "ağırlık / motor sayısı" itkisine karşılık gelen gaz, doğrusal ara değerle | Tablo yoksa ≈ √(asılı itki / en büyük itki) × 100, tahmini |
| Asılı kalma akımı (A) | İtki tablosundan | Tablo yoksa momentum teorisiyle, tahmini (5.3) |
| Toplam en büyük akım (A) | motor sayısı × motor en büyük akımı + diğer tüketiciler | Pil ve ESC kontrolünde kullanılır |
| Uçuş süresi (dk) | (kapasite Ah × kullanılabilir oran) / ortalama akım × 60 | Kullanılabilir oran varsayılan %80; ortalama akım = asılı akım × uçuş tarzı katsayısı. Her zaman **tahmini** |

İtki/ağırlık hedefleri (varsayılan, değiştirilebilir):

| Amaç | Hedef itki/ağırlık |
|---|---|
| Yük taşıma / çekim | ≥ 2 |
| Serbest uçuş | ≥ 5 |
| FPV yarış | ≥ 7 |

Uçuş tarzı katsayıları (varsayılan, değiştirilebilir):

| Amaç | Katsayı |
|---|---|
| Çekim / yük | 1,1 |
| Serbest uçuş | 2,0 |
| Yarış | 3,0 |

### 5.3 Tahmini hesaplar (itki verisi yoksa)

- **En büyük devir:** n ≈ KV × pil nominal gerilimi × yük altındaki düşüş katsayısı (varsayılan 0,8).
- **İtki:** T = C_T · ρ · n² · D⁴
  - ρ: hava yoğunluğu, 1,225 kg/m³.
  - D: pervane çapı.
  - C_T: pervane itki katsayısı; adım/çap oranına göre bir tablodan alınır (varsayılan aralık 0,08–0,15).
- **Asılı kalma gücü:** P = T^1,5 / √(2ρA) / (FoM × η_motor+ESC)
  - A: pervane disk alanı.
  - FoM: pervane verim katsayısı, varsayılan 0,65.
  - η_motor+ESC: motor ve ESC verimi, varsayılan 0,80.
  - Akım = P / gerilim.
- Bütün katsayılar tek bir ayar dosyasında `# DEĞİŞTİRİLEBİLİR:` olarak durur.
- Kullanıcı gerçek itki verisi girince tahmin yerine o veri kullanılır.
- Ekranda tahmini değerlerin yanında hangi değerin eksik olduğu yazılır, ör. "itki tablosu yok".

### 5.4 Şasi ölçüsünden en büyük pervane tahmini (K5)

Şasi dosyasından yalnızca sınır kutusu bilinir (en × boy); motorların tam yeri bilinmez. Bu yüzden tahmin kabadır ve **her zaman "tahmini"** etiketiyle gösterilir.

1. **Dingil mesafesi** (çapraz motor–motor), W ≈ √(en² + boy²) × k.
   - k, kol uçlarının motor merkezinden taşan payıdır; varsayılan 0,9.
2. **Komşu motorlar arası mesafe**, d = W × sin(π / motor sayısı).
   - Quad için W/√2, hexa için W/2.
3. **En büyük pervane çapı** ≈ d − pervane uçları arası boşluk.
   - Boşluk varsayılan 6 mm.
   - Sonuç inçe çevrilir ve aşağı yuvarlanır.

Notlar:

- Şasi dosyası yoksa veya birim onaylanmadıysa K5 "? doğrulanamıyor" olur.
- Pervane bu sınıra çok yakınsa ("±0,5 inç") ✗ yerine ⚠ uyarısı verilir, çünkü tahmin kesin değildir.
- k ve boşluk değerleri ayar dosyasında `# DEĞİŞTİRİLEBİLİR:` olarak durur.

### 5.5 Fiyat ve kur

- Bütçe TL olarak girilir.
- **Yabancı para birimindeki fiyatlar** güncel kurla TL'ye çevrilir. Çevrilen tutar **"tahmini"** etiketi, kullanılan kur ve kur tarihiyle gösterilir. Fiyatın kendisi zaten "kontrol edilmedi" notuyla gösterilir.
- **Kur kaynağı:** Türkiye Cumhuriyet Merkez Bankası'nın günlük kur dosyası (`tcmb.gov.tr/kurlar/today.xml`, anahtar gerektirmez). Kur kodla alınır, yapay zekaya sorulmaz.
- Kur günde bir kez alınır ve veritabanında saklanır.
- Kur alınamazsa son kayıtlı kur, tarihiyle birlikte kullanılır. Hiç kur yoksa yabancı fiyat bütçeye katılmaz ve "kur alınamadı" notu düşülür.
- Bütçe kontrolü sonucu kesin değil, "tahmini"dir.

---

## 6. Araştırma katmanı (yapay zeka)

- **Sağlayıcı: Google Gemini API** (kullanıcının kararı).
  - Gemini'nin Google Arama ile desteklenen yanıt özelliği (grounding) kullanılır. Bu özellik yanıtla birlikte kaynak sayfa bağlantılarını da döndürür.
  - Kod sağlayıcıdan bağımsız yazılır: `ArastirmaSaglayicisi` adlı bir arayüz ve onun `GeminiSaglayicisi` uygulaması olur. İleride başka bir sağlayıcı eklemek için yeni bir uygulama sınıfı yazmak yeterli olur.
- **İki adımlı çağrı:**
  1. **Arama adımı:** Gemini, Google Arama ile parçayı araştırır ve kaynaklı bir metin döndürür. Kaynak bağlantıları yanıtın ek bilgisinden (grounding metadata) alınır, modelin metninden değil.
  2. **Çıkarım adımı:** Bu metin, parça türünün JSON şemasıyla (yapılandırılmış çıktı) ikinci bir çağrıya verilir. Her alan için değer, birim, kaynak bağlantısı ve güven düzeyi gelir.
  - Bazı model sürümlerinde arama ile JSON şeması aynı çağrıda birlikte kullanılamayabiliyor. İki adımlı yapı her durumda çalışır. Uygulama aşamasında güncel belgeler kontrol edilecek; destekleniyorsa tek çağrıya indirilebilir.
  - Program aldığı JSON'u yine kendi doğrulayıcısından geçirir (bkz. 4.1).
- **Model ve fiyat:**
  - Hangi Gemini modelinin kullanılacağı ayardan seçilir.
  - Güncel model adları ve fiyatlar E3 aşamasında Google'ın belgelerinden kontrol edilip varsayılan olarak yazılacak.
  - Arama ile desteklenen istekler ayrıca ücretlendirilebilir; maliyet takibi bunu da sayar.
- **Mevcut istemciden yararlanma:** Kullanıcının `D:\uzay-koc` projesinde çalışan bir Gemini istemcisi var (`sohbet/gemini.py`).
  - Gemini Interactions API'ye REST ile, yalnızca standart kütüphane (`urllib`) kullanarak bağlanıyor.
  - JSON şemalı çıktı (`json_uret`), Türkçe hata mesajları ve SSL ayarı (MSYS2 Python için de) hazır.
  - Bu istemci **örnek alınarak** bu projeye uyarlanır; kod iki proje arasında doğrudan içe aktarılmaz. Böylece iki proje birbirine bağımlı olmaz.
  - Bu projeye eklenecek kısım arama adımıdır (Google Arama aracı). Bu aracın Interactions API'deki biçimi E3'te güncel belgelerden kontrol edilecek.
- **Bağımlılık:** Yok. Standart kütüphane yeterli, `google-genai` paketine gerek kalmaz.
- **İş akışı:**
  - Araştırma uzun sürebildiği için arka plan işi olarak çalışır.
  - Arayüz iş numarasıyla durumu sorar ve ilerleme gösterir. Kullanıcı bu sırada sayfada çalışmaya devam edebilir.
- **Maliyet koruması:**
  - Her istekte arama sayısı sınırlanır (`max_uses`, varsayılan 5).
  - Harcanan token sayısı ve tahmini ücret bir tabloya yazılır.
  - Ayarlardan girilen aylık sınır aşılırsa yeni araştırma başlatılmaz ve kullanıcıya Türkçe mesaj gösterilir.
- **Ret durumu:** Model isteği reddederse bu durum ele alınır ve kullanıcıya "araştırma yapılamadı, değerleri elle girin" mesajı gösterilir.
- **Güvenlik:**
  - Web sayfalarından gelen metin yalnızca veri olarak kullanılır.
  - Modelin döndürdüğü hiçbir metin kod veya komut olarak çalıştırılmaz.
  - Bağlantılar kullanıcıya gösterilir, program kendiliğinden açmaz.

---

## 7. Ayarlar

Ayarlar yerel ayar dosyasında tutulur, kodun içinde değil. Dosya `veri/ayarlar_yerel.json` olur.

**API anahtarının aranma sırası:**

1. Ortam değişkeni `GEMINI_API_KEY` veya `GOOGLE_API_KEY` (uzay-koc projesiyle aynı adlar).
2. Bu projenin yerel anahtar dosyası: `veri/gemini_anahtari.txt`.
3. Hiçbiri yoksa yapay zeka özellikleri kapalıdır, elle giriş açıktır.

**Kullanıcı kararı (15.11.2026):** E3 aşamasında `D:\uzay-koc\yerel\gemini_anahtari.txt` dosyası `veri/gemini_anahtari.txt` olarak kopyalanır.

- Kopya bağımsızdır: uzay-koc'ta anahtar değişirse buradaki eski kalır. Ayarlar ekranından yeni anahtar girilebilir.
- `veri/` klasörü yedeklenip başkasıyla paylaşılacaksa önce bu dosya çıkarılmalıdır. Ayarlar ekranında bu konuda uyarı gösterilir.

**Anahtarın güvenliği:**

- Anahtar hiçbir API yanıtında ve ekranda gösterilmez; yalnızca "anahtar var / yok" bilgisi döner.
- Anahtar loglara yazılmaz.

| Ayar | Varsayılan |
|---|---|
| Gemini API anahtarı | boş (girilmezse yapay zeka özellikleri kapalı, elle giriş açık) |
| Gemini modeli | E3'te güncel belgelere göre belirlenecek |
| Türkiye'deki mağazalara öncelik | **açık** |
| Aylık harcama sınırı | kullanıcı girer; boşsa sınır yok, ama harcama yine gösterilir |
| Güvenlik payları, kullanılabilir pil oranı, kablo payı | 5. bölümdeki değerler |

- Ayarlar ekranı ana sayfadan açılır.
- API anahtarı ekranda maskelenir ve hiçbir zaman sunucu yanıtlarında geri gönderilmez.

---

## 8. Ekran tasarımı (Elektronik sekmesi)

1. **Hedefler kartı:** uçuş süresi, yük, bütçe. Drone türü ve motor sayısı salt okunur gelir.
2. **Parça listesi:** her parça türü için bir satır.
   - Durum: eksik (zorunlu) / eklendi / doğrulanmadı / doğrulandı.
   - Ad, ağırlık, adet.
   - Düğmeler: "Ekle", "Öner", "Düzenle", "Kaldır".
3. **Parça formu:**
   - Marka/ad, model, ağırlık, adet ve "Bilgileri bul" düğmesi.
   - Altında türe özel teknik alanlar. Her alanın yanında köken işareti ve kaynak bağlantısı bulunur.
   - "Onayla" düğmesi.
4. **Öneri paneli:** 2–3 aday kartı. Her kartta uyum rozeti, hesap özeti, gerekçe, kaynak, fiyat ("kontrol edilmedi") ve "Bunu seç" düğmesi.
5. **Sonuç paneli** (her değişiklikte yenilenir):
   - Toplam ağırlık, itki/ağırlık, asılı gaz oranı, uçuş süresi, toplam akım. Tahmini olanlar etiketli gösterilir.
   - Uyum listesi (K1–K14) ✓ / ✗ / ? ile.

Tüm değişiklikler şasi bölümünde olduğu gibi otomatik kaydedilir.

---

## 9. Kod yapısı (öneri)

```
elektronik/
  modeller.py          ParcaTuru, Parca, TeknikDeger (değer + birim + köken + kaynak), ItkiKaydi
  semalar.py           Parça türü başına alan tanımları (tek kaynak: form, doğrulama ve JSON şeması buradan üretilir)
  dogrulama.py         Teknik değer aralık denetimleri
  zorunlu_parcalar.py  Drone türüne göre kural tablosu
  uyum/                Her kontrol ayrı sınıf (K1…K14), ortak arayüz: kontrol(drone_parcalari) -> KontrolSonucu
  hesap/               Toplam ağırlık, itki, uçuş süresi; tahmini_itki.py ayrı
  kisitlar.py          Kısıt modeli + KisitKaynagi arayüzü + BosKisitKaynagi
  servis.py            Parça ekleme, katalog arama, öneri akışını yöneten servis
arastirma/
  saglayici.py         ArastirmaSaglayicisi arayüzü (sağlayıcıdan bağımsız)
  gemini_saglayicisi.py  Gemini uygulaması: arama adımı + JSON çıkarım adımı (anahtar ayardan/ortamdan okunur)
  doviz.py             TCMB kur dosyasını okur, günlük önbellek
  parca_arastirici.py  Tek parçanın teknik değerlerini bulur
  oneri_arastirici.py  Kısıt paketine göre aday üretir
  is_kuyrugu.py        Arka plan işleri + durum sorgulama
  maliyet_takibi.py    Token/ücret kaydı ve aylık sınır
depolama/
  parca_deposu.py, drone_parca_deposu.py, hedef_deposu.py, fiyat_deposu.py
  veritabani.py        Şema sürümü 2 + sürüm 1'den yükseltme
cekirdek/
  ayarlar_yerel.py     Yerel ayar dosyası okuma/yazma
```

---

## 10. Uygulama sırası (alt aşamalar)

Her alt aşama sonunda testler koşulur ve özet verilir. Yapay zeka en sona yakın eklenir; böylece kontrol ve hesap kodu modelden bağımsız test edilmiş olur.

| Alt aşama | Kapsam | Yapay zeka |
|---|---|---|
| **E1** | Veri modeli, şema sürümü 2, katalog, **elle parça ekleme**, drone'a parça bağlama, zorunlu parça işaretleme, parça listesi ekranı | yok |
| **E2** | Uyum kontrolleri K1–K13, hesaplar ve tahmini formüller, sonuç paneli | yok |
| **E3** | Ayarlar ekranı (API anahtarı, Türkiye önceliği, maliyet sınırı), parça bilgisi araştırma, doğrulama akışı | var |
| **E4** | Hedefler kartı, "Öner" akışı (sıralı adımlar, aday kontrolü, sıralama), fiyat kayıtları, TCMB kuruyla TL çevirisi | var |
| **E5** | İkinci grup parçalar (ağırlık + gerilim kontrolü) | isteğe bağlı |

---

## 11. Riskler

| Risk | Önlem |
|---|---|
| Model yanlış veya uydurma değer bulur | Kaynak bağlantısı zorunlu; aralık denetimi; kullanıcı onayı; "doğrulanmadı" işareti |
| İtki verisi bulunamaz | Tahmini formül + "tahmini" etiketi + elle itki tablosu girişi |
| Fiyat/stok eskir | "Kontrol edilmedi" notu, bulunma tarihi, kaynak bağlantısı; fiyat hesapta kesin değer sayılmaz |
| API maliyeti beklenenden yüksek olur | Arama sayısı sınırı, katalog önbelleği (aynı parça tekrar aranmaz), aylık sınır |
| İnternet / API yok | Elle giriş ile tam çalışma |
| Aynı parça farklı yazılır | Arama anahtarı sadeleştirme; kullanıcıya "katalogda benzer parça var" önerisi |

---

## 12. Kararlar ve varsayımlar

**Verilen kararlar (15.11.2026):**

| Soru | Karar |
|---|---|
| Yapay zeka sağlayıcısı | **Google Gemini API** (bkz. 6) |
| Parça girişi | **Marka + model + ağırlık** (+ adet) |
| Pervane–şasi uyumu (K5) | **Şasi ölçüsünden tahmin** (bkz. 5.4) |
| Yabancı fiyatlar | **Kurla TL'ye çevrilir**, "tahmini" gösterilir (bkz. 5.5) |

**Varsayımlar** (aksi söylenmezse bunlarla ilerlenecek):

- Güvenlik payları: ESC %20, pil %20.
- Kullanılabilir pil kapasitesi %80.
- Kablo/vida payı %5.
- İtki/ağırlık hedefleri ve uçuş tarzı katsayıları 5.2'deki tablolardaki gibi.
- Kullanıcının girdiği ağırlık, modelin bulduğu ağırlıktan önceliklidir.
- Elle girilen parça doğrudan "doğrulandı" sayılır.
- Katalog tüm dronelar arasında ortaktır.
