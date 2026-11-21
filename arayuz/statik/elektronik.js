// Drone sayfasındaki elektronik bölümü: parça listesi, zorunlu parçalar,
// ağırlık özeti ve parça ekleme/düzenleme formu.
// Bu dosya drone.js'ten önce yüklenir; droneKimligi drone.js'te tanımlıdır.
"use strict";

// DEĞİŞTİRİLEBİLİR: Katalog önerileri için yazmayı bitirdikten sonra bekleme (ms) ve gösterilecek öneri sayısı.
const ONERI_BEKLEME_MS = 300;
const EN_FAZLA_ONERI = 5;
// DEĞİŞTİRİLEBİLİR: Ekranda gösterilen ondalık basamak sayıları (öneri paneli ve görseller de kullanır).
const AGIRLIK_BASAMAK = 1;
const ORAN_BASAMAK = 1;
const AKIM_BASAMAK = 1;
const SURE_BASAMAK = 1;
const ITKI_BASAMAK = 0;
const YUZDE_BASAMAK = 0;

const ZORUNLU_ISARETLERI = { tamam: "✓", eksik: "✗", bilinmiyor: "?", istege_bagli: "–", onerilen: "!" };
const UYUM_ISARETLERI = { uygunsuz: "✗", uyari: "⚠", bilinmiyor: "?", uygun: "✓" };
const UYUM_ADLARI = { uygunsuz: "uyumsuz", uyari: "dikkat", bilinmiyor: "doğrulanamıyor", uygun: "uygun" };

let turTanimlari = null;   // /api/parca-turleri yanıtı
let elektronikOzeti = null; // /api/dronelar/{k}/elektronik yanıtı
let formModu = null;        // {tip: "ekle"} veya {tip: "duzenle", parca}
let oneriZamanlayicisi = null;

// ---------- Başlatma ve yenileme ----------

// drone.js sayfa açılırken çağırır.
async function elektronikBolumunuBaslat() {
  turTanimlari = await istekGonder("/api/parca-turleri");
  seceneklereYaz("pf-tur", turTanimlari.turler);
  seceneklereYaz("pf-alt-tur", turTanimlari.alt_turler);
  seceneklereYaz("pf-durum", turTanimlari.durumlar);
}

// Şasi ağırlığı değişince drone.js de çağırır.
async function elektronikOzetiniYenile() {
  if (!droneKimligi || !turTanimlari) return;
  try {
    elektronikOzeti = await istekGonder(`/api/dronelar/${droneKimligi}/elektronik`);
    ozetiCiz();
  } catch (veri) {
    hataGoster("elektronik-hatasi", veri);
  }
}

function turTanimi(tur) {
  return turTanimlari.turler.find((t) => t.deger === tur);
}

// ---------- Özet: zorunlular + ağırlık ----------

function ozetiCiz() {
  const o = elektronikOzeti;

  const cipler = $("zorunlu-listesi");
  cipler.replaceChildren();
  for (const z of o.zorunluluklar) {
    const cip = document.createElement("span");
    cip.className = `cip cip-${z.durum}`;
    cip.title = z.aciklama;
    cip.textContent = `${ZORUNLU_ISARETLERI[z.durum] || ""} ${z.etiket}: ${z.aciklama}`;
    cipler.append(cip);
  }

  const a = o.agirlik;
  const g = (deger) => `${sayiBicimle(deger, AGIRLIK_BASAMAK)} g`;
  const satirlar = [
    ["Şasi", a.sasi_g != null ? g(a.sasi_g) : "girilmedi (Şasi sekmesinden girin)"],
    ["Parçalar (ağırlığı bilinenler)", g(a.parcalar_g)],
    ["Kablo, vida vb. payı (tahmini)", g(a.kablo_payi_g)],
    [a.eksiksiz_mi ? "Toplam (tahmini)" : "Toplam (eksik, tahmini)", g(a.toplam_g)],
  ];
  tabloDoldur("agirlik-tablosu", satirlar);

  const uyarilar = [];
  if (a.sasi_g == null) uyarilar.push("Şasi ağırlığı girilmemiş; toplama katılmadı.");
  for (const ad of a.agirligi_eksik_parcalar) uyarilar.push(`${ad}: ağırlık girilmemiş, toplama katılmadı.`);
  listeKutusu("agirlik-uyarisi", "Toplam ağırlık eksik olabilir:", uyarilar);

  ucusHesabiniCiz();
  uyumListesiniCiz();
  parcaListesiniCiz();
  gorselleriCiz();
  ustOzetiYenile();
}

// ---------- Uçuş hesabı ----------

// İtki/ağırlık hedefinin nereden geldiği (Hedefler sekmesinde girilen ya da kullanım amacına göre varsayılan).
function hedefKaynagiMetni(u) {
  return u.hedef_itki_agirlik_elle_mi ? "senin hedefin" : "kullanım amacına göre";
}

function ucusHesabiniCiz() {
  const u = elektronikOzeti.ucus;
  const oran = u.itki_agirlik_orani;
  let oranMetni = hesapMetni(oran, "", ORAN_BASAMAK);
  if (oran.deger != null) {
    const hedef = `hedef ≥ ${sayiBicimle(u.hedef_itki_agirlik, ORAN_BASAMAK)} (${hedefKaynagiMetni(u)})`;
    oranMetni += u.hedefe_ulasiyor_mu ? ` ✓ ${hedef}` : ` ✗ ${hedef}, düşük`;
  }
  const satirlar = [
    ["Toplam ağırlık", hesapMetni(u.toplam_agirlik_g, " g", AGIRLIK_BASAMAK)],
    ["Toplam en büyük itki", hesapMetni(u.toplam_itki_g, " g", ITKI_BASAMAK)],
    ["İtki / ağırlık", oranMetni],
    ["Asılı kalma gazı", hesapMetni(u.asili_gaz_yuzde, " %", YUZDE_BASAMAK)],
    ["Asılı kalma akımı (toplam)", hesapMetni(u.asili_akim_a, " A", AKIM_BASAMAK)],
    ["Tam gaz akımı (toplam)", hesapMetni(u.toplam_maks_akim_a, " A", AKIM_BASAMAK)],
    ["Uçuş süresi", ucusSuresiMetni(u)],
  ];
  const yuk = elektronikOzeti.hedefler.yuk_g;
  if (yuk) satirlar.splice(1, 0, ["Taşınacak yük (hedeflerden)", `${sayiBicimle(yuk, AGIRLIK_BASAMAK)} g (toplama dahil)`]);
  // Değerin nasıl hesaplandığı satırın üzerine gelince görünür (yük satırının açıklaması yok).
  const degerler = [u.toplam_agirlik_g, u.toplam_itki_g, oran, u.asili_gaz_yuzde, u.asili_akim_a, u.toplam_maks_akim_a, u.ucus_suresi_dk];
  if (yuk) degerler.splice(1, 0, null);
  tabloDoldur("ucus-tablosu", satirlar);
  const hucreler = $("ucus-tablosu").querySelectorAll("tr td:last-child");
  degerler.forEach((h, i) => { if (h && hucreler[i] && h.deger != null) hucreler[i].title = h.aciklama; });

  const notlar = $("ucus-notlari");
  notlar.replaceChildren(...u.notlar.map((n) => {
    const li = document.createElement("li");
    li.textContent = n;
    return li;
  }));
  goster("ucus-notlari", u.notlar.length > 0);
}

function ucusSuresiMetni(u) {
  let metin = hesapMetni(u.ucus_suresi_dk, " dk", SURE_BASAMAK);
  if (u.hedef_ucus_suresi_dk != null && u.ucus_suresi_dk.deger != null) {
    const hedef = sayiBicimle(u.hedef_ucus_suresi_dk, SURE_BASAMAK);
    metin += u.ucus_suresi_hedefe_ulasiyor_mu ? ` ✓ hedef ≥ ${hedef} dk` : ` ✗ hedef ≥ ${hedef} dk (yetersiz)`;
  }
  return metin;
}

// ---------- Uyum kontrolleri ----------

function uyumListesiniCiz() {
  const sonuclar = elektronikOzeti.uyum;
  const sayac = $("uyum-sayaci");
  sayac.replaceChildren();
  for (const [durum, ad] of Object.entries(UYUM_ADLARI)) {
    const adet = sonuclar.filter((s) => s.durum === durum).length;
    if (adet === 0) continue;
    const cip = document.createElement("span");
    cip.className = `cip cip-uyum-${durum}`;
    cip.textContent = `${UYUM_ISARETLERI[durum]} ${adet} ${ad}`;
    sayac.append(cip);
  }

  const liste = $("uyum-listesi");
  liste.replaceChildren();
  // Sorunlu olanlar üstte: uyumsuz, dikkat, bilinmiyor, uygun.
  const sirali = [...sonuclar].sort((a, b) => UYUM_DURUM_SIRASI.indexOf(a.durum) - UYUM_DURUM_SIRASI.indexOf(b.durum));
  for (const s of sirali) {
    const satir = document.createElement("div");
    satir.className = `uyum-satiri uyum-${s.durum}`;
    const isaret = document.createElement("span");
    isaret.className = "uyum-isareti";
    isaret.textContent = UYUM_ISARETLERI[s.durum];
    const metin = document.createElement("div");
    const baslik = document.createElement("div");
    baslik.className = "liste-baslik";
    baslik.textContent = `${s.kod} · ${s.baslik}`;
    if (s.tahmini) {
      const rozet = document.createElement("span");
      rozet.className = "etiket uyari";
      rozet.textContent = "tahmini";
      baslik.append(rozet);
    }
    const aciklama = document.createElement("div");
    aciklama.className = "soluk";
    aciklama.style.whiteSpace = "pre-line"; // birden çok çiftin mesajı alt alta
    aciklama.textContent = s.aciklama;
    metin.append(baslik, aciklama);
    satir.append(isaret, metin);
    liste.append(satir);
  }
}

// ---------- Parça listesi ----------

function parcaListesiniCiz() {
  const liste = $("parca-listesi");
  liste.replaceChildren();
  const kalemler = elektronikOzeti.kalemler;
  goster("parca-listesi-bos", kalemler.length === 0);

  // Türlere göre, tür listesindeki sırayla grupla.
  for (const tur of turTanimlari.turler) {
    const grup = kalemler.filter((k) => k.parca.tur === tur.deger);
    if (grup.length === 0) continue;
    const baslik = document.createElement("div");
    baslik.className = "grup-basligi";
    baslik.textContent = tur.ad;
    liste.append(baslik, ...grup.map(parcaSatiri));
  }
}

function parcaSatiri({ bag, parca }) {
  const satir = document.createElement("div");
  satir.className = "liste-satiri";

  // Sol: ad, ayrıntılar, rozetler
  const bilgi = document.createElement("div");
  const ad = document.createElement("div");
  ad.className = "liste-baslik";
  ad.textContent = parca.gorunen_ad + (parca.alt_tur_adi ? ` (${parca.alt_tur_adi})` : "");
  const ayrinti = document.createElement("div");
  ayrinti.className = "soluk";
  const agirlik = parca.agirlik_g != null
    ? `${sayiBicimle(parca.agirlik_g, AGIRLIK_BASAMAK)} g × ${bag.adet} = ${sayiBicimle(parca.agirlik_g * bag.adet, AGIRLIK_BASAMAK)} g`
    : "ağırlık girilmemiş";
  const eksik = parca.eksik_alanlar.length ? ` · ${parca.eksik_alanlar.length} teknik değer boş` : "";
  ayrinti.textContent = agirlik + eksik;
  bilgi.append(ad, ayrinti);
  if (!parca.dogrulandi) {
    const rozet = document.createElement("span");
    rozet.className = "etiket uyari";
    rozet.textContent = "doğrulanmadı";
    ad.append(rozet);
  }
  if (parca.kaynak_url) {
    const baglanti = document.createElement("a");
    baglanti.href = parca.kaynak_url; // sunucu yalnızca http(s) bağlantı kabul ediyor
    baglanti.target = "_blank";
    baglanti.rel = "noopener noreferrer";
    baglanti.className = "kaynak";
    baglanti.textContent = "kaynak";
    ayrinti.append(" · ", baglanti);
  }

  // Sağ: adet, durum, düğmeler
  const kontroller = document.createElement("div");
  kontroller.className = "satir";

  const adet = document.createElement("input");
  adet.type = "number";
  adet.min = "1";
  adet.step = "1";
  adet.value = bag.adet;
  adet.className = "adet-girdisi";
  adet.title = "Adet";
  adet.addEventListener("change", () => bagGuncelle(bag, { adet: Number(adet.value) }));

  const durum = document.createElement("select");
  for (const d of turTanimlari.durumlar) durum.append(new Option(d.ad, d.deger));
  durum.value = bag.durum;
  durum.title = "Bu drone'daki durumu";
  durum.addEventListener("change", () => bagGuncelle(bag, { durum: durum.value }));

  const duzenle = document.createElement("button");
  duzenle.type = "button";
  duzenle.className = "ikincil";
  duzenle.textContent = "Düzenle";
  duzenle.addEventListener("click", () => formuAc({ tip: "duzenle", parca }));

  const kaldir = document.createElement("button");
  kaldir.type = "button";
  kaldir.className = "tehlike";
  kaldir.textContent = "Kaldır";
  kaldir.addEventListener("click", () => bagSil(bag, parca));

  kontroller.append(adet, durum, duzenle, kaldir);
  satir.append(bilgi, kontroller);
  return satir;
}

async function bagGuncelle(bag, degisiklik) {
  goster("elektronik-hatasi", false);
  try {
    await istekGonder(`/api/dronelar/${droneKimligi}/parcalar/${bag.kimlik}`, jsonIstegi("PATCH", degisiklik));
  } catch (veri) {
    hataGoster("elektronik-hatasi", veri);
  }
  await elektronikOzetiniYenile();
}

async function bagSil(bag, parca) {
  if (!confirm(`"${parca.gorunen_ad}" bu drone'dan kaldırılsın mı? (Parça katalogda kalır.)`)) return;
  goster("elektronik-hatasi", false);
  try {
    await istekGonder(`/api/dronelar/${droneKimligi}/parcalar/${bag.kimlik}`, { method: "DELETE" });
  } catch (veri) {
    hataGoster("elektronik-hatasi", veri);
  }
  await elektronikOzetiniYenile();
}

// ---------- Parça formu ----------

$("parca-ekle-dugmesi").addEventListener("click", () => formuAc({ tip: "ekle" }));
$("pf-vazgec").addEventListener("click", formuKapat);
$("pf-tur").addEventListener("change", () => {
  teknikAlanlariCiz($("pf-tur").value, {});
  turaGoreAlanlariGoster();
  katalogOnerileriniPlanla();
});
$("pf-alt-tur").addEventListener("change", katalogOnerileriniPlanla);
$("pf-uretici").addEventListener("input", katalogOnerileriniPlanla);
$("pf-model").addEventListener("input", katalogOnerileriniPlanla);

function formuAc(mod) {
  formModu = mod;
  const duzenleme = mod.tip === "duzenle";
  const p = duzenleme ? mod.parca : null;

  $("parca-formu-basligi").textContent = duzenleme ? `Parçayı düzenle: ${p.gorunen_ad}` : "Parça ekle";
  goster("parca-formu-notu", duzenleme);
  for (const alan of document.querySelectorAll(".pf-ekleme-alani")) alan.classList.toggle("gizli", duzenleme);
  $("pf-tur").disabled = duzenleme; // katalogdaki parçanın türü değiştirilemez
  $("pf-alt-tur").disabled = duzenleme;

  $("pf-tur").value = p ? p.tur : $("pf-tur").value || turTanimlari.turler[0].deger;
  $("pf-alt-tur").value = p && p.alt_tur ? p.alt_tur : turTanimlari.alt_turler[0].deger;
  $("pf-uretici").value = p ? p.uretici : "";
  $("pf-model").value = p ? p.model : "";
  $("pf-agirlik").value = p && p.agirlik_g != null ? p.agirlik_g : "";
  $("pf-adet").value = 1;
  $("pf-durum").value = "planlanan";
  $("pf-kaynak").value = p && p.kaynak_url ? p.kaynak_url : "";
  $("pf-notlar").value = p && p.notlar ? p.notlar : "";

  teknikAlanlariCiz($("pf-tur").value, p ? p.teknik : {});
  $("pf-teknik-kutusu").open = duzenleme;
  turaGoreAlanlariGoster();
  goster("katalog-onerileri", false);
  goster("parca-formu-hatasi", false);
  goster("parca-formu-karti", true);
  $("parca-formu-karti").scrollIntoView({ behavior: "smooth", block: "start" });
  $("pf-uretici").focus();
}

function formuKapat() {
  formModu = null;
  goster("parca-formu-karti", false);
}

function turaGoreAlanlariGoster() {
  const digerMi = $("pf-tur").value === "diger";
  for (const alan of document.querySelectorAll(".pf-alt-tur-alani")) alan.classList.toggle("gizli", !digerMi);
}

// Seçilen türün teknik alanlarını, sunucudan gelen tanımlara göre kurar.
function teknikAlanlariCiz(tur, degerler) {
  const kap = $("pf-teknik");
  kap.replaceChildren();
  for (const alan of turTanimi(tur).alanlar) {
    const kimlik = `pf-t-${alan.ad}`;
    const etiket = document.createElement("label");
    etiket.htmlFor = kimlik;
    etiket.textContent = alan.etiket;
    const girdi = teknikGirdisiOlustur(alan, degerler[alan.ad]);
    girdi.id = kimlik;
    girdi.dataset.ad = alan.ad;
    girdi.dataset.cins = alan.cins;
    kap.append(etiket, girdi);
  }
}

function teknikGirdisiOlustur(alan, deger) {
  const bos = deger === null || deger === undefined;
  if (alan.cins === "secim" || alan.cins === "mantiksal") {
    const secici = document.createElement("select");
    secici.append(new Option("bilinmiyor", ""));
    const secenekler = alan.cins === "secim"
      ? alan.secenekler
      : [{ deger: "evet", ad: "Evet" }, { deger: "hayir", ad: "Hayır" }];
    for (const s of secenekler) secici.append(new Option(s.ad, s.deger));
    if (!bos) secici.value = alan.cins === "mantiksal" ? (deger ? "evet" : "hayir") : deger;
    return secici;
  }
  const girdi = document.createElement("input");
  if (alan.cins === "tamsayi" || alan.cins === "sayi") {
    girdi.type = "number";
    girdi.step = alan.cins === "tamsayi" ? "1" : "any";
    girdi.min = alan.cins === "tamsayi" ? "1" : "0";
  } else {
    girdi.type = "text";
    if (alan.cins === "metin_listesi") girdi.placeholder = "ör. DShot600, DShot300";
    if (alan.cins === "sayi_listesi") girdi.placeholder = "ör. 5; 9";
  }
  if (!bos) girdi.value = Array.isArray(deger) ? deger.join(alan.cins === "sayi_listesi" ? "; " : ", ") : deger;
  girdi.placeholder ||= "bilinmiyor";
  return girdi;
}

// Formdaki teknik alanları sunucunun beklediği türlere çevirir; boş alan null olur.
function teknikDegerleriTopla() {
  const teknik = {};
  for (const girdi of $("pf-teknik").querySelectorAll("[data-ad]")) {
    const ham = girdi.value.trim();
    const { ad, cins } = girdi.dataset;
    if (ham === "") {
      teknik[ad] = null;
    } else if (cins === "tamsayi" || cins === "sayi") {
      teknik[ad] = Number(ham);
    } else if (cins === "mantiksal") {
      teknik[ad] = ham === "evet";
    } else if (cins === "metin_listesi") {
      teknik[ad] = ham.split(/[,;]/).map((s) => s.trim()).filter(Boolean);
    } else if (cins === "sayi_listesi") {
      // Ondalık için virgül de kabul edilir (5,5); öğeler noktalı virgül veya boşlukla ayrılır.
      teknik[ad] = ham.split(/[;\s]+/).filter(Boolean).map((s) => sayiOku(s));
      if (teknik[ad].some(Number.isNaN)) throw { hata: `${girdi.previousSibling.textContent}: sayıları "5; 9" biçiminde yazın.` };
    } else {
      teknik[ad] = ham;
    }
  }
  return teknik;
}

function parcaBilgisiTopla() {
  const agirlik = $("pf-agirlik").value.trim();
  const tur = $("pf-tur").value;
  return {
    tur,
    alt_tur: tur === "diger" ? $("pf-alt-tur").value : null,
    uretici: $("pf-uretici").value,
    model: $("pf-model").value,
    agirlik_g: agirlik === "" ? null : Number(agirlik),
    kaynak_url: $("pf-kaynak").value.trim() || null,
    notlar: $("pf-notlar").value.trim() || null,
    teknik: teknikDegerleriTopla(),
  };
}

$("parca-formu").addEventListener("submit", async (olay) => {
  olay.preventDefault();
  goster("parca-formu-hatasi", false);
  $("pf-kaydet").disabled = true;
  try {
    const bilgi = parcaBilgisiTopla();
    if (formModu.tip === "duzenle") {
      await istekGonder(`/api/katalog/${formModu.parca.kimlik}`, jsonIstegi("PUT", bilgi));
    } else {
      await istekGonder(
        `/api/dronelar/${droneKimligi}/parcalar`,
        jsonIstegi("POST", { parca: bilgi, adet: Number($("pf-adet").value), durum: $("pf-durum").value })
      );
    }
    formuKapat();
    await elektronikOzetiniYenile();
  } catch (veri) {
    hataGoster("parca-formu-hatasi", veri);
    if (veri && veri.mevcut_kimlik && formModu.tip === "ekle") mevcutKaydiOner(veri.mevcut_kimlik);
  } finally {
    $("pf-kaydet").disabled = false;
  }
});

// Aynı parça katalogda varsa, hata kutusuna "katalogdakini kullan" düğmesi eklenir.
function mevcutKaydiOner(parcaKimlik) {
  const dugme = document.createElement("button");
  dugme.type = "button";
  dugme.textContent = "Katalogdaki kaydı bu drone'a ekle";
  dugme.style.marginTop = "8px";
  dugme.addEventListener("click", () => katalogdanEkle(parcaKimlik));
  $("parca-formu-hatasi").append(dugme);
}

async function katalogdanEkle(parcaKimlik) {
  goster("parca-formu-hatasi", false);
  try {
    await istekGonder(
      `/api/dronelar/${droneKimligi}/parcalar`,
      jsonIstegi("POST", { parca_kimlik: parcaKimlik, adet: Number($("pf-adet").value), durum: $("pf-durum").value })
    );
    formuKapat();
    await elektronikOzetiniYenile();
  } catch (veri) {
    hataGoster("parca-formu-hatasi", veri);
  }
}

// ---------- Katalog önerileri (yazarken) ----------

function katalogOnerileriniPlanla() {
  clearTimeout(oneriZamanlayicisi);
  oneriZamanlayicisi = setTimeout(katalogOnerileriniGoster, ONERI_BEKLEME_MS);
}

async function katalogOnerileriniGoster() {
  const kutu = $("katalog-onerileri");
  const metin = `${$("pf-uretici").value} ${$("pf-model").value}`.trim();
  if (!formModu || formModu.tip !== "ekle" || metin.length < 2) {
    goster("katalog-onerileri", false);
    return;
  }
  const tur = $("pf-tur").value;
  const parametreler = new URLSearchParams({ metin, tur });
  if (tur === "diger") parametreler.set("alt_tur", $("pf-alt-tur").value);
  let sonuclar;
  try {
    sonuclar = await istekGonder(`/api/katalog?${parametreler}`);
  } catch {
    return; // öneri gösterilememesi formu engellemesin
  }
  // Bu drone'da zaten olan parçalar önerilmez.
  const mevcut = new Set(elektronikOzeti.kalemler.map((k) => k.parca.kimlik));
  sonuclar = sonuclar.filter((p) => !mevcut.has(p.kimlik)).slice(0, EN_FAZLA_ONERI);

  kutu.replaceChildren();
  if (sonuclar.length === 0) {
    goster("katalog-onerileri", false);
    return;
  }
  const baslik = document.createElement("div");
  baslik.className = "soluk";
  baslik.textContent = "Katalogda kayıtlı benzer parçalar (yeniden yazmanıza gerek yok):";
  kutu.append(baslik);
  for (const p of sonuclar) {
    const satir = document.createElement("div");
    satir.className = "liste-satiri";
    const ad = document.createElement("div");
    ad.textContent = p.gorunen_ad + (p.agirlik_g != null ? ` · ${sayiBicimle(p.agirlik_g, AGIRLIK_BASAMAK)} g` : "");
    const sec = document.createElement("button");
    sec.type = "button";
    sec.className = "ikincil";
    sec.textContent = "Bunu ekle";
    sec.addEventListener("click", () => katalogdanEkle(p.kimlik));
    satir.append(ad, sec);
    kutu.append(satir);
  }
  goster("katalog-onerileri", true);
}
