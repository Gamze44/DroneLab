// Drone sayfasındaki şasi bölümü.
// Akış: dosya yükle -> ham ölçüler ve birim önerisi -> birim onayı -> mm sonuçları.
// Ağırlık elle girilir. Her adım sunucuda otomatik kaydedilir.
// Bu dosya drone.js'ten önce yüklenir; droneKimligi ve droneGuncellendi drone.js'te tanımlıdır.
"use strict";

// DEĞİŞTİRİLEBİLİR: Ekranda gösterilen ondalık basamak sayıları.
const OLCU_BASAMAK = 1;
const HACIM_BASAMAK = 1;
const MM3_BIR_CM3 = 1000;
const MM2_BIR_CM2 = 100;

const BIRIM_ADLARI = { mm: "milimetre (mm)", cm: "santimetre (cm)", m: "metre (m)", inch: "inç (inch)" };
const TUR_ADLARI = { kati: "3B katı model", levha: "2B levha çizimi" };

let sonYukleme = null; // Sunucudan gelen son şasi okuma bilgisi

function olculeriYaz(olculer, birim, levhaMi) {
  // Levhada kalınlık (z) çizimde yok; "× 0" yazmak yanıltıcı olur.
  const gosterilen = levhaMi ? olculer.slice(0, 2) : olculer;
  return gosterilen.map((d) => sayiBicimle(d, OLCU_BASAMAK)).join(" × ") + (birim ? " " + birim : "");
}

// drone.js sayfa açılırken çağırır; kayıtlı şasi varsa ekrana getirir.
function sasiBolumunuBaslat(sasi) {
  if (!sasi) return;
  birimKartiniDoldur(sasi.yukleme);
  if (sasi.olculer) {
    $("birim-secici").value = sasi.olculer.birim;
    onizlemeyiGuncelle();
    sonucuGoster(sasi.olculer);
  }
}

// ---------- Yükleme ----------

$("yukleme-formu").addEventListener("submit", async (olay) => {
  olay.preventDefault();
  const dosya = $("dosya-secici").files[0];
  if (!dosya) return;

  if (sonYukleme && !confirm("Bu drone'un mevcut şasisi yeni dosyayla değiştirilecek ve kayıtlı şasi ağırlığı silinecek. Devam edilsin mi?")) {
    return;
  }

  goster("sasi-hatasi", false);
  $("yukle-dugmesi").disabled = true;
  $("yukleme-durumu").textContent = "Dosya okunuyor...";

  const form = new FormData();
  form.append("dosya", dosya);
  try {
    const yanit = await istekGonder(`/api/dronelar/${droneKimligi}/sasi`, { method: "POST", body: form });
    goster("sonuc-karti", false);
    birimKartiniDoldur(yanit.yukleme);
    droneGuncellendi(yanit.drone);
    $("dosya-secici").value = "";
  } catch (veri) {
    hataGoster("sasi-hatasi", veri);
  } finally {
    $("yukle-dugmesi").disabled = false;
    $("yukleme-durumu").textContent = "";
  }
});

// ---------- Birim onayı ----------

function birimKartiniDoldur(y) {
  sonYukleme = y;
  const levhaMi = y.tur === "levha";

  $("mevcut-sasi").textContent = `Kayıtlı şasi: ${y.dosya_adi}. Yeni dosya yüklersen bunun yerine geçer.`;
  goster("mevcut-sasi", true);

  const satirlar = [
    ["Dosya", y.dosya_adi],
    ["Tür", TUR_ADLARI[y.tur] || y.tur],
    ["Dosyadaki birim", y.dosya_birimi || "belirtilmemiş"],
  ];
  if (levhaMi) {
    satirlar.push(["Dış parça sayısı", String(y.dis_kontur_sayisi)]);
    satirlar.push(["Delik sayısı", String(y.delik_sayisi)]);
  } else {
    satirlar.push(["Üçgen sayısı", y.ucgen_sayisi.toLocaleString("tr-TR")]);
    satirlar.push(["Ayrı parça sayısı", String(y.govde_sayisi)]);
    satirlar.push(["Kapalı model", y.kapali_mi ? "Evet" : "Hayır (hacim hatalı olabilir)"]);
  }
  tabloDoldur("dosya-bilgileri", satirlar);

  $("ham-olculer").textContent = olculeriYaz(y.olculer_ham, "", levhaMi);

  const secici = $("birim-secici");
  secici.replaceChildren();
  for (const birim of Object.keys(y.birim_carpanlari_mm)) {
    const secenek = document.createElement("option");
    secenek.value = birim;
    secenek.textContent = BIRIM_ADLARI[birim] || birim;
    secici.append(secenek);
  }
  secici.value = y.oneri.birim;

  const etiket = $("oneri-etiketi");
  etiket.textContent = y.oneri.kaynak === "dosya" ? "dosyadan okundu" : "öneri (tahmini)";
  etiket.classList.toggle("dosya", y.oneri.kaynak === "dosya");
  $("oneri-aciklamasi").textContent = y.oneri.aciklama;

  onizlemeyiGuncelle();
  listeKutusu("okuma-uyarilari", "Dosya okunurken dikkat çeken noktalar:", y.uyarilar);
  goster("birim-karti", true);
}

function onizlemeyiGuncelle() {
  if (!sonYukleme) return;
  const carpan = sonYukleme.birim_carpanlari_mm[$("birim-secici").value];
  const mm = sonYukleme.olculer_ham.map((d) => d * carpan);
  $("onizleme-olculer").textContent = olculeriYaz(mm, "mm", sonYukleme.tur === "levha");
}

$("birim-secici").addEventListener("change", () => {
  onizlemeyiGuncelle();
  goster("sonuc-karti", false);
});

$("birim-onay-dugmesi").addEventListener("click", async () => {
  if (!sonYukleme) return;
  $("birim-onay-dugmesi").disabled = true;
  goster("sasi-hatasi", false);
  try {
    const yanit = await istekGonder(
      `/api/dronelar/${droneKimligi}/sasi/birim`,
      jsonIstegi("POST", { birim: $("birim-secici").value })
    );
    sonucuGoster(yanit.olculer);
    // Şasi ölçüleri değişti: üstten görünüş, K5 ve özet yeniden hesaplanır.
    elektronikOzetiniYenile();
  } catch (veri) {
    hataGoster("sasi-hatasi", veri);
  } finally {
    $("birim-onay-dugmesi").disabled = false;
  }
});

// Onaydan sonra birim kartı kapanır; kullanıcı isterse bu düğmeyle yeniden açar.
$("birim-degistir").addEventListener("click", () => {
  goster("birim-karti", true);
  $("birim-karti").scrollIntoView({ behavior: "smooth", block: "start" });
});

// ---------- Sonuç ----------

function sonucuGoster(s) {
  const levhaMi = sonYukleme && sonYukleme.tur === "levha";
  const satirlar = [
    ["Onaylanan birim", BIRIM_ADLARI[s.birim] || s.birim],
    ["En (x)", sayiBicimle(s.en_mm, OLCU_BASAMAK) + " mm"],
    ["Boy (y)", sayiBicimle(s.boy_mm, OLCU_BASAMAK) + " mm"],
  ];
  if (levhaMi) {
    satirlar.push(["Kalınlık", "ağırlık hesabı aşamasında girilecek"]);
    satirlar.push(["Net alan (delikler çıkarılmış)", sayiBicimle(s.alan_mm2 / MM2_BIR_CM2, HACIM_BASAMAK) + " cm²"]);
  } else {
    satirlar.push(["Yükseklik (z)", sayiBicimle(s.yukseklik_mm, OLCU_BASAMAK) + " mm"]);
    satirlar.push(["Hacim", sayiBicimle(s.hacim_mm3 / MM3_BIR_CM3, HACIM_BASAMAK) + " cm³"]);
  }
  tabloDoldur("sonuc-bilgileri", satirlar);
  listeKutusu("sonuc-uyarilari", "Uyarılar:", s.uyarilar);
  goster("sonuc-karti", true);
  // Birim onaylandı; doğrulama kartı artık gerekmez (yeni dosya yüklenince yeniden açılır).
  goster("birim-karti", false);
}

// ---------- Elle ağırlık ----------

async function agirligiGonder(agirlik) {
  goster("agirlik-hatasi", false);
  try {
    const yanit = await istekGonder(
      `/api/dronelar/${droneKimligi}/sasi/agirlik`,
      jsonIstegi("PUT", { agirlik_g: agirlik })
    );
    droneGuncellendi(yanit.drone);
    $("agirlik-girdisi").value = "";
  } catch (veri) {
    hataGoster("agirlik-hatasi", veri);
  }
}

$("agirlik-formu").addEventListener("submit", (olay) => {
  olay.preventDefault();
  agirligiGonder(Number($("agirlik-girdisi").value));
});

$("agirlik-temizle").addEventListener("click", () => agirligiGonder(null));
