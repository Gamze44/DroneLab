"""
Yapay zeka ile parça önerisi.

Akış: istem oluştur → Gemini'den şemalı JSON al → her adayı programın kendi
doğrulayıcısından geçir (geçersiz değerler silinir) → uyum kontrolleri ve uçuş
hesabıyla değerlendir → uyumsuzlar sona gelecek şekilde sırala.
Öneriler internette aranmadan modelin bilgisinden gelir; "doğrulanmadı" sayılır.
"""
