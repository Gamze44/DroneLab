// Ayarlar sayfası: Gemini anahtarı (yalnızca var/yok gösterilir), model ve günlük sınır.
"use strict";

const ANAHTAR_KAYNAK_ADLARI = { ortam_degiskeni: "ortam değişkeninden (GEMINI_API_KEY)", dosya: "veri/gemini_anahtari.txt dosyasından" };
// Model listesindeki özel değerlerin ekranda görünen adı (diğerleri model adıyla görünür).
const MODEL_ADLARI = { otomatik: "Otomatik (önerilen)" };

function ayarlariCiz(a) {
  tabloDoldur("ayar-durumu", [
    ["API anahtarı", a.anahtar_var ? `var – ${ANAHTAR_KAYNAK_ADLARI[a.anahtar_kaynagi] || ""}` : "yok (öneri kapalı, elle giriş açık)"],
    ["Bugünkü yapay zeka isteği", `${a.bugun_kullanilan} / ${a.gunluk_sinir}`],
  ]);
  const secici = $("ay-model");
  secici.replaceChildren(...a.modeller.map((m) => new Option(MODEL_ADLARI[m] || m, m)));
  secici.value = a.model;
  $("ay-sinir").max = a.en_buyuk_gunluk_sinir;
  $("ay-sinir").value = a.gunluk_sinir;
  $("ay-anahtar").value = "";
  // Ortam değişkenindeki anahtar buradan silinemez; düğme yalnızca dosya varken anlamlı.
  $("ay-anahtar-sil").disabled = a.anahtar_kaynagi !== "dosya";
}

async function ayarlariYukle() {
  try {
    ayarlariCiz(await istekGonder("/api/ayarlar/yapay-zeka"));
  } catch (veri) {
    hataGoster("ayar-hatasi", veri);
  }
}

$("ayar-formu").addEventListener("submit", async (olay) => {
  olay.preventDefault();
  goster("ayar-hatasi", false);
  const govde = { model: $("ay-model").value, gunluk_sinir: Number($("ay-sinir").value) };
  const anahtar = $("ay-anahtar").value.trim();
  if (anahtar) govde.anahtar = anahtar;
  try {
    ayarlariCiz(await istekGonder("/api/ayarlar/yapay-zeka", jsonIstegi("PUT", govde)));
    $("ay-durum").textContent = "Kaydedildi.";
  } catch (veri) {
    hataGoster("ayar-hatasi", veri);
  }
});

$("ay-anahtar-sil").addEventListener("click", async () => {
  if (!confirm("Anahtar dosyası silinsin mi? Öneri özelliği yeni anahtar girilene kadar kapanır.")) return;
  goster("ayar-hatasi", false);
  try {
    ayarlariCiz(await istekGonder("/api/ayarlar/yapay-zeka/anahtar", { method: "DELETE" }));
    $("ay-durum").textContent = "Anahtar dosyası silindi.";
  } catch (veri) {
    hataGoster("ayar-hatasi", veri);
  }
});

// ---------- Şartname kütüphanesi ----------

async function kutuphaneyiYukle() {
  goster("sartname-kutuphane-hatasi", false);
  try {
    const liste = await istekGonder("/api/sartnameler");
    $("sartname-listesi").replaceChildren(...liste.map(sartnameSatiri));
    goster("sartname-listesi-bos", liste.length === 0);
  } catch (veri) {
    hataGoster("sartname-kutuphane-hatasi", veri);
  }
}

function sartnameSatiri(s) {
  const satir = document.createElement("div");
  satir.className = "liste-satiri";
  const bilgi = document.createElement("div");
  const ad = document.createElement("div");
  ad.className = "liste-baslik";
  ad.textContent = s.ad;
  const ozet = document.createElement("div");
  ozet.className = "soluk";
  ozet.textContent = `${s.dosya_adi} · ${s.onayli_madde_sayisi}/${s.madde_sayisi} madde onaylı · ` +
    `${s.kullanan_drone_sayisi} drone kullanıyor · ${zamanBicimle(s.yuklenme_zamani)}`;
  bilgi.append(ad, ozet);
  const sil = document.createElement("button");
  sil.type = "button";
  sil.className = "tehlike";
  sil.textContent = "Sil";
  sil.disabled = s.kullanan_drone_sayisi > 0;
  sil.title = sil.disabled ? "Bir drone kullanıyor; önce drone'dan kaldırın." : "";
  sil.addEventListener("click", async () => {
    if (!confirm(`"${s.ad}" şartnamesi ve maddeleri kalıcı olarak silinsin mi?`)) return;
    try {
      await istekGonder(`/api/sartnameler/${s.kimlik}`, { method: "DELETE" });
      await kutuphaneyiYukle();
    } catch (veri) {
      hataGoster("sartname-kutuphane-hatasi", veri);
    }
  });
  satir.append(bilgi, sil);
  return satir;
}

ayarlariYukle();
kutuphaneyiYukle();
