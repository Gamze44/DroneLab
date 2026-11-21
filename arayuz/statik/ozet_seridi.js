// Drone sayfasının üstündeki özet şeridi (ağırlık, itki/ağırlık, uçuş süresi, maliyet,
// uyum) ve sol menüdeki adım durumları. Elektronik özeti her yenilendiğinde ve fiyat
// ya da şartname değiştiğinde ustOzetiYenile() çağrılır.
"use strict";

// DEĞİŞTİRİLEBİLİR: Özet şeridindeki ondalık basamaklar. Şerit dar olduğu için sekmelerdekinden az olabilir;
// adlar elektronik.js / maliyet.js'teki sabitlerle çakışmasın diye OZET_ ile başlar (sayfada tek ortak kapsam var).
const OZET_AGIRLIK_BASAMAK = 0;
const OZET_ORAN_BASAMAK = 1;
const OZET_SURE_BASAMAK = 1;
const OZET_TL_BASAMAK = 0;

let ozetIstegiSirasi = 0; // üst üste gelen yenilemelerde yalnızca en sonuncusu ekrana yazılsın

function ozetKutusu(kimlik, deger, alt, durum) {
  const kutu = $(kimlik);
  kutu.classList.remove("iyi", "kotu", "dikkat");
  if (durum) kutu.classList.add(durum);
  kutu.querySelector(".ozet-deger").textContent = deger;
  kutu.querySelector(".ozet-alt").textContent = alt;
}

function adimDurumu(adim, metin, sinif) {
  const e = $(`durum-${adim}`);
  e.className = `adim-durum ${sinif || ""}`;
  e.textContent = metin;
}

function sayac(liste, durum) {
  return liste.filter((x) => x.durum === durum).length;
}

async function ustOzetiYenile() {
  if (!elektronikOzeti || !droneKimligi) return;
  const sira = ++ozetIstegiSirasi;
  // Maliyet veya şartname alınamazsa özetin geri kalanı yine gösterilir.
  const [maliyet, sartname] = await Promise.all([
    istekGonder(`/api/dronelar/${droneKimligi}/maliyet`).catch(() => null),
    istekGonder(`/api/dronelar/${droneKimligi}/sartname`).catch(() => null),
  ]);
  if (sira !== ozetIstegiSirasi) return;
  ozetiYaz(elektronikOzeti, maliyet, sartname);
}

function ozetiYaz(o, m, s) {
  const a = o.agirlik;
  const u = o.ucus;

  // Ağırlık
  ozetKutusu("oz-agirlik", a.toplam_g > 0 ? `${sayiBicimle(a.toplam_g, OZET_AGIRLIK_BASAMAK)} g` : "–",
    a.toplam_g <= 0 ? "ağırlık girilmedi" : a.eksiksiz_mi ? "tahmini (kablo payı dahil)" : "eksik: bazı ağırlıklar yok",
    a.toplam_g > 0 && !a.eksiksiz_mi ? "dikkat" : null);

  // İtki / ağırlık
  const oran = u.itki_agirlik_orani;
  ozetKutusu("oz-oran", oran.deger != null ? sayiBicimle(oran.deger, OZET_ORAN_BASAMAK) : "–",
    oran.deger != null ? `hedef ≥ ${sayiBicimle(u.hedef_itki_agirlik, OZET_ORAN_BASAMAK)}${oran.tahmini ? " · tahmini" : ""}` : "hesaplanamadı",
    u.hedefe_ulasiyor_mu === null ? null : u.hedefe_ulasiyor_mu ? "iyi" : "kotu");

  // Uçuş süresi
  const sure = u.ucus_suresi_dk;
  const sureDurum = u.ucus_suresi_hedefe_ulasiyor_mu;
  ozetKutusu("oz-sure", sure.deger != null ? `${sayiBicimle(sure.deger, OZET_SURE_BASAMAK)} dk` : "–",
    sure.deger == null ? "hesaplanamadı"
      : u.hedef_ucus_suresi_dk != null ? `hedef ≥ ${sayiBicimle(u.hedef_ucus_suresi_dk, OZET_SURE_BASAMAK)} dk · tahmini` : "tahmini",
    sureDurum === null ? null : sureDurum ? "iyi" : "kotu");

  // Maliyet
  if (m) {
    const alinacak = m.toplamlar.alinacak;
    const eksik = m.toplamlar.toplam.eksik_kalem_sayisi;
    let alt = `toplam değer ${sayiBicimle(m.toplamlar.toplam.tl, OZET_TL_BASAMAK)} TL`;
    if (eksik) alt += ` · ${eksik} fiyat eksik`;
    let durum = null;
    let deger = `${sayiBicimle(alinacak.tl, OZET_TL_BASAMAK)} TL`;
    if (m.butce_tl != null) {
      deger += ` / ${sayiBicimle(m.butce_tl, OZET_TL_BASAMAK)}`;
      // Fiyatı eksik kalem varken "bütçede" demek yanıltır; yalnızca aşım kesin olarak gösterilir.
      durum = m.butce_kalan_tl < 0 ? "kotu" : eksik ? null : "iyi";
    }
    ozetKutusu("oz-maliyet", deger, `alınacaklar · ${alt}`, durum);
  }

  // Uyum (+ şartname)
  const uyumsuz = sayac(o.uyum, "uygunsuz");
  const dikkat = sayac(o.uyum, "uyari");
  const bilinmeyen = sayac(o.uyum, "bilinmiyor");
  let uyumDeger = "✓ uygun";
  let uyumDurum = "iyi";
  if (uyumsuz) [uyumDeger, uyumDurum] = [`${uyumsuz} ✗ uyumsuz`, "kotu"];
  else if (dikkat) [uyumDeger, uyumDurum] = [`${dikkat} ⚠ dikkat`, "dikkat"];
  else if (bilinmeyen) [uyumDeger, uyumDurum] = [`${bilinmeyen} ? eksik veri`, null];
  const sartnameUyumsuz = s && s.sartname ? sayac(s.rapor, "uygunsuz") : 0;
  const uyumAlt = s && s.sartname
    ? (sartnameUyumsuz ? `şartname: ${sartnameUyumsuz} madde uymuyor` : "şartname: uymayan madde yok")
    : `${o.uyum.length} kontrol`;
  if (sartnameUyumsuz && uyumDurum !== "kotu") uyumDurum = "kotu";
  ozetKutusu("oz-uyum", uyumDeger, uyumAlt, uyumDurum);

  adimDurumlariniYaz(o, m, s);
}

function adimDurumlariniYaz(o, m, s) {
  adimDurumu("sasi", o.agirlik.sasi_g != null ? "✓" : "ağırlık yok", o.agirlik.sasi_g != null ? "tamam" : "dikkat");

  const eksikParca = sayac(o.zorunluluklar, "eksik");
  adimDurumu("elektronik", eksikParca ? `${eksikParca} eksik` : "✓", eksikParca ? "sorun" : "tamam");

  const h = o.hedefler;
  const hedefVar = h.ucus_suresi_dk != null || h.yuk_g != null || h.butce_tl != null;
  adimDurumu("hedefler", hedefVar ? "✓" : "", "tamam");

  const uyumsuz = sayac(o.uyum, "uygunsuz");
  const dikkat = sayac(o.uyum, "uyari");
  if (uyumsuz) adimDurumu("uyum", `${uyumsuz} ✗`, "sorun");
  else if (dikkat) adimDurumu("uyum", `${dikkat} ⚠`, "dikkat");
  else if (sayac(o.uyum, "bilinmiyor")) adimDurumu("uyum", "?", "notr");
  else adimDurumu("uyum", "✓", "tamam");

  const u = o.ucus;
  if (u.itki_agirlik_orani.deger == null) adimDurumu("ucus", "?", "notr");
  else if (u.hedefe_ulasiyor_mu === false || u.ucus_suresi_hedefe_ulasiyor_mu === false) adimDurumu("ucus", "hedef altı", "sorun");
  else adimDurumu("ucus", "✓", "tamam");

  if (!m) adimDurumu("maliyet", "", "");
  else if (m.butce_tl != null && m.butce_kalan_tl < 0) adimDurumu("maliyet", "bütçe aşıldı", "sorun");
  else if (m.toplamlar.toplam.eksik_kalem_sayisi) adimDurumu("maliyet", `${m.toplamlar.toplam.eksik_kalem_sayisi} fiyat yok`, "notr");
  else adimDurumu("maliyet", "✓", "tamam");

  if (!s || !s.sartname) adimDurumu("sartname", "", "");
  else if (sayac(s.rapor, "uygunsuz")) adimDurumu("sartname", `${sayac(s.rapor, "uygunsuz")} ✗`, "sorun");
  else if (sayac(s.rapor, "onay_bekliyor") || s.rapor.length === 0) adimDurumu("sartname", "onay bekliyor", "dikkat");
  else adimDurumu("sartname", "✓", "tamam");
}
