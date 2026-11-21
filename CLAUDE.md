# Drone Tasarım Programı

## Proje
Windows'ta kullanıcının kendi bilgisayarında çalışan bir drone tasarım ve uygunluk programı. Ayrıntılar docs/proje_raporu.pdf dosyasındadır. İşe başlamadan önce o dosyayı oku.

## Kodlama kuralları
- Python 3.11, nesne yönelimli (OOP) ve modüler yapı. Her sınıf tek bir işi yapar.
- Tüm isimler (dosya, klasör, sınıf, fonksiyon, değişken) Türkçe olur ve Türkçe karakter içermez. Sınıflar PascalCase, fonksiyon ve değişkenler snake_case, sabitler BUYUK_HARF.
- Her modülün başında modül açıklaması, her sınıf ve fonksiyonda Türkçe docstring bulunur (ne yapar, parametreler, dönüş değeri, birim).
- Kod içi yorumlar Türkçe ve sade olur, "ne"yi değil "neden"i açıklar. Proje sahibi kodu sonradan kendisi değiştirecek; müdahale edebileceği yerleri "# DEĞİŞTİRİLEBİLİR:" etiketiyle işaretle.
- Tür ipuçları (type hints) kullan.
- Sihirli sayı yazma; sabitleri dosya başında ya da ayar dosyasında tanımla.
- Hata mesajları Türkçe ve kullanıcının anlayacağı dilde olur. Özel hata sınıfları cekirdek/hatalar.py içinde durur.
- Birimler: uzunluk mm, kütle gram, yoğunluk g/cm3. Dönüşümler cekirdek/birimler.py içinde yapılır.
- API anahtarı kodun içine yazılmaz; ortam değişkeninden veya yerel ayar dosyasından okunur.
- Tahmine dayalı sonuçlar "tahmini" etiketiyle döndürülür ve ekranda öyle gösterilir.
- Dosya yolları için pathlib kullan, Windows uyumlu yaz.

## Çalışma kuralları
- Yalnızca istenen aşamayı yap. Raporda "sonraya bırakılan" bölümleri (3D yerleşim ve denge, sabit kanat, Onshape API) yazma.
- Belirsizlik veya önemli bir karar varsa kod yazmadan önce sor.
- Her aşama sonunda kodu çalıştır, pytest ile testleri koş ve Türkçe kısa özet ver: ne yapıldı, nasıl çalıştırılır, nelere dikkat edilmeli.
- Yeni bağımlılık eklersen requirements.txt dosyasına yaz ve bana söyle.
- Var olan dosyaları gereksiz yere bastan yazma, küçük ve odaklı değişiklik yap.

## Çalıştırma
- Program: python uygulama.py
- Testler: pytest
- Ortam notu: PATH'teki `python` MSYS2 Python'udur ve paket kuramaz. Sanal ortam `.venv` standart Windows Python 3.13 ile kuruldu (`py -3.13 -m venv .venv`). Komutları `.\.venv\Scripts\python.exe` ile çalıştır.
