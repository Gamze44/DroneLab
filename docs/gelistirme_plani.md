# Geliştirme Planı – Drone Tasarım Programı

> Bu dosya Claude Code için yazıldı. Konumu: `docs/gelistirme_plani.md`.
> `CLAUDE.md` ve `docs/proje_raporu.md` ile birlikte okunur.
>
> **Kullanım (proje sahibi için):** Her görev için yeni bir oturum aç (`/clear`) ve şunu yaz:
> `docs/gelistirme_plani.md dosyasını oku, çalışma kurallarına uy ve sıradaki görevi yap.`
> Belirli bir görevi istiyorsan: `... ve G3 görevini yap.`

---

## Proje bağlamı

Windows'ta kullanıcının kendi bilgisayarında çalışan bir drone tasarım ve uygunluk programı. Mevcut bölümler: görev tanımı (drone türü, amaç, isteğe bağlı yarışma şartnamesi), şasi (STL/STEP/DXF'ten ağırlık hesabı), elektronik (elimdeki parçalar veya internetten öneri, uyumluluk ve uçuş hesapları) ve şartname uyum raporu. Bu plan, mevcut programın üzerine eklenecek geliştirmeleri tanımlar.

---

## Claude Code için çalışma kuralları

1. **Tek görev:** Yalnızca istenen görevi yap. Görev belirtilmemişse durum tablosundaki ilk işaretlenmemiş görevi yap. Bitince dur, sıradaki göreve kendiliğinden geçme.
2. **Önce incele:** Görevle ilgili mevcut kodu oku. Özellik kısmen varsa baştan yazma, yalnızca eksikleri tamamla. Bu plandaki sınıf adları öneridir; kodda karşılığı varsa mevcut adları kullan.
3. **Kısa plan:** Kod yazmadan önce 5–10 satırlık plan ver: eklenecek ve değişecek dosyalar, yeni sınıflar, yeni bağımlılıklar, açık sorular. Yeni bağımlılık, proje dosyası şeması değişikliği veya belirsizlik varsa onayımı bekle; yoksa devam et.
4. **Bozma:** Mevcut ekranları, yerleşimi, renkleri, animasyonları ve hesapları görev gerektirmedikçe değiştirme. Hesapları yeniden yazma; mevcut hesap sınıflarını (uçuş hesabı, uyumluluk kontrolü, ağırlık hesabı) yeniden kullan.
5. **Kod kuralları:** `CLAUDE.md` geçerlidir: OOP ve modüler yapı, Türkçe isimler (Türkçe karakter içermeyen), Türkçe docstring ve yorumlar, tür ipuçları, ayarlanabilir sabitler dosya başında `# DEĞİŞTİRİLEBİLİR:` etiketiyle.
6. **Dürüst sonuç:** Tahmine dayalı değerler "tahmini", internetten gelen ve kullanıcının onaylamadığı değerler "doğrulanmadı", fiyatlar "kontrol edilmedi" etiketiyle gösterilir. Eksik veri uydurulmaz; boş (None) kalır.
7. **Bağımlılıklar:** Windows'ta yalnızca `pip install` ile, ek sistem kurulumu gerektirmeden kurulan kütüphaneleri seç. `requirements.txt` dosyasına ekle ve seçimini bir cümleyle gerekçelendir. Arayüz kütüphaneleri (grafik vb.) CDN'den değil yerel dosyadan yüklenir; program internetsiz açılabilmelidir.
8. **Doğrulama:** Yeni testleri yaz, tüm `pytest` takımını çalıştır, programı çalıştırıp özelliği dene. Görsel doğrulama yapamıyorsan bunu açıkça söyle ve benim elle deneyeceğim adımları yaz.
9. **Kapanış:** Bu dosyadaki durum tablosunda görevi `[x]` yap ve yanına tek satırlık not ekle. Sonra kısa bir Türkçe özet ver: ne eklendi, nasıl kullanılır, bilinen sınırlar, önerilen commit mesajı.
10. **Güvenlik:** API anahtarı hiçbir proje dosyasına, rapora, günlüğe veya dışa aktarılan dosyaya yazılmaz.

---

## Durum tablosu (önerilen sıra)

- [x] G0 – Mevcut durum envanteri — `docs/mevcut_durum.md`; tamamen var olan görev yok, 8 görev kısmen var
- [ ] G1 – Proje kaydetme, açma ve sürüm geçmişi
- [ ] G2 – Malzeme listesi (BOM) ve maliyet
- [ ] G3 – Teknik rapor üretimi
- [ ] A1 – API harcama sayacı ve aylık limit
- [ ] A2 – Hata günlüğü ve hata raporu
- [ ] G4 – Senaryo karşılaştırma
- [ ] G5 – Pil optimizasyon grafiği
- [ ] G6 – "Elimdeki drone" kolu
- [ ] G7 – Bağlantı şeması
- [ ] G8 – İtki verisi içe aktarma
- [ ] G9 – Uçuş kaydıyla kalibrasyon
- [ ] G10 – Ortam koşulları
- [ ] G11 – Mevzuat kontrolü
- [ ] A3 – Parça kataloğu paylaşma
- [ ] A4 – İngilizce arayüz
- [ ] A5 – GitHub Actions ile test ve .exe derleme
- [ ] A6 – Güncelleme kontrolü
- [ ] B1–B4 – Büyük işler (yalnızca açıkça istendiğinde, Plan modunda)

---

## G0 – Mevcut durum envanteri

**Amaç:** Hangi geliştirmelerin programda zaten var olduğunu görmek. **Kod değiştirme.**

- Projenin genel yapısını özetle: paketler, ana sınıflar, hesap sınıflarının gerçek adları, arayüz yapısı, kullanılan grafik ve 3D kütüphaneleri, proje verisinin şu an nasıl tutulduğu.
- Bu dosyadaki her görev için durum belirle: **Var / Kısmen / Yok**, kanıtıyla (dosya:satır).
- Sonucu `docs/mevcut_durum.md` dosyasına yaz.
- Tamamen var olan görevleri durum tablosunda `[x] (zaten vardı)` olarak işaretle.
- Sıralamada değişiklik önerin varsa gerekçesiyle yaz, ama tabloyu ben onaylamadan değiştirme.

---

## G1 – Proje kaydetme, açma ve sürüm geçmişi

**Amaç:** Kullanıcı tüm tasarımı tek dosyada saklayıp sonra açabilsin. Sonraki görevlerin çoğu bu yapıya dayanır.

**Yapılacaklar**
- `proje/` paketi: `DroneProjesi` (tüm proje verisi), `ProjeDeposu` (yeni, aç, kaydet, farklı kaydet), `SurumGecmisi`.
- Dosya biçimi: `.droneproj` uzantılı ZIP. İçinde `proje.json` ve `ekler/` klasörü (şasi dosyasının kopyası) bulunur, böylece proje başka bilgisayara taşınabilir.
- `proje.json` içinde `sema_surumu` alanı olsun. Eski projeleri yeni şemaya yükseltmek için bir `SemaGocu` yapısı kur.
- Kaydedilecekler: görev tanımı ve hedefler; şartname kaynağı ve onaylanmış maddeler; şasi (dosya, birim, malzeme, baskı ayarları, bilinen veya düzeltilmiş ağırlık); parçalar (katalog kimliği ve kullanıcı düzeltmeleri). Hesap sonuçları kaydedilmez, açılışta yeniden hesaplanır.
- Arayüz: Yeni, Aç, Kaydet, Farklı kaydet, son açılan projeler listesi, kaydedilmemiş değişiklik uyarısı, otomatik kayıt (varsayılan 5 dakika, DEĞİŞTİRİLEBİLİR).
- Sürüm geçmişi: her elle kayıtta anlık görüntü alınır; kullanıcı listeden önceki sürüme dönebilir. Saklanan sürüm sayısı sınırlıdır (DEĞİŞTİRİLEBİLİR).

**Kabul ölçütleri**
- Kaydet → programı kapat → aç: ekrandaki tüm değerler ve sonuçlar aynıdır (gidiş-dönüş testi).
- Bozuk veya yabancı dosyada program çökmez, Türkçe hata verir.
- Orijinal şasi dosyası silinse bile proje ZIP içindeki kopyadan açılır.
- Proje dosyasında API anahtarı bulunmaz (testle kontrol edilir).

---

## G2 – Malzeme listesi (BOM) ve maliyet

**Amaç:** Tasarımın parça, ağırlık ve maliyet dökümünü çıkarmak.

**Yapılacaklar**
- `MalzemeListesi` ve `MalzemeSatiri` sınıfları; liste projeden üretilir.
- Sütunlar: tür, ad, model, adet, birim ağırlık (g), toplam ağırlık (g), birim fiyat, para birimi, kaynak bağlantısı, durum (elimde / alınacak), doğrulandı, fiyat tarihi.
- Şasi de bir satır olarak yer alır (malzeme, ağırlık; fiyatı kullanıcı girer).
- Toplamlar: toplam ağırlık, toplam maliyet, yalnızca alınacak parçaların maliyeti, bütçeyle fark.
- Farklı para birimleri birbirine karıştırılmaz, her biri ayrı toplanır. Kullanıcı kur girerse TL karşılığı "kullanıcı kuru ile" etiketiyle gösterilir. Program kendisi kur çekmez.
- Ekran: adet, fiyat ve durumun düzenlenebildiği tablo.
- Dışa aktarma: `.xlsx` ve `.csv`. CSV, Excel'de Türkçe karakterlerin doğru görünmesi için UTF-8 BOM ile yazılır.

**Kabul ölçütleri**
- Örnek projede toplamlar elle hesaplanan değerlerle aynıdır.
- Adet değişince toplam ağırlık ve uçuş hesapları güncellenir.
- `.xlsx` dosyası Excel'de açılır, Türkçe karakterler doğrudur.

---

## G3 – Teknik rapor üretimi

**Amaç:** Tasarım verilerinden yarışma raporlarına temel olacak Word ve PDF rapor üretmek.

**Yapılacaklar**
- `rapor/` paketi: `RaporOlusturucu` ve biçime göre `WordYazici`, `PdfYazici`.
- Word için python-docx; PDF için Windows'ta ek sistem kurulumu gerektirmeyen bir kütüphane (ör. reportlab). Word'den PDF'e dönüşüm için Office veya LibreOffice'e bağımlı olma.
- Bölümler (kullanıcı seçip çıkarabilir): kapak (proje ve takım adı, isteğe bağlı logo, tarih); özet; görev tanımı ve hedefler; şasi (malzeme, ölçüler, ağırlık, 3D önizlemeden alınan görüntü); malzeme listesi (G2); performans hesapları ve varsayımları; şartname uyum tablosu (madde no, şart, tasarım değeri, durum); uyarılar ve riskler; kaynaklar.
- "tahmini", "doğrulanmadı" ve "kontrol edilmedi" etiketleri raporda korunur ve dipnotla açıklanır.
- **Yarışma şablonu seçeneği:** Şartnamede rapor bölüm başlıkları tanımlıysa, model bu başlıkları çıkarır, kullanıcı onaylar ve rapor iskeleti bu sıraya göre kurulur. Programın verisiyle doldurulamayan bölümler "Bu bölüm takım tarafından doldurulacak" yer tutucusuyla kalır. Model yalnızca başlıkları çıkarır, rapor metni uydurmaz.
- PDF'te Türkçe karakterler için yazı tipi gömülür.

**Kabul ölçütleri**
- Örnek projeden iki biçimde rapor üretilir ve açılır.
- Rapordaki sayılar ekrandakilerle birebir aynıdır (testle).
- Türkçe karakter testi geçer.

---

## A1 – API harcama sayacı ve aylık limit

**Amaç:** Model kullanım maliyetini görmek ve sınırlamak.

**Yapılacaklar**
- Her model isteğinde API yanıtındaki kullanım bilgisi kaydedilir: tarih, özellik (parça araştırma, öneri, şartname), token sayıları, tahmini maliyet.
- Fiyatlar koda gömülmez; ayar dosyasında tutulur ve kullanıcı günceller (DEĞİŞTİRİLEBİLİR). Başlangıç değerlerini güncel resmi fiyatlandırma sayfasından al ve kaynak bağlantısını ayar dosyasına yaz. Web araması gibi ayrı ücretlendirilen araçlar ayrı sayılır.
- Ayarlar: aylık limit. Limitin %80'inde uyarı verilir; limit aşılırsa istek gönderilmeden önce kullanıcı onayı istenir.
- Ekran: bu ayın harcaması ve özelliklere göre dağılımı.

**Kabul ölçütleri**
- Sahte yanıtlarla sayaç doğru toplar.
- Limit aşımında onaysız istek gönderilmez (testle).

---

## A2 – Hata günlüğü ve hata raporu

**Yapılacaklar**
- Python `logging` ile `kayitlar/` klasöründe boyut sınırlı, dönen günlük dosyası (sınır DEĞİŞTİRİLEBİLİR). `.exe` olarak çalışırken de yazılabilir bir konum kullanılır.
- Yakalanmamış hatalar günlüğe yazılır; kullanıcıya sade, Türkçe bir mesaj gösterilir.
- "Hata raporu oluştur" butonu: son günlükler, program sürümü ve işletim sistemi bilgisi bir ZIP dosyasına konur. API anahtarı ve kullanıcı adını içeren dosya yolları maskelenir.

**Kabul ölçütleri**
- Bilinçli oluşturulan bir hatada program çökmez, günlükte iz kalır.
- Hata raporu ZIP'inde API anahtarı bulunmaz (testle).

---

## G4 – Senaryo karşılaştırma

**Amaç:** Farklı parça seçimlerini yan yana karşılaştırmak.

**Yapılacaklar**
- Projede birden fazla senaryo olabilir: "Ana tasarım" kopyalanır, kullanıcı parçaları değiştirir. Bu, G1 proje yapısına eklenir; şema sürümünü artır ve göç adımını yaz.
- 2–3 senaryo yan yana gösterilir: toplam ağırlık, itki/ağırlık oranı, askıda kalma gazı, tahmini uçuş süresi, toplam akım, maliyet, uyum sonuçları, şartname durumu.
- Her satırda en iyi değer vurgulanır ve farklar (+/−) gösterilir. Tahmini değerler işaretlenir.
- Bir senaryo "ana tasarım yap" ile ana tasarıma dönüştürülebilir.
- Hesaplar için mevcut hesap sınıfları kullanılır.

**Kabul ölçütleri**
- İki senaryoda yalnızca pil farklıyken yalnızca pile bağlı değerler değişir (testle).
- Senaryolar kaydedilip yeniden açılır.

---

## G5 – Pil optimizasyon grafiği

**Amaç:** Uçuş süresinin en yüksek olduğu pil kapasitesini göstermek.

**Yapılacaklar**
- Seçili hücre sayısı (S) için kapasite aralığı taranır (aralık ve adım DEĞİŞTİRİLEBİLİR). Her noktada pil ağırlığı bir enerji yoğunluğu varsayımıyla tahmin edilir, uçuş süresi mevcut hesap sınıfıyla hesaplanır.
- Grafik: x ekseni kapasite (mAh), y ekseni uçuş süresi (dk). En yüksek nokta işaretlenir. İtki/ağırlık oranının alt eşiğin altına düştüğü bölge taralı gösterilir. Katalogdaki gerçek piller ayrı noktalarla işaretlenir.
- Enerji yoğunluğu ve eşikler DEĞİŞTİRİLEBİLİR sabitlerdir; eğri "tahmini" etiketlidir.
- Grafik kütüphanesi: arayüzde zaten varsa onu kullan, yoksa hafif bir kütüphaneyi yerel dosya olarak ekle.
- Pervane ve KV taraması bu görevin kapsamı dışında, ama yapıyı genişletilebilir kur.

**Kabul ölçütleri**
- Bilinen girdilerle beklenen en iyi nokta bulunur (testle).
- Grafikteki en yüksek nokta, aynı kapasiteyle doğrudan yapılan hesapla aynıdır.

---

## G6 – "Elimdeki drone" kolu

**Amaç:** Var olan bir drone için hedefe göre yükseltme önerileri vermek.

**Yapılacaklar**
- Ana menüde iki kol: "Sıfırdan drone" ve "Elimdeki drone".
- Girdiler: mevcut parçalar (elektronik ekranındaki formlar yeniden kullanılır), şasi ağırlığı veya ölçülmüş toplam ağırlık, isteğe bağlı gözlemler (ör. ölçülmüş uçuş süresi).
- Hedefler (birden fazlası, öncelik sırasıyla seçilebilir): daha uzun uçuş, daha fazla yük (gram), daha hafif, daha düşük maliyet, şartnameye uyum.
- `DurumAnalizcisi`: mevcut uyum sonuçlarından zayıf noktaları bulur (ör. ESC akım payı düşük, itki/ağırlık düşük, pil C değeri yetersiz).
- `YukseltmeOnericisi`: her hedef için en az değişiklikli öneriler üretir; tek parça değişimine öncelik verir. Adaylar önce katalogdan, yoksa mevcut öneri servisinden gelir. Her öneride değişen parça, gerekçe, önce/sonra karşılaştırması (G4 bileşeni), ek maliyet ve uyum sonucu bulunur.
- Ölçülmüş uçuş süresi girildiyse hesaplar buna göre düzeltilir ve bu açıkça belirtilir.

**Kabul ölçütleri**
- ESC'si zayıf örnek bir drone'da ESC değişimi önerilir (testle).
- "Daha hafif" hedefinde tüm öneriler toplam ağırlığı azaltır (testle).

---

## G7 – Bağlantı şeması

**Amaç:** Seçilen parçalara göre kablo bağlantılarının mantıksal şemasını çizmek.

**Yapılacaklar**
- Şema içeriği: pil → güç dağıtımı veya ESC → motorlar; uçuş kartı ile ESC arası sinyal (protokol); alıcı, VTX, GPS ve telemetrinin uçuş kartındaki UART'lara bağlantısı; kamera → VTX veya uçuş kartı; BEC ve gerilim hatları (5 V, 9 V, pil gerilimi).
- UART atama önerisi uçuş kartının port sayısına göre yapılır; port yetmezse uyarı verilir.
- Gerilim uyumsuzlukları kırmızıyla işaretlenir ve açıklanır.
- Çıktı SVG'dir: ekranda gösterilir, PNG veya SVG olarak kaydedilir, teknik rapora (G3) eklenebilir.
- Pin düzeyinde kesin eşleme yapılmaz. Uçuş kartının pin bilgisi katalogda yoksa şema mantıksal kalır ve "Pinleri uçuş kartı üreticisinin şemasından doğrulayın" notu eklenir.

**Kabul ölçütleri**
- 4 motorlu örnek konfigürasyonda tüm parçalar şemada yer alır.
- UART sayısı aşıldığında uyarı verilir (testle).

---

## G8 – İtki verisi içe aktarma

**Amaç:** Gerçek test verisiyle "tahmini" hesapları azaltmak.

**Yapılacaklar**
- CSV şablonu: gaz (%), itki (g), akım (A), gerilim (V); isteğe bağlı güç (W) ve RPM. Dosya başında motor, pervane ve pil S bilgisi. Örnek dosya: `veri/sablonlar/itki_tablosu_sablonu.csv`.
- İçe aktarmada doğrulama: eksik sütun, birim, sırasız gaz değerleri. Hatalar satır numarasıyla Türkçe gösterilir.
- Tablo kataloğa motor + pervane + gerilim kombinasyonuna bağlı olarak kaydedilir.
- Hesap motoru kombinasyon için tablo varsa onu kullanır ve ara değerleri doğrusal interpolasyonla bulur; sonuç "ölçülmüş veriye dayalı" etiketlenir. Tablo yoksa mevcut tahmin yöntemi sürer.
- Tablonun gerilimi kullanımla uyuşmuyorsa (ör. tablo 4S, kullanım 6S) tablo kullanılmaz ve uyarı verilir.

**Kabul ölçütleri**
- Bilinen bir tabloyla askıda kalma gazı elle hesaplanan değerle aynıdır.
- Hatalı CSV'de satır numaralı Türkçe hata verilir (testle).

---

## G9 – Uçuş kaydıyla kalibrasyon

**Amaç:** Gerçek uçuş verisiyle tahminleri karşılaştırıp düzeltmek.

**Yapılacaklar**
- Desteklenen kayıtlar: ArduPilot `.bin` (ör. pymavlink ile) ve Betaflight Blackbox Explorer'dan dışa aktarılan CSV. Betaflight `.bbl` dosyasını doğrudan okuyan güvenilir bir Python kütüphanesi bulursan öner, onaysız ekleme.
- Çıkarılacak değerler: uçuş süresi, harcanan mAh, ortalama ve en yüksek akım, gerilim eğrisi, askıda kalma bölümlerindeki ortalama gaz ve akım.
- Askıda kalma bölümleri basit eşiklerle (dikey hız, irtifa değişimi) bulunur; eşikler DEĞİŞTİRİLEBİLİR.
- Tahmini ve ölçülmüş değerler yan yana, fark yüzdesiyle gösterilir.
- Program bir düzeltme katsayısı önerir. Kullanıcı onaylarsa katsayı projeye kaydedilir ve sonraki hesaplarda "kalibre edilmiş" etiketiyle uygulanır; kullanıcı istediğinde kaldırabilir.
- Büyük kayıt dosyaları akış halinde okunur ve ilerleme gösterilir.
- Testler için küçük sentetik CSV dosyaları üret. Gerçek bir `.bin` örneği gerekirse benden iste.

**Kabul ölçütleri**
- Sentetik kayıttan çıkarılan değerler beklenen değerlerle aynıdır.
- Katsayı uygulanınca tahmini uçuş süresi ölçülen değere yaklaşır (testle).

---

## G10 – Ortam koşulları

**Amaç:** Yarışma alanının irtifa, sıcaklık ve rüzgâr koşullarını hesaba katmak.

**Yapılacaklar**
- Girdiler: alan irtifası (m), sıcaklık (°C), ortalama rüzgâr (m/s). Şartnamede alan bilgisi varsa öneri olarak doldurulur.
- Hava yoğunluğu standart atmosfer modeliyle irtifa ve sıcaklıktan hesaplanır.
- İtki ve güç, deniz seviyesi standart yoğunluğuna göre yoğunluk oranıyla ölçeklenir. Varsayım kod içinde yorumla açıklanır.
- Rüzgâr için basit bir ek güç payı uygulanır (DEĞİŞTİRİLEBİLİR, "tahmini").
- Sonuç ekranında "standart koşullar" ve "alan koşulları" iki ayrı sütundur.

**Kabul ölçütleri**
- Deniz seviyesinde ve 15 °C'de sonuçlar mevcut hesapla birebir aynıdır (geri uyumluluk testi).
- İrtifa arttıkça itki/ağırlık oranı düşer.

---

## G11 – Mevzuat kontrolü

**Amaç:** Toplam kalkış ağırlığına göre kayıt ve pilot belgesi gerekliliklerini göstermek.

**Yapılacaklar**
- `veri/mevzuat.json`: ülke, kurum, sınıf adı, kalkış ağırlığı aralığı, gereklilikler (kayıt, pilot belgesi vb.), kaynak bağlantısı, son kontrol tarihi.
- Türkiye için sınıfları Sivil Havacılık Genel Müdürlüğü'nün (SHGM, Türkiye'nin sivil havacılık otoritesi) güncel İHA düzenlemesinden araştırıp doldur. Her değere kaynak bağlantısı ekle. Emin olamadığın değeri boş bırak ve bana listele. Ezbere değer yazma.
- Program toplam kalkış ağırlığına göre sınıfı ve gereklilikleri gösterir; yanında "Bilgilendirme amaçlıdır, resmi kaynağı kontrol edin" notu ve kaynak bağlantısı bulunur.
- Son kontrol tarihi 6 aydan eskiyse (DEĞİŞTİRİLEBİLİR) "Mevzuat verisi eski olabilir" uyarısı verilir.
- Kurallar kodda değil veri dosyasındadır; kullanıcı dosyayı güncelleyebilir.

**Kabul ölçütleri**
- Veri dosyasındaki sınır değerlerin hemen altı ve hemen üstü için doğru sınıf bulunur (testle).

---

## A3 – Parça kataloğu paylaşma

- Doğrulanmış parçalar seçilerek JSON olarak dışa aktarılır.
- İçe aktarmada çakışma ekranı: aynı model varsa "mevcudu koru / yenisiyle değiştir / ikisini tut".
- İçe aktarılan parçalarda kaynağı belirtilir; kullanıcı isterse doğrulanmış olarak kabul eder.
- **Kabul:** Dışa aktar → boş kataloğa içe aktar: veriler aynıdır (testle).

---

## A4 – İngilizce arayüz

- Arayüz metinleri dil dosyalarına taşınır: `veri/diller/tr.json`, `veri/diller/en.json`. Kod içi isimler Türkçe kalır.
- Dil ayarlardan seçilir; eksik çeviride Türkçe gösterilir.
- Teknik raporun (G3) dili de seçilebilir.
- **Kabul:** HTML ve JavaScript'te dil anahtarı dışında sabit arayüz metni kalmaz (tarama testi).

---

## A5 – GitHub Actions ile test ve .exe derleme

- Her push'ta Windows ortamında `pytest` çalışır.
- Sürüm etiketi atıldığında PyInstaller ile `.exe` derlenir ve sürüm sayfasına eklenir.
- Proje GitHub'da değilse yalnızca iş akışı dosyasını hazırla ve nasıl kullanılacağını anlat.

---

## A6 – Güncelleme kontrolü

- Program sürümü tek bir yerde tanımlanır (ör. `cekirdek/surum.py`).
- Açılışta (ayardan kapatılabilir) GitHub Releases'ta daha yeni sürüm olup olmadığına bakılır. Varsa yalnızca bildirilir ve indirme bağlantısı gösterilir. Otomatik indirme veya kurulum yapılmaz.
- İnternet yoksa kontrol sessizce atlanır.

---

## Büyük işler (B1–B4)

Bunlara yalnızca açıkça istediğimde başla. Başlarken Plan modunda ayrıntılı plan yaz ve onayımı bekle.

- **B1 – 3D yerleşim ve ağırlık dengesi:** `docs/proje_raporu.md` içindeki kapsam: parçalar kutu modeller olarak, birleşik ağırlık merkezi (x, y, z), pil konumu önerisi, çakışma kontrolü. Önerilen yerleşim bir başlangıç taslağıdır; titreşim, ısınma ve anten girişimi modellenmez.
- **B2 – Sabit kanat ve VTOL desteği:** kanat alanı, kanat yükü, stall hızı, ağırlık merkezinin aerodinamik merkeze göre konumu, servo parçaları.
- **B3 – Onshape bağlantısı:** Onshape API ile belgeleri listeleme ve parçayı STEP veya STL olarak çekme. API anahtarları yalnızca yerel ayarlarda tutulur.
- **B4 – Uçuş kontrolcü başlangıç ayarları:** Betaflight CLI komutları veya ArduPilot `.param` dosyası taslağı (pil gerilim eşikleri, motor protokolü, failsafe). Program ayarları karta asla otomatik yüklemez. Çıktının başında "Uçuştan önce tüm değerleri elle doğrulayın" uyarısı bulunur.
