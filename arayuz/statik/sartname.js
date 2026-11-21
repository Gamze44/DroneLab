// "Şartname" sekmesi: drone'a şartname ekleme (kütüphaneden ya da yeni belge),
// madde tablosu (Gemini ile çıkarım, elle düzeltme, onay) ve madde bazlı uyum raporu.
// drone.js'ten önce yüklenir; droneKimligi drone.js'te tanımlıdır.
"use strict";

const MADDE_ISARETLERI = { uygun: "✓", uygunsuz: "✗", bilinmiyor: "?", bilgi: "ℹ", onay_bekliyor: "⏳" };
const MADDE_DURUM_SIRASI = ["uygunsuz", "bilinmiyor", "onay_bekliyor", "bilgi", "uygun"];

let sartnameSecenekleri = null; // /api/sartname-secenekleri
let droneSartnamesi = null;     // /api/dronelar/{k}/sartname yanıtındaki şartname

// Sayfa açılınca sekme başlığındaki özet için ve sekme her açıldığında çağrılır.
async function sartnameSekmesiniAc() {
  goster("sartname-hatasi", false);
  try {
    sartnameSecenekleri ||= await istekGonder("/api/sartname-secenekleri");
    await kutuphaneyiYukle();
    await sartnameRaporunuYenile();
  } catch (veri) {
    hataGoster("sartname-hatasi", veri);
  }
}

async function sartnameRaporunuYenile() {
  const v = await istekGonder(`/api/dronelar/${droneKimligi}/sartname`);
  droneSartnamesi = v.sartname;
  const s = v.sartname;
  $("sartname-mevcut").textContent = s
    ? `Bu drone'un şartnamesi: ${s.ad} (${s.dosya_adi}) · ${s.onayli_madde_sayisi}/${s.madde_sayisi} madde onaylı` +
      (s.kullanan_drone_sayisi > 1 ? ` · ${s.kullanan_drone_sayisi} drone kullanıyor` : "")
    : "Bu drone'a şartname eklenmedi (isteğe bağlı).";
  goster("sartname-kaldir", !!s);
  goster("sartname-rapor-karti", !!s);
  goster("sartname-madde-karti", !!s);
  raporuCiz(v.rapor);
  if (s) await maddeleriYukle(s.kimlik);
  ustOzetiYenile();
}

// ---------- Kütüphane ve yükleme ----------

async function kutuphaneyiYukle() {
  const liste = await istekGonder("/api/sartnameler");
  const secici = $("sartname-kutuphane");
  secici.replaceChildren(...liste.map((s) => new Option(`${s.ad} – ${s.dosya_adi} (${s.madde_sayisi} madde)`, String(s.kimlik))));
  goster("sartname-kutuphane-bos", liste.length === 0);
  secici.disabled = liste.length === 0;
  $("sartname-bagla").disabled = liste.length === 0;
}

$("sartname-bagla").addEventListener("click", async () => {
  goster("sartname-hatasi", false);
  try {
    await istekGonder(`/api/dronelar/${droneKimligi}/sartname`,
      jsonIstegi("PUT", { sartname_kimlik: Number($("sartname-kutuphane").value) }));
    await sartnameSekmesiniAc();
  } catch (veri) {
    hataGoster("sartname-hatasi", veri);
  }
});

$("sartname-kaldir").addEventListener("click", async () => {
  if (!confirm("Şartname bu drone'dan kaldırılsın mı? (Şartname kütüphanede kalır.)")) return;
  try {
    await istekGonder(`/api/dronelar/${droneKimligi}/sartname`, { method: "DELETE" });
    await sartnameSekmesiniAc();
  } catch (veri) {
    hataGoster("sartname-hatasi", veri);
  }
});

$("sartname-yukleme-formu").addEventListener("submit", async (olay) => {
  olay.preventDefault();
  goster("sartname-hatasi", false);
  const form = new FormData();
  form.append("dosya", $("sartname-dosya").files[0]);
  form.append("ad", $("sartname-ad").value);
  form.append("drone_kimlik", String(droneKimligi));
  $("sartname-yukle").disabled = true;
  $("sartname-yukleme-durumu").textContent = "Belge okunuyor…";
  try {
    await istekGonder("/api/sartnameler", { method: "POST", body: form });
    $("sartname-yukleme-formu").reset();
    $("sartname-yukleme-durumu").textContent = "Yüklendi. Şimdi maddeleri çıkarın veya elle ekleyin.";
    await sartnameSekmesiniAc();
  } catch (veri) {
    $("sartname-yukleme-durumu").textContent = "";
    hataGoster("sartname-hatasi", veri);
  } finally {
    $("sartname-yukle").disabled = false;
  }
});

// ---------- Uyum raporu ----------

function raporuCiz(rapor) {
  const sayac = $("sartname-sayaci");
  sayac.replaceChildren();
  for (const durum of MADDE_DURUM_SIRASI) {
    const adet = rapor.filter((r) => r.durum === durum).length;
    if (!adet) continue;
    const cip = document.createElement("span");
    cip.className = `cip cip-uyum-${durum}`;
    cip.textContent = `${MADDE_ISARETLERI[durum]} ${adet} ${rapor.find((r) => r.durum === durum).durum_adi}`;
    sayac.append(cip);
  }

  const kap = $("sartname-raporu");
  kap.replaceChildren();
  if (rapor.length === 0) {
    bosMesaj(kap, "Henüz madde yok.");
    return;
  }
  // Şartnamedeki sırayla (madde numarası) gösterilir; rapor şartnameyle karşılaştırılarak okunur.
  for (const r of rapor) {
    const m = r.madde;
    const satir = document.createElement("div");
    satir.className = `uyum-satiri uyum-${r.durum}`;
    const isaret = document.createElement("span");
    isaret.className = "uyum-isareti";
    isaret.textContent = MADDE_ISARETLERI[r.durum];
    const metin = document.createElement("div");
    const baslik = document.createElement("div");
    baslik.className = "liste-baslik";
    const yer = [m.madde_no ? `Madde ${m.madde_no}` : "", m.sayfa ? `s. ${m.sayfa}` : ""].filter(Boolean).join(", ");
    baslik.textContent = `${yer ? yer + ": " : ""}${m.buyukluk_adi} — tasarım: ${r.tasarim}`;
    if (r.tahmini) {
      const rozet = document.createElement("span");
      rozet.className = "etiket uyari";
      rozet.textContent = "tahmini";
      baslik.append(rozet);
    }
    const aciklama = document.createElement("div");
    aciklama.className = "soluk";
    aciklama.textContent = `${r.aciklama} · "${m.aciklama}"`;
    metin.append(baslik, aciklama);
    satir.append(isaret, metin);
    kap.append(satir);
  }
}

// ---------- Madde tablosu ----------

async function maddeleriYukle(sartnameKimlik) {
  const s = await istekGonder(`/api/sartnameler/${sartnameKimlik}`);
  goster("madde-metin-uyarisi", s.metin_uzunlugu === 0);
  $("madde-cikar").disabled = s.metin_uzunlugu === 0;
  const govde = $("madde-satirlari");
  govde.replaceChildren(...s.maddeler.map(maddeSatiri));
  $("madde-durumu").textContent = s.maddeler.length ? "" : "Henüz madde yok.";
}

function maddeSatiri(m = {}) {
  const tr = document.createElement("tr");
  const no = Object.assign(document.createElement("input"), { type: "text", value: m.madde_no ?? "", placeholder: "4.2" });
  const sayfa = Object.assign(document.createElement("input"), { type: "number", min: "1", step: "1", value: m.sayfa ?? "" });
  const aciklama = Object.assign(document.createElement("textarea"), { value: m.aciklama ?? "", placeholder: "Şartnamedeki ifade" });
  const buyukluk = seciciOlustur(sartnameSecenekleri.buyuklukler, m.buyukluk);
  const sinir = seciciOlustur(sartnameSecenekleri.sinir_turleri, m.sinir_turu || "en_cok");
  const deger = Object.assign(document.createElement("input"), { type: "number", min: "0", step: "any", value: m.deger ?? "" });
  const birim = document.createElement("span");
  birim.className = "soluk";
  const sinif = seciciOlustur(sartnameSecenekleri.siniflar, m.sinif);
  const onay = Object.assign(document.createElement("input"), { type: "checkbox", checked: !!m.onaylandi, title: "Şartnameyle karşılaştırdım, doğru" });
  const sil = Object.assign(document.createElement("button"), { type: "button", className: "tehlike", textContent: "Sil" });
  sil.addEventListener("click", () => tr.remove());

  // Parça maddelerinde (GPS…) yalnızca "zorunlu" anlamlıdır ve değer girilmez.
  const buyuklugeGore = () => {
    const b = sartnameSecenekleri.buyuklukler.find((x) => x.deger === buyukluk.value);
    birim.textContent = b.birim ? ` ${b.birim}` : "";
    if (b.parca_mi) sinir.value = "zorunlu";
    sinir.disabled = b.parca_mi;
    deger.disabled = b.parca_mi;
  };
  buyukluk.addEventListener("change", buyuklugeGore);
  buyuklugeGore();

  const degerHucresi = document.createElement("td");
  degerHucresi.append(deger, birim);
  tr.append(hucreOlustur(no), hucreOlustur(sayfa), hucreOlustur(aciklama), hucreOlustur(buyukluk), hucreOlustur(sinir), degerHucresi,
    hucreOlustur(sinif), hucreOlustur(onay), hucreOlustur(sil));
  tr.oku = () => ({
    madde_no: no.value.trim() || null,
    sayfa: sayfa.value === "" ? null : Number(sayfa.value),
    aciklama: aciklama.value,
    buyukluk: buyukluk.value,
    sinir_turu: sinir.value,
    deger: deger.disabled || deger.value === "" ? null : Number(deger.value),
    sinif: sinif.value,
    onaylandi: onay.checked,
  });
  tr.onayla = () => { onay.checked = true; };
  return tr;
}

$("madde-ekle").addEventListener("click", () => {
  const tr = maddeSatiri({ sinif: "kesin" });
  $("madde-satirlari").append(tr);
  tr.querySelector("textarea").focus();
});

$("madde-hepsini-onayla").addEventListener("click", () => {
  for (const tr of $("madde-satirlari").children) tr.onayla();
  $("madde-durumu").textContent = "İşaretlendi; kaydetmeyi unutmayın.";
});

$("madde-kaydet").addEventListener("click", async () => {
  if (!droneSartnamesi) return;
  goster("madde-hatasi", false);
  const maddeler = [...$("madde-satirlari").children].map((tr) => tr.oku());
  try {
    await istekGonder(`/api/sartnameler/${droneSartnamesi.kimlik}/maddeler`, jsonIstegi("PUT", { maddeler }));
    await sartnameRaporunuYenile();
    $("madde-durumu").textContent = "Kaydedildi.";
  } catch (veri) {
    hataGoster("madde-hatasi", veri);
  }
});

$("madde-cikar").addEventListener("click", async () => {
  if (!droneSartnamesi) return;
  if ($("madde-satirlari").children.length &&
      !confirm("Gemini maddeleri yeniden çıkaracak; mevcut maddeler (onaylılar dahil) silinip yenileri gelecek. Devam edilsin mi?")) return;
  goster("madde-hatasi", false);
  $("madde-cikar").disabled = true;
  $("madde-durumu").textContent = "Gemini şartnameyi okuyor… (uzun belgelerde 1–2 dakika sürebilir)";
  try {
    const r = await istekGonder(`/api/sartnameler/${droneSartnamesi.kimlik}/cikar`, { method: "POST" });
    await sartnameRaporunuYenile();
    const atlanan = r.atlanan ? ` · ${r.atlanan} madde geçersiz geldiği için alınmadı` : "";
    $("madde-durumu").textContent =
      `${r.maddeler.length} madde çıkarıldı${atlanan} · bugün ${r.bugun_kullanilan}/${r.gunluk_sinir} istek. ` +
      "Her maddeyi şartnameyle karşılaştırıp onaylayın.";
  } catch (veri) {
    $("madde-durumu").textContent = "";
    hataGoster("madde-hatasi", veri);
  } finally {
    $("madde-cikar").disabled = false;
  }
});
