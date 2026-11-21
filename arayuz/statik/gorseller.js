// Drone sayfasının görselleri: şasi üstten görünüşü, uçuş göstergeleri, ağırlık
// dağılımı ve uyum bağlantı şeması. Hepsi elektronik özetinden (elektronikOzeti)
// çizilir; özet her yenilendiğinde gorselleriCiz() çağrılır. Ek kütüphane yoktur (SVG).
"use strict";

// DEĞİŞTİRİLEBİLİR: Görsel etiketlerindeki ondalık basamaklar (çizimde yer dar olduğu için az basamak).
// Oran, süre, ağırlık ve yüzde basamakları elektronik.js'teki tablolarla aynı kalsın diye oradan gelir.
const GORUNUM_MM_BASAMAK = 0;
const GORUNUM_INC_BASAMAK = 1;
const LEJANT_AGIRLIK_BASAMAK = 0;

// DEĞİŞTİRİLEBİLİR: Ağırlık dağılımı renkleri (koyu zeminde birbirinden ayırt edilebilir).
const AGIRLIK_RENKLERI = ["#4f8cff", "#22d3ee", "#a78bfa", "#f472b6", "#fbbf24", "#34d399", "#fb923c", "#e879f9", "#60a5fa", "#94a3b8", "#cbd5e1"];

// DEĞİŞTİRİLEBİLİR: Asılı kalma gazı bölgeleri (%). Düşük gaz güç fazlası, yüksek gaz zorlanma demektir.
const GAZ_BOLGELERI = [
  { bitis: 50, sinif: "dolgu-uygun" },
  { bitis: 70, sinif: "dolgu-uyari" },
  { bitis: 100, sinif: "dolgu-uygunsuz" },
];

function enKotuDurum(durumlar) {
  return UYUM_DURUM_SIRASI.find((d) => durumlar.includes(d)) || "bilinmiyor";
}

function uyumSonucu(kod) {
  return elektronikOzeti.uyum.find((u) => u.kod === kod);
}

function gorselleriCiz() {
  if (!elektronikOzeti) return;
  sasiGorunumunuCiz();
  ucusGostergeleriniCiz();
  agirlikDagiliminiCiz();
  uyumSemasiniCiz();
}

// ---------- Şasi üstten görünüş ----------

function sasiGorunumunuCiz() {
  const kap = $("sasi-gorunumu");
  const g = elektronikOzeti.sasi_gorunumu;
  if (!g) {
    bosMesaj(kap, elektronikOzeti.sasi_dingil_bilinmiyor
      ? "Parçalı şaside motor yerleri dingil mesafesine göre çizilir. Yukarıdaki \"Dingil mesafesi\" kartından " +
        "dingili gir veya gövde ve koldan hesaplat."
      : "Şasi dosyası yükleyip birimini onaylayınca üstten görünüş burada çizilir.");
    return;
  }
  const n = elektronikOzeti.motor_sayisi;
  const R = g.dingil_mm / 2;
  // İnç → mm dönüşümü sunucuda yapılır; inç değerleri yalnızca etikette gösterilir.
  const pervaneInc = g.pervane_cap_inc;
  const pervaneR = g.pervane_cap_mm ? g.pervane_cap_mm / 2 : 0;
  const sinirR = g.en_buyuk_pervane_mm ? g.en_buyuk_pervane_mm / 2 : 0;
  const k5 = uyumSonucu("K5");
  const durum = pervaneInc ? (k5 ? k5.durum : "bilinmiyor") : "bilinmiyor";

  const yari = Math.max(g.en_mm / 2, g.boy_mm / 2, R + Math.max(pervaneR, sinirR)) * 1.08;
  const yazi = yari * 0.065;
  const svg = svgOge("svg", { viewBox: `${-yari} ${-yari} ${2 * yari} ${2 * yari + yazi * 3}`, class: "gorsel", style: "max-height:440px" });

  svg.append(svgOge("rect", {
    x: -g.en_mm / 2, y: -g.boy_mm / 2, width: g.en_mm, height: g.boy_mm, rx: yazi * 0.4,
    fill: "none", stroke: "var(--soluk-yazi)", "stroke-dasharray": `${yazi * 0.5} ${yazi * 0.5}`, "stroke-width": yazi * 0.08,
  }));

  // Motorlar bir çember üzerinde eşit aralıklı kabul edilir (X düzeni: ilk kol öne-sağa).
  const motorlar = [];
  for (let i = 0; i < n; i++) {
    const aci = motorAcisi(i, n);
    motorlar.push([R * Math.cos(aci), R * Math.sin(aci)]);
  }
  for (const [x, y] of motorlar) {
    svg.append(svgOge("line", { x1: 0, y1: 0, x2: x, y2: y, stroke: "#3a4a66", "stroke-width": R * 0.07, "stroke-linecap": "round" }));
  }
  for (const [x, y] of motorlar) {
    if (sinirR) {
      svg.append(svgOge("circle", {
        cx: x, cy: y, r: sinirR, fill: "none", stroke: "var(--soluk-yazi)", opacity: 0.6,
        "stroke-dasharray": `${yazi * 0.3} ${yazi * 0.3}`, "stroke-width": yazi * 0.06,
      }));
    }
    if (pervaneR) {
      svg.append(svgIpucu(svgOge("circle", {
        cx: x, cy: y, r: pervaneR, class: `durum-${durum} dolgu-${durum}`, "fill-opacity": 0.14, "stroke-width": yazi * 0.1,
      }), k5 ? `${k5.kod} ${k5.baslik}: ${k5.aciklama}` : "Pervane"));
    }
    svg.append(svgOge("circle", { cx: x, cy: y, r: R * 0.06, fill: "var(--yazi)" }));
  }
  svg.append(svgOge("rect", {
    x: -R * 0.16, y: -R * 0.22, width: R * 0.32, height: R * 0.44, rx: R * 0.05, fill: "var(--vurgu)", opacity: 0.85,
  }));
  svg.append(svgOge("path", {
    d: `M 0 ${-R * 0.34} l ${-R * 0.06} ${R * 0.08} h ${R * 0.12} z`, fill: "var(--vurgu-acik)",
  }, svgOge("title", {}, "Ön")));

  const satirlar = [
    `Dış ölçü ${sayiBicimle(g.en_mm, GORUNUM_MM_BASAMAK)} × ${sayiBicimle(g.boy_mm, GORUNUM_MM_BASAMAK)} mm · ` +
      `dingil ≈ ${sayiBicimle(g.dingil_mm, GORUNUM_MM_BASAMAK)} mm`,
    (g.en_buyuk_pervane_inc ? `Sığabilecek en büyük pervane ≈ ${sayiBicimle(g.en_buyuk_pervane_inc, GORUNUM_INC_BASAMAK)} inç` : "Şasi pervane için çok küçük görünüyor") +
      (pervaneInc ? ` · takılı ${sayiBicimle(pervaneInc, GORUNUM_INC_BASAMAK)} inç` : " · pervane eklenmedi"),
  ];
  satirlar.forEach((s, i) => svg.append(svgOge("text", {
    x: 0, y: yari + yazi * (1.2 + i * 1.3), "text-anchor": "middle", style: `font-size:${yazi}px`,
  }, s)));
  kap.replaceChildren(svg);
}

// ---------- Uçuş göstergeleri ----------

// Hedef çizgili yatay çubuk. iyi: true/false/null (renk), hedef yoksa çizgi çizilmez.
function cubukGosterge(baslik, h, birim, basamak, hedef, aciklamaEk = "") {
  const kap = document.createElement("div");
  const b = document.createElement("div");
  b.className = "ozet-etiket";
  b.textContent = baslik;
  kap.append(b);
  if (h.deger == null) {
    kap.append(ogeOlustur("p", "soluk", hesaplanamadiMetni(h, true)));
    return kap;
  }
  const enFazla = Math.max(hedef ? hedef * 1.5 : 0, h.deger * 1.15, 1e-9);
  const iyi = hedef == null ? null : h.deger >= hedef;
  const sinif = iyi === null ? "dolgu-uygun" : iyi ? "dolgu-uygun" : "dolgu-uygunsuz";
  const G = 300;
  // Geniş ekranda yazı aşırı büyümesin diye çubuğun genişliği sınırlanır.
  const svg = svgOge("svg", { viewBox: `0 0 ${G} 74`, class: "gorsel", style: "max-width:420px" });
  svg.append(svgOge("text", { x: 0, y: 24, class: "koyu-metin", style: "font-size:22px" }, hesapMetni(h, birim, basamak)));
  svg.append(svgOge("rect", { x: 0, y: 36, width: G, height: 14, rx: 7, fill: "var(--giris-arka)", stroke: "var(--cizgi)" }));
  svg.append(svgOge("rect", { x: 0, y: 36, width: Math.max(4, (h.deger / enFazla) * G), height: 14, rx: 7, class: sinif }));
  if (hedef != null) {
    const x = (hedef / enFazla) * G;
    svg.append(svgOge("line", { x1: x, y1: 30, x2: x, y2: 56, stroke: "var(--yazi)", "stroke-width": 2 }));
    svg.append(svgOge("text", { x, y: 70, "text-anchor": "middle" }, `hedef ≥ ${sayiBicimle(hedef, basamak)}${birim}`));
  }
  kap.append(svgIpucu(svg, h.aciklama + aciklamaEk));
  return kap;
}

// Yarım daire gösterge (0–100 %), renkli bölgelerle.
function yayGosterge(baslik, h) {
  const kap = document.createElement("div");
  const b = document.createElement("div");
  b.className = "ozet-etiket";
  b.textContent = baslik;
  kap.append(b);
  if (h.deger == null) {
    kap.append(ogeOlustur("p", "soluk", hesaplanamadiMetni(h, true)));
    return kap;
  }
  const cx = 100, cy = 100, r = 80;
  const nokta = (yuzde) => {
    const a = Math.PI * (1 - yuzde / 100);
    return [cx + r * Math.cos(a), cy - r * Math.sin(a)];
  };
  const yay = (bas, son) => {
    const [x1, y1] = nokta(bas);
    const [x2, y2] = nokta(son);
    return `M ${x1} ${y1} A ${r} ${r} 0 0 1 ${x2} ${y2}`;
  };
  const svg = svgOge("svg", { viewBox: "0 0 200 125", class: "gorsel", style: "max-width:260px" });
  let bas = 0;
  for (const bolge of GAZ_BOLGELERI) {
    svg.append(svgOge("path", { d: yay(bas, bolge.bitis), class: bolge.sinif.replace("dolgu", "durum"), "stroke-width": 14, fill: "none", opacity: 0.35 }));
    bas = bolge.bitis;
  }
  const deger = Math.min(100, Math.max(0, h.deger));
  const [ix, iy] = nokta(deger);
  svg.append(svgOge("line", { x1: cx, y1: cy, x2: ix, y2: iy, stroke: "var(--yazi)", "stroke-width": 3, "stroke-linecap": "round" }));
  svg.append(svgOge("circle", { cx, cy, r: 6, fill: "var(--yazi)" }));
  svg.append(svgOge("text", { x: cx, y: 122, "text-anchor": "middle", class: "koyu-metin", style: "font-size:18px" },
    `%${hesapMetni(h, "", YUZDE_BASAMAK)}`));
  kap.append(svgIpucu(svg, `${h.aciklama}. Yeşil: rahat (≤%50), sarı: yüklü, kırmızı: motorlar zorlanır.`));
  return kap;
}

function ucusGostergeleriniCiz() {
  const u = elektronikOzeti.ucus;
  $("ucus-gostergeleri").replaceChildren(
    cubukGosterge("İtki / ağırlık", u.itki_agirlik_orani, "", ORAN_BASAMAK, u.hedef_itki_agirlik, ` · ${hedefKaynagiMetni(u)}`),
    cubukGosterge("Uçuş süresi", u.ucus_suresi_dk, " dk", SURE_BASAMAK, u.hedef_ucus_suresi_dk),
    yayGosterge("Asılı kalma gazı", u.asili_gaz_yuzde),
  );
}

// ---------- Ağırlık dağılımı ----------

function agirlikDagiliminiCiz() {
  const o = elektronikOzeti;
  const a = o.agirlik;
  const gruplar = new Map();
  if (a.sasi_g) gruplar.set("Şasi", a.sasi_g);
  for (const { bag, parca } of o.kalemler) {
    if (parca.agirlik_g == null) continue;
    const ad = parca.alt_tur_adi || parca.tur_adi;
    gruplar.set(ad, (gruplar.get(ad) || 0) + parca.agirlik_g * bag.adet);
  }
  if (a.kablo_payi_g) gruplar.set("Kablo/vida payı", a.kablo_payi_g);
  if (a.yuk_g) gruplar.set("Yük", a.yuk_g);
  const kap = $("agirlik-dagilimi");
  const toplam = [...gruplar.values()].reduce((x, y) => x + y, 0);
  if (!toplam) {
    bosMesaj(kap, "Şasi ve parça ağırlıkları girilince dağılım burada görünür.");
    return;
  }
  const G = 600;
  const svg = svgOge("svg", { viewBox: `0 0 ${G} 30`, class: "gorsel" });
  const lejant = document.createElement("div");
  lejant.className = "lejant";
  let x = 0;
  [...gruplar.entries()].forEach(([ad, g], i) => {
    const renk = AGIRLIK_RENKLERI[i % AGIRLIK_RENKLERI.length];
    const w = (g / toplam) * G;
    const yuzde = sayiBicimle((g / toplam) * 100, YUZDE_BASAMAK);
    svg.append(svgIpucu(svgOge("rect", { x, y: 0, width: Math.max(w - 1.5, 0.5), height: 30, rx: 3, fill: renk }), `${ad}: ${sayiBicimle(g, AGIRLIK_BASAMAK)} g (%${yuzde})`));
    x += w;
    const s = document.createElement("span");
    s.style.setProperty("--renk", renk);
    s.textContent = `${ad} ${sayiBicimle(g, LEJANT_AGIRLIK_BASAMAK)} g (%${yuzde})`;
    lejant.append(s);
  });
  const not = document.createElement("p");
  not.className = "soluk";
  not.textContent = `Toplam ${sayiBicimle(toplam, AGIRLIK_BASAMAK)} g` +
    (a.agirligi_eksik_parcalar.length ? ` · ağırlığı girilmemiş: ${a.agirligi_eksik_parcalar.join(", ")}` : "");
  kap.replaceChildren(svg, lejant, not);
}

// ---------- Uyum bağlantı şeması ----------

// DEĞİŞTİRİLEBİLİR: Şemadaki kutuların yerleri (viewBox 760 × 320).
const SEMA_DUGUMLERI = {
  pil: { x: 70, y: 180, ad: "Pil", tur: "pil" },
  pdb: { x: 220, y: 180, ad: "PDB", tur: "guc_dagitim" },
  esc: { x: 380, y: 180, ad: "ESC", tur: "esc" },
  motor: { x: 540, y: 180, ad: "Motor", tur: "motor" },
  pervane: { x: 690, y: 180, ad: "Pervane", tur: "pervane" },
  fc: { x: 380, y: 60, ad: "Uçuş kartı", tur: "ucus_karti" },
  alici: { x: 560, y: 60, ad: "Alıcı", tur: "alici" },
  diger: { x: 200, y: 60, ad: "Kamera / VTX / GPS", tur: "diger" },
  sasi: { x: 690, y: 285, ad: "Şasi", tur: null },
};
const DUGUM_EN = 128;
const DUGUM_BOY = 46;

function kisalt(metin, uzunluk = 18) {
  return metin.length > uzunluk ? metin.slice(0, uzunluk - 1) + "…" : metin;
}

function uyumSemasiniCiz() {
  const o = elektronikOzeti;
  const parcalar = (tur) => o.kalemler.filter((k) => k.parca.tur === tur).map((k) => k.parca);
  const pdbVar = parcalar("guc_dagitim").length > 0;

  const kenarlar = [
    pdbVar ? ["pil", "pdb", ["K3", "K12"]] : ["pil", "esc", ["K2", "K12"]],
    pdbVar ? ["pdb", "esc", ["K2"]] : null,
    ["esc", "motor", ["K6"]],
    ["motor", "pervane", ["K4"]],
    ["pervane", "sasi", ["K5"]],
    ["fc", "esc", ["K8", "K9"]],
    ["alici", "fc", ["K10"]],
    ["fc", "diger", ["K13"]],
    ["pil", "fc", ["K3"], "yukari"],
    ["pil", "motor", ["K1"], "asagi"],
  ].filter(Boolean);
  const dugumKontrolleri = { pil: ["K7"], motor: ["K11"] };

  const svg = svgOge("svg", { viewBox: "0 0 760 320", class: "gorsel" });
  for (const [a, b, kodlar, egri] of kenarlar) {
    const A = SEMA_DUGUMLERI[a], B = SEMA_DUGUMLERI[b];
    const sonuclar = kodlar.map(uyumSonucu).filter(Boolean);
    const durum = enKotuDurum(sonuclar.map((s) => s.durum));
    let d, lx, ly;
    if (egri === "yukari") {
      // Üst sıradaki kutuların altından geçip uçuş kartının sol alt köşesine bağlanır.
      const [hx, hy] = [B.x - DUGUM_EN / 2 + 12, B.y + DUGUM_BOY / 2];
      d = `M ${A.x} ${A.y - DUGUM_BOY / 2} C ${A.x} ${A.y - 70}, ${hx - 60} ${hy + 40}, ${hx} ${hy}`;
      [lx, ly] = [(A.x + hx) / 2 + 10, A.y - 58];
    } else if (egri === "asagi") {
      d = `M ${A.x} ${A.y + DUGUM_BOY / 2} C ${A.x} ${A.y + 110}, ${B.x} ${B.y + 110}, ${B.x} ${B.y + DUGUM_BOY / 2}`;
      [lx, ly] = [(A.x + B.x) / 2, A.y + 92];
    } else {
      d = `M ${A.x} ${A.y} L ${B.x} ${B.y}`;
      [lx, ly] = [(A.x + B.x) / 2, (A.y + B.y) / 2 - 8];
    }
    const ipucu = sonuclar.map((s) => `${s.kod} ${s.baslik}: ${s.aciklama}`).join("\n") || "Kontrol sonucu yok";
    const grup = svgIpucu(svgOge("g", {}, svgOge("path", { d, class: `sema-kenar durum-${durum}` })), ipucu);
    grup.append(svgOge("text", {
      x: lx, y: ly, "text-anchor": "middle",
      style: "font-size:11px; paint-order:stroke; stroke:var(--kart); stroke-width:4px",
    }, kodlar.join("·")));
    svg.append(grup);
  }

  for (const [anahtar, dugum] of Object.entries(SEMA_DUGUMLERI)) {
    if (anahtar === "pdb" && !pdbVar) continue; // PDB yoksa pil doğrudan ESC'ye bağlanır
    const liste = dugum.tur === null ? (o.sasi_olculeri_var || o.agirlik.sasi_g ? [{ gorunen_ad: "eklendi" }] : []) : parcalar(dugum.tur);
    const bos = liste.length === 0;
    const ikinci = bos ? "eklenmedi" : liste.length > 1 && dugum.tur === "diger"
      ? liste.map((p) => p.alt_tur_adi).join(", ") : liste[0].gorunen_ad;
    const g = svgOge("g", { class: "sema-dugum" + (bos ? " bos" : "") });
    g.append(svgOge("rect", {
      x: dugum.x - DUGUM_EN / 2, y: dugum.y - DUGUM_BOY / 2, width: DUGUM_EN, height: DUGUM_BOY, rx: 9,
      stroke: bos ? "#5b6678" : "var(--vurgu)",
    }));
    g.append(svgOge("text", { x: dugum.x, y: dugum.y - 4, "text-anchor": "middle", class: "koyu-metin" }, dugum.ad));
    g.append(svgOge("text", { x: dugum.x, y: dugum.y + 13, "text-anchor": "middle", style: "font-size:11px" }, kisalt(ikinci)));
    for (const kod of dugumKontrolleri[anahtar] || []) {
      const s = uyumSonucu(kod);
      if (!s) continue;
      g.append(svgIpucu(svgOge("circle", {
        cx: dugum.x + DUGUM_EN / 2 - 4, cy: dugum.y - DUGUM_BOY / 2 + 4, r: 8, class: `dolgu-${s.durum}`,
      }), `${s.kod} ${s.baslik}: ${s.aciklama}`));
    }
    svg.append(svgIpucu(g, liste.map((p) => p.gorunen_ad).join("\n") || `${dugum.ad} eklenmedi`));
  }
  $("uyum-semasi").replaceChildren(svg);
}
