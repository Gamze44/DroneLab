// Drone sayfasındaki maliyet bölümü: şasi ve parça fiyatlarının elle girilmesi,
// TL toplamları (tüm drone / alınacaklar / elimdekiler) ve kur bilgisi.
// drone.js'ten önce yüklenir; droneKimligi drone.js'te tanımlıdır.
"use strict";

const TL_BASAMAK = 2;
const KUR_BASAMAK = 4;
const TL_KODU = "TRY";

let paraBirimleri = null;

function tlYaz(deger) {
  return `${sayiBicimle(deger, TL_BASAMAK)} TL`;
}

async function maliyetiYenile(kurlariYenile = false) {
  if (!droneKimligi) return;
  goster("maliyet-hatasi", false);
  try {
    paraBirimleri ||= await istekGonder("/api/para-birimleri");
    const m = await istekGonder(`/api/dronelar/${droneKimligi}/maliyet${kurlariYenile ? "?yenile=true" : ""}`);
    toplamlariCiz(m);
    kalemleriCiz(m);
  } catch (veri) {
    hataGoster("maliyet-hatasi", veri);
  }
}

$("kurlari-yenile").addEventListener("click", () => maliyetiYenile(true));

function toplamMetni(t) {
  let metin = tlYaz(t.tl) + (t.tahmini ? " (tahmini)" : "");
  if (t.eksik_kalem_sayisi) metin += ` – ${t.eksik_kalem_sayisi} kalemin fiyatı eksik`;
  return metin;
}

function toplamlariCiz(m) {
  const t = m.toplamlar;
  const satirlar = [
    ["Alınacaklar (planlanan + önerilen)", toplamMetni(t.alinacak)],
    ["Elimdekiler", toplamMetni(t.elimde)],
    ["Dronun toplam değeri", toplamMetni(t.toplam)],
  ];
  if (m.butce_tl != null) {
    const kalan = m.butce_kalan_tl;
    const durum = kalan >= 0 ? `✓ ${tlYaz(kalan)} kalıyor` : `✗ ${tlYaz(-kalan)} aşılıyor`;
    const eksik = t.alinacak.eksik_kalem_sayisi ? " (fiyatı eksik kalemler hariç)" : "";
    satirlar.unshift(["Bütçe (Hedefler sekmesinden)", `${tlYaz(m.butce_tl)} – ${durum}${eksik}`]);
  }
  tabloDoldur("maliyet-toplamlari", satirlar);

  const kurlar = m.kurlar.map((k) => `1 ${k.para_birimi} = ${sayiBicimle(k.tl_karsiligi, KUR_BASAMAK)} TL`);
  const tarih = m.kurlar.length ? ` (TCMB döviz satış, ${m.kurlar[0].kur_tarihi})` : "";
  $("kur-bilgisi").textContent = kurlar.length ? `Kullanılan kurlar: ${kurlar.join(" · ")}${tarih}` : "";

  const uyarilar = [];
  if (m.kur_notu) uyarilar.push(m.kur_notu);
  for (const k of m.kalemler) if (k.eksik && k.eksik !== "fiyat girilmemiş") uyarilar.push(`${k.ad}: ${k.eksik}`);
  const eksikFiyat = m.kalemler.filter((k) => k.eksik === "fiyat girilmemiş").map((k) => k.ad);
  if (eksikFiyat.length) uyarilar.push(`Fiyatı girilmemiş (toplama katılmadı): ${eksikFiyat.join(", ")}`);
  listeKutusu("maliyet-uyarisi", "Toplamlar eksik olabilir:", uyarilar);
}

function paraSecici(secili) {
  const s = document.createElement("select");
  for (const { deger, ad } of paraBirimleri) s.append(new Option(deger === TL_KODU ? "TL" : deger, deger));
  s.value = secili || TL_KODU;
  s.title = "Para birimi";
  return s;
}

function hucre(icerik) {
  const td = document.createElement("td");
  if (typeof icerik === "string") td.textContent = icerik;
  else if (icerik) td.append(...[].concat(icerik));
  return td;
}

function kalemleriCiz(m) {
  const govde = $("maliyet-kalemleri");
  govde.replaceChildren();
  for (const k of m.kalemler) {
    const tr = document.createElement("tr");

    const tutar = document.createElement("input");
    tutar.type = "number";
    tutar.min = "0";
    tutar.step = "any";
    tutar.className = "fiyat-girdisi";
    tutar.placeholder = "fiyat";
    if (k.tutar != null) tutar.value = k.tutar;
    const para = paraSecici(k.para_birimi);
    const fiyatKaydet = () => fiyatiKaydet(k, tutar.value.trim(), para.value, k.tip === "sasi" ? elimdeKutusu.checked : null);

    let durum;
    let elimdeKutusu = null;
    if (k.tip === "sasi") {
      elimdeKutusu = document.createElement("input");
      elimdeKutusu.type = "checkbox";
      elimdeKutusu.checked = m.sasi_elimde;
      elimdeKutusu.id = "sasi-elimde";
      const etiket = document.createElement("label");
      etiket.htmlFor = "sasi-elimde";
      etiket.textContent = " elimde";
      elimdeKutusu.addEventListener("change", fiyatKaydet);
      durum = [elimdeKutusu, etiket];
    } else {
      durum = k.durum_adi;
    }
    tutar.addEventListener("change", fiyatKaydet);
    para.addEventListener("change", fiyatKaydet);

    let tlMetni = "–";
    if (k.tl_tutar != null) tlMetni = sayiBicimle(k.tl_tutar, TL_BASAMAK) + (k.tahmini ? " (tahmini)" : "");
    else if (k.eksik && k.tutar != null) tlMetni = k.eksik;

    tr.append(hucre(k.ad), hucre(durum), hucre(String(k.adet)), hucre([tutar, para]), hucre(tlMetni));
    if (k.elimde) tr.className = "soluk";
    govde.append(tr);
  }
}

async function fiyatiKaydet(kalem, hamTutar, paraBirimi, sasiElimde) {
  goster("maliyet-hatasi", false);
  const tutar = hamTutar === "" ? null : Number(hamTutar.replace(",", "."));
  if (tutar !== null && Number.isNaN(tutar)) {
    hataGoster("maliyet-hatasi", { hata: "Fiyatı sayı olarak yazın (ör. 1250 veya 12,5)." });
    return;
  }
  try {
    if (kalem.tip === "sasi") {
      await istekGonder(`/api/dronelar/${droneKimligi}/sasi/fiyat`,
        jsonIstegi("PUT", { tutar, para_birimi: paraBirimi, elimde: sasiElimde }));
    } else {
      await istekGonder(`/api/katalog/${kalem.parca_kimlik}/fiyat`, jsonIstegi("PUT", { tutar, para_birimi: paraBirimi }));
    }
  } catch (veri) {
    hataGoster("maliyet-hatasi", veri);
    return;
  }
  await maliyetiYenile();
  ustOzetiYenile();
}
