// Elektronik sekmesindeki "Öner" paneli: Gemini'den aday ister, programın uyum
// değerlendirmesiyle gösterir, seçilen adayı "önerilen" olarak ekler.
// elektronik.js'ten sonra yüklenir (turTanimlari, elektronikOzeti, elektronikOzetiniYenile oradadır).
"use strict";

const GOOGLE_ARAMA_ADRESI = "https://www.google.com/search?q=";

let oneriSonuclari = [];

$("oneri-ac-dugmesi").addEventListener("click", oneriPaneliniAc);
$("oneri-kapat").addEventListener("click", () => goster("oneri-karti", false));
$("oneri-iste").addEventListener("click", oneriIste);
$("oneri-tur").addEventListener("change", () => goster("oneri-alt-tur", $("oneri-tur").value === "diger"));

function oneriPaneliniAc() {
  seceneklereYaz("oneri-tur", turTanimlari.turler);
  seceneklereYaz("oneri-alt-tur", turTanimlari.alt_turler);
  // Drone'da henüz olmayan ilk türü seç; kullanıcı en çok eksik parçayı merak eder.
  // Türler sunucudan önem sırasıyla gelir (motor, pervane, esc, …); sıra orada değiştirilir.
  const turler = turTanimlari.turler.map((t) => t.deger);
  const mevcut = new Set(elektronikOzeti.kalemler.map((k) => k.parca.tur));
  $("oneri-tur").value = turler.find((t) => !mevcut.has(t)) || turler[0];
  goster("oneri-alt-tur", $("oneri-tur").value === "diger");
  goster("oneri-karti", true);
  $("oneri-karti").scrollIntoView({ behavior: "smooth", block: "start" });
}

async function oneriIste() {
  goster("oneri-hatasi", false);
  $("oneri-adaylari").replaceChildren();
  $("oneri-iste").disabled = true;
  $("oneri-durumu").textContent = "Gemini düşünüyor… (10–60 saniye sürebilir)";
  const tur = $("oneri-tur").value;
  try {
    const sonuc = await istekGonder(
      `/api/dronelar/${droneKimligi}/oneriler`,
      jsonIstegi("POST", { tur, alt_tur: tur === "diger" ? $("oneri-alt-tur").value : null })
    );
    oneriSonuclari = sonuc.adaylar;
    const atlanan = sonuc.atlanan ? ` · ${sonuc.atlanan} aday kullanılamadı (adı eksik ya da zaten drone'da)` : "";
    $("oneri-durumu").textContent =
      `${sonuc.adaylar.length} aday · bugün ${sonuc.bugun_kullanilan}/${sonuc.gunluk_sinir} öneri · ${sonuc.model}${atlanan}`;
    adaylariCiz();
  } catch (veri) {
    $("oneri-durumu").textContent = "";
    hataGoster("oneri-hatasi", veri);
  } finally {
    $("oneri-iste").disabled = false;
  }
}

function adaylariCiz() {
  const kap = $("oneri-adaylari");
  kap.replaceChildren();
  if (oneriSonuclari.length === 0) {
    bosMesaj(kap, "Kullanılabilir aday gelmedi. Tekrar deneyin veya parçayı elle ekleyin.");
    return;
  }
  oneriSonuclari.forEach((aday, sira) => kap.append(adayKarti(aday, sira)));
}

function teknikOzeti(parca) {
  const alanlar = turTanimi(parca.tur).alanlar;
  return alanlar
    .filter((a) => parca.teknik[a.ad] !== null && parca.teknik[a.ad] !== undefined)
    .map((a) => {
      let d = parca.teknik[a.ad];
      if (Array.isArray(d)) d = d.join(", ");
      else if (typeof d === "boolean") d = d ? "evet" : "hayır";
      return `${a.etiket}: ${d}`;
    })
    .join(" · ");
}

function adayKarti(aday, sira) {
  const p = aday.parca;
  const kart = ogeOlustur("div", "aday-karti");

  const baslik = ogeOlustur("div", "liste-baslik", `${sira + 1}. ${p.gorunen_ad}`);
  baslik.append(aday.katalog_kimlik ? ogeOlustur("span", "etiket dosya", "katalogda var") : ogeOlustur("span", "etiket uyari", "doğrulanmadı"));
  const uyumsuz = aday.uyum.filter((u) => u.durum === "uygunsuz").length;
  if (uyumsuz) baslik.append(ogeOlustur("span", "etiket hata", `${uyumsuz} uyumsuzluk`));
  kart.append(baslik);

  const agirlik = p.agirlik_g != null ? `${sayiBicimle(p.agirlik_g, AGIRLIK_BASAMAK)} g × ${aday.adet}` : "ağırlık bilinmiyor";
  kart.append(ogeOlustur("div", "soluk", agirlik));
  if (aday.gerekce) kart.append(ogeOlustur("p", "", aday.gerekce));
  const teknik = teknikOzeti(p);
  if (teknik) kart.append(ogeOlustur("div", "soluk", teknik));
  if (aday.silinen_alanlar.length) {
    kart.append(ogeOlustur("div", "soluk", `Geçersiz geldiği için boş bırakılan değerler: ${aday.silinen_alanlar.join(", ")}`));
  }

  // Programın değerlendirmesi
  const hesap = [];
  if (aday.itki_agirlik) hesap.push(`itki/ağırlık: ${hesapMetni(aday.itki_agirlik, "", ORAN_BASAMAK)}`);
  if (aday.ucus_suresi_dk) hesap.push(`uçuş süresi: ${hesapMetni(aday.ucus_suresi_dk, " dk", SURE_BASAMAK)}`);
  if (hesap.length) kart.append(ogeOlustur("div", "soluk", `Bu parçayla ${hesap.join(" · ")}`));
  const sirali = [...aday.uyum].sort((a, b) => UYUM_DURUM_SIRASI.indexOf(a.durum) - UYUM_DURUM_SIRASI.indexOf(b.durum));
  for (const u of sirali) {
    const satir = ogeOlustur("div", `uyum-satiri uyum-${u.durum}`);
    const metin = ogeOlustur("div", "soluk", `${u.kod} · ${u.baslik}: ${u.aciklama}`);
    metin.style.whiteSpace = "pre-line";
    satir.append(ogeOlustur("span", "uyum-isareti", UYUM_ISARETLERI[u.durum]), metin);
    kart.append(satir);
  }

  for (const ihlal of aday.sartname_ihlalleri || []) {
    const satir = ogeOlustur("div", "uyum-satiri uyum-uygunsuz");
    const yer = ihlal.madde_no ? `Şartname madde ${ihlal.madde_no}` : "Şartname";
    satir.append(ogeOlustur("span", "uyum-isareti", "✗"), ogeOlustur("div", "soluk", `${yer}: ${ihlal.aciklama}`));
    kart.append(satir);
  }
  if ((aday.sartname_ihlalleri || []).length) baslik.append(ogeOlustur("span", "etiket hata", "şartnameye uymuyor"));

  const dugmeler = ogeOlustur("div", "satir");
  dugmeler.style.marginTop = "8px";
  const sec = ogeOlustur("button", "", `Bunu seç (${aday.adet} adet, önerilen)`);
  sec.type = "button";
  sec.addEventListener("click", () => adayiSec(aday, sec));
  const ara = ogeOlustur("a", "kaynak", "Google'da ara (fiyat ve özellikleri kontrol et)");
  ara.href = GOOGLE_ARAMA_ADRESI + encodeURIComponent(`${p.uretici} ${p.model}`);
  ara.target = "_blank";
  ara.rel = "noopener noreferrer";
  dugmeler.append(sec, ara);
  kart.append(dugmeler);
  return kart;
}

async function adayiSec(aday, dugme) {
  goster("oneri-hatasi", false);
  dugme.disabled = true;
  const p = aday.parca;
  const adres = `/api/dronelar/${droneKimligi}/oneriler/sec`;
  const govde = aday.katalog_kimlik
    ? { parca_kimlik: aday.katalog_kimlik, adet: aday.adet }
    : {
        adet: aday.adet,
        parca: { tur: p.tur, alt_tur: p.alt_tur, uretici: p.uretici, model: p.model, agirlik_g: p.agirlik_g, notlar: p.notlar, teknik: p.teknik },
      };
  try {
    try {
      await istekGonder(adres, jsonIstegi("POST", govde));
    } catch (veri) {
      // Bu arada aynı parça kataloğa eklendiyse katalogdaki kayıt kullanılır.
      if (!veri || !veri.mevcut_kimlik || govde.parca_kimlik) throw veri;
      await istekGonder(adres, jsonIstegi("POST", { parca_kimlik: veri.mevcut_kimlik, adet: aday.adet }));
    }
    dugme.textContent = "Eklendi ✓";
    await elektronikOzetiniYenile();
  } catch (veri) {
    dugme.disabled = false;
    hataGoster("oneri-hatasi", veri);
  }
}
