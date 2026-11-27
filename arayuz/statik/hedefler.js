// "Hedefler ve itki" sekmesi: drone hedefleri (uçuş süresi, yük, bütçe, itki/ağırlık, kablo/vida) ve
// drone'daki motorların itki tablosu. elektronik.js'ten sonra yüklenir
// (elektronikOzeti ve elektronikOzetiniYenile oradadır).
"use strict";

// Tablo sütunları: [alan adı, metin mi, ekrandaki ipucu].
const ITKI_SUTUNLARI = [
  ["gerilim_v", false, "22,2"],
  ["pervane", true, "5x4.3x3"],
  ["gaz_yuzde", false, "100"],
  ["itki_g", false, "1500"],
  ["akim_a", false, ""],
  ["guc_w", false, ""],
];

// Sekme her açıldığında sunucudaki son bilgiyle kurulur (parçalar Elektronik'te değişmiş olabilir).
function hedeflerSekmesiniAc() {
  if (!elektronikOzeti) return;
  const h = elektronikOzeti.hedefler;
  $("hd-ucus").value = h.ucus_suresi_dk ?? "";
  $("hd-yuk").value = h.yuk_g ?? "";
  $("hd-butce").value = h.butce_tl ?? "";
  $("hd-oran").value = h.itki_agirlik ?? "";
  // Boş bırakılırsa kullanım amacına göre varsayılan hedef geçerli; kutuda ve açıklamada gösterilir.
  const varsayilan = sayiBicimle(elektronikOzeti.ucus.amac_hedef_itki_agirlik, 1);
  $("hd-oran").placeholder = `boşsa ${varsayilan}`;
  $("hd-oran-aciklama").textContent =
    `Boş bırakırsan "${mevcutDrone.amac}" amacına göre ${varsayilan} hedeflenir. Sakin uçuş ve çekim için 2–3, ` +
    "freestyle için 4–8, yarış için 8 ve üstü yaygındır. 2'nin altı güvenli kalkış için önerilmez.";
  $("hd-kablo").value = h.kablo_vida_g ?? "";
  kabloIpucunuYaz();
  $("hd-kablo-aciklama").textContent =
    "Boş bırakırsan program kablo, vida, lehim ve bant için şasi + parça ağırlığının küçük bir oranını " +
    "tahmini pay olarak ekler. Bunları tartıp gram olarak girersen tahmin yerine senin değerin kullanılır.";
  // Drone bilgisi drone.js'teki mevcutDrone'dan okunur; ekrandaki metin değişse de bozulmaz.
  $("hedef-drone-bilgisi").textContent = `Drone: ${droneTanimi(mevcutDrone)} · ${elektronikOzeti.motor_sayisi} motor`;
  goster("hedef-hatasi", false);
  $("hedef-durumu").textContent = "";
  motorSeciciniKur();
}

// Kablo/vida kutusu boşken programın tahmin ettiği pay ipucu olarak gösterilir. Tartılmış değer
// kayıtlıyken tahmin hesaplanmadığı için genel bir ipucu yazılır.
function kabloIpucunuYaz() {
  const a = elektronikOzeti.agirlik;
  $("hd-kablo").placeholder = a.kablo_payi_elle_mi ? "boşsa tahmini pay" : `boşsa ≈ ${sayiBicimle(a.kablo_payi_g, 0)} (tahmini)`;
}

// Kimliği verilen girdideki sayıyı okur; boşsa null, sayı değilse kullanıcıya gösterilecek hata fırlatır.
function girdiSayisiOku(kimlik, ad) {
  const deger = sayiOku($(kimlik).value);
  if (Number.isNaN(deger)) throw { hata: `${ad} bir sayı olmalı.` };
  return deger;
}

$("hedef-formu").addEventListener("submit", async (olay) => {
  olay.preventDefault();
  goster("hedef-hatasi", false);
  try {
    const govde = {
      ucus_suresi_dk: girdiSayisiOku("hd-ucus", "Uçuş süresi"),
      yuk_g: girdiSayisiOku("hd-yuk", "Yük"),
      butce_tl: girdiSayisiOku("hd-butce", "Bütçe"),
      itki_agirlik: girdiSayisiOku("hd-oran", "İtki/ağırlık hedefi"),
      kablo_vida_g: girdiSayisiOku("hd-kablo", "Kablo ve vida ağırlığı"),
    };
    await istekGonder(`/api/dronelar/${droneKimligi}/hedefler`, jsonIstegi("PUT", govde));
    $("hedef-durumu").textContent = "Kaydedildi.";
    await elektronikOzetiniYenile();
    kabloIpucunuYaz();
  } catch (veri) {
    hataGoster("hedef-hatasi", veri);
  }
});

// ---------- İtki tablosu ----------

function droneMotorlari() {
  return elektronikOzeti.kalemler.filter((k) => k.parca.tur === "motor").map((k) => k.parca);
}

function motorSeciciniKur() {
  const motorlar = droneMotorlari();
  const secici = $("itki-motor");
  const onceki = secici.value;
  secici.replaceChildren(...motorlar.map((m) => new Option(m.gorunen_ad, String(m.kimlik))));
  if (motorlar.some((m) => String(m.kimlik) === onceki)) secici.value = onceki;
  goster("itki-motor-yok", motorlar.length === 0);
  goster("itki-alani", motorlar.length > 0);
  if (motorlar.length) itkiTablosunuCiz();
}

function seciliMotor() {
  return droneMotorlari().find((m) => String(m.kimlik) === $("itki-motor").value);
}

$("itki-motor").addEventListener("change", itkiTablosunuCiz);
$("itki-satir-ekle").addEventListener("click", () => $("itki-satirlari").append(itkiSatiri({})));
$("itki-kaydet").addEventListener("click", itkiTablosunuKaydet);

function itkiTablosunuCiz() {
  const motor = seciliMotor();
  const govde = $("itki-satirlari");
  govde.replaceChildren();
  const satirlar = (motor && motor.teknik.itki_tablosu) || [];
  for (const s of satirlar) govde.append(itkiSatiri(s));
  if (satirlar.length === 0) govde.append(itkiSatiri({}));
  $("itki-durumu").textContent = satirlar.length ? `${satirlar.length} satır kayıtlı` : "Tablo yok – uçuş hesabı tahmini formülü kullanıyor.";
  goster("itki-hatasi", false);
}

function itkiSatiri(veri) {
  const tr = document.createElement("tr");
  for (const [ad, metinMi, ipucu] of ITKI_SUTUNLARI) {
    const girdi = document.createElement("input");
    girdi.type = metinMi ? "text" : "number";
    if (!metinMi) { girdi.step = "any"; girdi.min = "0"; }
    else girdi.className = "pervane-girdisi";
    girdi.dataset.ad = ad;
    girdi.placeholder = ipucu;
    if (veri[ad] != null) girdi.value = veri[ad];
    const td = document.createElement("td");
    td.append(girdi);
    tr.append(td);
  }
  const sil = document.createElement("button");
  sil.type = "button";
  sil.className = "tehlike";
  sil.textContent = "Sil";
  sil.addEventListener("click", () => tr.remove());
  const td = document.createElement("td");
  td.append(sil);
  tr.append(td);
  return tr;
}

function itkiSatirlariniTopla() {
  const satirlar = [];
  for (const tr of $("itki-satirlari").querySelectorAll("tr")) {
    const satir = {};
    let dolu = false;
    for (const girdi of tr.querySelectorAll("input[data-ad]")) {
      const ham = girdi.value.trim();
      if (ham === "") { satir[girdi.dataset.ad] = null; continue; }
      dolu = true;
      satir[girdi.dataset.ad] = girdi.type === "text" ? ham : sayiOku(ham);
    }
    if (dolu) satirlar.push(satir); // tamamen boş satırlar atlanır
  }
  return satirlar;
}

async function itkiTablosunuKaydet() {
  const motor = seciliMotor();
  if (!motor) return;
  goster("itki-hatasi", false);
  $("itki-kaydet").disabled = true;
  try {
    await istekGonder(`/api/katalog/${motor.kimlik}/itki-tablosu`, jsonIstegi("PUT", { satirlar: itkiSatirlariniTopla() }));
    await elektronikOzetiniYenile();
    itkiTablosunuCiz();
    $("itki-durumu").textContent += " · kaydedildi";
  } catch (veri) {
    hataGoster("itki-hatasi", veri);
  } finally {
    $("itki-kaydet").disabled = false;
  }
}
