// Tüm sayfalarda kullanılan küçük yardımcılar.
// Kullanıcı verisi (drone adı, dosya adı) her zaman textContent ile yazılır;
// innerHTML kullanılmaz, böylece yazılan metin HTML olarak yorumlanmaz.
"use strict";

const $ = (kimlik) => document.getElementById(kimlik);

function goster(kimlik, gorunsun) {
  $(kimlik).classList.toggle("gizli", !gorunsun);
}

function sayiBicimle(deger, basamak) {
  return Number(deger).toLocaleString("tr-TR", { minimumFractionDigits: basamak, maximumFractionDigits: basamak });
}

function zamanBicimle(isoZaman) {
  const tarih = new Date(isoZaman);
  return isNaN(tarih) ? isoZaman : tarih.toLocaleString("tr-TR", { dateStyle: "medium", timeStyle: "short" });
}

// Sunucuya istek gönderir; hata durumunda {hata, rehber} nesnesi fırlatır.
async function istekGonder(adres, secenekler = {}) {
  let yanit;
  try {
    yanit = await fetch(adres, secenekler);
  } catch {
    throw { hata: "Programın sunucusuna ulaşılamadı. Program kapanmış olabilir." };
  }
  const veri = await yanit.json().catch(() => ({}));
  if (!yanit.ok) throw veri;
  return veri;
}

function jsonIstegi(yontem, govde) {
  return { method: yontem, headers: { "Content-Type": "application/json" }, body: JSON.stringify(govde) };
}

function tabloDoldur(govdeKimligi, satirlar) {
  const govde = $(govdeKimligi);
  govde.replaceChildren();
  for (const [baslik, deger] of satirlar) {
    const tr = document.createElement("tr");
    const td1 = document.createElement("td");
    const td2 = document.createElement("td");
    td1.textContent = baslik;
    td2.textContent = deger;
    tr.append(td1, td2);
    govde.append(tr);
  }
}

// Başlık + madde listesi olan uyarı/hata kutusunu doldurur; madde yoksa gizler.
function listeKutusu(kimlik, baslik, maddeler, siraliMi = false) {
  const kutu = $(kimlik);
  kutu.replaceChildren();
  if (!maddeler || maddeler.length === 0) {
    goster(kimlik, false);
    return;
  }
  const b = document.createElement("strong");
  b.textContent = baslik;
  const liste = document.createElement(siraliMi ? "ol" : "ul");
  for (const m of maddeler) {
    const li = document.createElement("li");
    li.textContent = m;
    liste.append(li);
  }
  kutu.append(b, liste);
  goster(kimlik, true);
}

// ---------- SVG çizim yardımcıları ----------

const SVG_AD_ALANI = "http://www.w3.org/2000/svg";

// SVG öğesi oluşturur: svgOge("circle", {cx: 5, r: 2}, ...çocuklar). Metin her zaman textContent ile yazılır.
function svgOge(ad, nitelikler = {}, ...cocuklar) {
  const oge = document.createElementNS(SVG_AD_ALANI, ad);
  for (const [anahtar, deger] of Object.entries(nitelikler)) {
    if (deger !== null && deger !== undefined) oge.setAttribute(anahtar, String(deger));
  }
  for (const c of cocuklar) {
    if (c === null || c === undefined) continue;
    oge.append(typeof c === "string" ? document.createTextNode(c) : c);
  }
  return oge;
}

// SVG'ye fareyle gelince görünen açıklama ekler.
function svgIpucu(oge, metin) {
  oge.append(svgOge("title", {}, metin));
  return oge;
}

// DEĞİŞTİRİLEBİLİR: Rotor sayısına göre kol uzunluğu ve pervane yarıçapı (viewBox 100 × 100 içinde).
const DRONE_CIZIM_OLCULERI = {
  4: { kol: 42, pervane: 16, govde: "kare" },
  6: { kol: 40, pervane: 11.5, govde: "daire" },
  8: { kol: 41, pervane: 9, govde: "daire" },
};

// Yukarıdan bakılmış çok rotorlu drone. motorSayisi 4 (quad, X düzeni), 6 (hexa) veya 8 (okto).
// Pervaneler .pervane sınıfıyla döndürülebilir; komşu pervaneler ters yöne döner (gerçekteki gibi).
// Renk "currentColor"dan gelir; boyut kapsayan SVG'nin genişliğiyle belirlenir.
function droneCizimi(sinif = "", motorSayisi = 4) {
  const o = DRONE_CIZIM_OLCULERI[motorSayisi] || DRONE_CIZIM_OLCULERI[4];
  const konumlar = [];
  for (let i = 0; i < motorSayisi; i++) {
    // İlk kol öne-sağa bakar (quad'da X düzeni); kollar eşit açıyla dizilir.
    const aci = ((360 / motorSayisi) * i + 180 / motorSayisi - 90) * (Math.PI / 180);
    konumlar.push([50 + o.kol * Math.cos(aci), 50 + o.kol * Math.sin(aci), i % 2 === 1]);
  }
  const p = o.pervane;
  const kol = (x, y) => svgOge("line", { x1: 50, y1: 50, x2: x, y2: y, stroke: "currentColor", "stroke-width": motorSayisi === 4 ? 6 : 4.5, "stroke-linecap": "round" });
  const rotor = (x, y, ters) => svgOge("g", {},
    svgOge("circle", { cx: x, cy: y, r: p + 1, fill: "currentColor", opacity: 0.12 }),
    svgOge("g", { class: "pervane" + (ters ? " ters" : "") },
      svgOge("ellipse", { cx: x, cy: y, rx: p, ry: p * 0.16, fill: "currentColor", opacity: 0.85 }),
      svgOge("ellipse", { cx: x, cy: y, rx: p * 0.16, ry: p, fill: "currentColor", opacity: 0.35 })),
    svgOge("circle", { cx: x, cy: y, r: p * 0.25 + 1, fill: "currentColor" }));
  const govde = o.govde === "kare"
    ? svgOge("rect", { x: 38, y: 36, width: 24, height: 28, rx: 6, fill: "currentColor" })
    : svgOge("circle", { cx: 50, cy: 50, r: 13, fill: "currentColor" });
  return svgOge("svg", { viewBox: "0 0 100 100", class: sinif, "aria-hidden": "true" },
    svgOge("g", { class: "govde-salinimi" },
      ...konumlar.map(([x, y]) => kol(x, y)),
      govde,
      svgOge("circle", { class: "led", cx: 50, cy: o.govde === "kare" ? 40 : 44, r: 2.5, fill: "#4ade80" }),
      ...konumlar.map(([x, y, ters]) => rotor(x, y, ters))));
}

// Başlıktaki saat ve sistem durumu (yalnızca o öğe olan sayfalarda çalışır).
function saatiBaslat() {
  const saat = document.getElementById("sistem-saati");
  if (!saat) return;
  const yaz = () => { saat.textContent = new Date().toLocaleTimeString("tr-TR", { hour12: false }); };
  yaz();
  setInterval(yaz, 1000);
}
document.addEventListener("DOMContentLoaded", saatiBaslat);

// Sunucudan gelen hatayı (varsa dışa aktarma rehberiyle) kutuda gösterir.
function hataGoster(kutuKimligi, veri) {
  const kutu = $(kutuKimligi);
  kutu.replaceChildren();
  const mesaj = document.createElement("div");
  mesaj.textContent = (veri && veri.hata) || "Bilinmeyen bir hata oluştu.";
  kutu.append(mesaj);
  if (veri && veri.rehber && veri.rehber.length) {
    const b = document.createElement("strong");
    b.textContent = "Nasıl dışa aktarılır:";
    const liste = document.createElement("ol");
    for (const adim of veri.rehber) {
      const li = document.createElement("li");
      li.textContent = adim;
      liste.append(li);
    }
    kutu.append(b, liste);
  }
  goster(kutuKimligi, true);
}
