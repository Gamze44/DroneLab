// Drone sayfasındaki şasi bölümü.
// Akış: dosya (veya parçalı şasi zip'i) yükle -> ham ölçüler ve birim önerisi -> birim onayı -> mm sonuçları.
// Zip'te parçaların görevi ve adedi onaylanır; dingil elle girilir ya da gövde ve koldan hesaplanıp onaylanır.
// Ağırlık elle girilir. Her adım sunucuda otomatik kaydedilir.
// Bu dosya drone.js'ten önce yüklenir; droneKimligi ve droneGuncellendi drone.js'te tanımlıdır.
"use strict";

// DEĞİŞTİRİLEBİLİR: Ekranda gösterilen ondalık basamak sayıları.
const OLCU_BASAMAK = 1;
const HACIM_BASAMAK = 1;
const DINGIL_BASAMAK = 0;

const BIRIM_ADLARI = { mm: "milimetre (mm)", cm: "santimetre (cm)", m: "metre (m)", inch: "inç (inch)" };
const TUR_ADLARI = { kati: "3B katı model", levha: "2B levha çizimi" };
// Dingilin nereden geldiği; [etiket metni, etiket sınıfı].
const DINGIL_KAYNAK_ETIKETLERI = {
  elle: ["elle girildi", "dosya"],
  hesap: ["parçalardan hesaplandı · tahmini", "uyari"],
  dis_olcu: ["dış ölçüden · tahmini", "uyari"],
  yok: ["girilmedi", "hata"],
};

let sonYukleme = null; // Sunucudan gelen son şasi okuma bilgisi
let sonDingilTahmini = null; // "Hesapla" ile gelen, henüz onaylanmamış dingil tahmini

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
    goster("dingil-karti", false);
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
    ["Tür", y.parcali ? `Parçalı şasi (zip, ${y.parcalar.length} parça)` : TUR_ADLARI[y.tur] || y.tur],
    ["Dosyadaki birim", y.dosya_birimi || "belirtilmemiş"],
  ];
  if (y.parcali) {
    satirlar.push(["Toplam üçgen sayısı", y.ucgen_sayisi.toLocaleString("tr-TR")]);
    satirlar.push(["Dosyadaki sayılar", "parçaların en büyük ölçüleri (birim önerisi için)"]);
  } else if (levhaMi) {
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
  parcalariDoldur(y);
}

// ---------- Parçalı şasi ----------

function parcalariDoldur(y) {
  goster("parcalar-karti", y.parcali);
  if (!y.parcali) return;
  const govde = $("parca-satirlari");
  govde.replaceChildren();
  for (const p of y.parcalar) {
    const levhaMi = p.tur === "levha";
    const kopya = p.ozdes_govde_sayisi > 1 && p.tek_govde_olculeri_ham
      ? `${p.ozdes_govde_sayisi} özdeş (biri ${olculeriYaz(p.tek_govde_olculeri_ham, "", levhaMi)})`
      : "1";
    const rol = seciciOlustur(y.parca_rolleri, p.rol);
    rol.dataset.alan = "rol";
    rol.setAttribute("aria-label", `${p.dosya_adi} görevi`);
    const adet = Object.assign(document.createElement("input"), {
      type: "number", min: "1", max: String(y.en_fazla_parca_adedi), step: "1", value: p.adet, className: "adet-girdisi",
    });
    adet.dataset.alan = "adet";
    adet.setAttribute("aria-label", `${p.dosya_adi} adedi`);
    const tr = document.createElement("tr");
    tr.dataset.sira = p.sira;
    tr.append(
      hucreOlustur(p.dosya_adi),
      hucreOlustur(olculeriYaz(p.olculer_ham, "", levhaMi)),
      hucreOlustur(kopya),
      hucreOlustur(rol),
      hucreOlustur(adet),
    );
    govde.append(tr);
  }
  $("parca-durumu").textContent = "";
}

$("parcalari-kaydet").addEventListener("click", async () => {
  const parcalar = [...$("parca-satirlari").children].map((tr) => ({
    sira: Number(tr.dataset.sira),
    rol: tr.querySelector("[data-alan=rol]").value,
    adet: Number(tr.querySelector("[data-alan=adet]").value),
  }));
  goster("parca-hatasi", false);
  $("parcalari-kaydet").disabled = true;
  try {
    const yanit = await istekGonder(`/api/dronelar/${droneKimligi}/sasi/parcalar`, jsonIstegi("PUT", { parcalar }));
    sonYukleme = yanit.yukleme;
    parcalariDoldur(yanit.yukleme);
    $("parca-durumu").textContent = "Kaydedildi.";
    if (yanit.olculer) {
      sonucuGoster(yanit.olculer);
      elektronikOzetiniYenile();
    }
  } catch (veri) {
    hataGoster("parca-hatasi", veri);
  } finally {
    $("parcalari-kaydet").disabled = false;
  }
});

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
  // Parçalı şaside parçalar montajlı olmadığı için en/boy ölçülmez, tahmin edilir.
  const tahmini = s.tahmini ? " (tahmini)" : "";
  const satirlar = [["Onaylanan birim", BIRIM_ADLARI[s.birim] || s.birim]];
  if (s.parcali_mi) satirlar.push(["Parça dosyası sayısı", String(s.parca_sayisi)]);
  satirlar.push(
    ["En (x)" + tahmini, sayiBicimle(s.en_mm, OLCU_BASAMAK) + " mm"],
    ["Boy (y)" + tahmini, sayiBicimle(s.boy_mm, OLCU_BASAMAK) + " mm"],
  );
  if (levhaMi) {
    satirlar.push(["Kalınlık", "ağırlık hesabı aşamasında girilecek"]);
    // Birim dönüşümü (mm² → cm², mm³ → cm³) sunucuda yapılır; burada yalnızca gösterilir.
    satirlar.push(["Net alan (delikler çıkarılmış)", sayiBicimle(s.alan_cm2, HACIM_BASAMAK) + " cm²"]);
  } else {
    satirlar.push(["Yükseklik (z)" + tahmini, sayiBicimle(s.yukseklik_mm, OLCU_BASAMAK) + " mm"]);
    satirlar.push([s.parcali_mi ? "Toplam hacim (adetlerle)" : "Hacim", sayiBicimle(s.hacim_cm3, HACIM_BASAMAK) + " cm³"]);
  }
  tabloDoldur("sonuc-bilgileri", satirlar);
  listeKutusu("sonuc-uyarilari", "Uyarılar:", s.uyarilar);
  goster("sonuc-karti", true);
  // Birim onaylandı; doğrulama kartı artık gerekmez (yeni dosya yüklenince yeniden açılır).
  goster("birim-karti", false);
  dingilKartiniDoldur(s);
}

// ---------- Dingil ----------

function dingilKartiniDoldur(s) {
  goster("dingil-karti", true);
  const kaynak = s.dingil_kaynagi || (s.etkin_dingil_mm != null ? "dis_olcu" : "yok");
  const [etiketMetni, etiketSinifi] = DINGIL_KAYNAK_ETIKETLERI[kaynak];
  $("dingil-degeri").textContent = s.etkin_dingil_mm != null
    ? (kaynak === "elle" ? "" : "≈ ") + sayiBicimle(s.etkin_dingil_mm, DINGIL_BASAMAK) + " mm"
    : "bilinmiyor";
  const etiket = $("dingil-kaynagi");
  etiket.textContent = etiketMetni;
  etiket.className = "etiket " + etiketSinifi;
  $("dingil-yoksa").textContent = s.parcali_mi
    ? "parçalı şaside pervane sığma kontrolü yapılamaz; aşağıdan gövde ve koldan hesaplatabilirsin."
    : "şasinin dış ölçüsünden tahmin edilir.";
  $("dingil-girdisi").value = s.dingil_mm != null ? Math.round(s.dingil_mm * 10) / 10 : "";
  $("dingil-temizle").disabled = s.dingil_mm == null;
  goster("dingil-tahmini", false);
  sonDingilTahmini = null;

  const parcali = Boolean(sonYukleme && sonYukleme.parcali);
  goster("dingil-hesap", parcali);
  if (!parcali) return;
  const secenekler = sonYukleme.parcalar.map((p) => ({ deger: String(p.sira), ad: p.dosya_adi }));
  const ilk = (rol) => sonYukleme.parcalar.find((p) => p.rol === rol);
  seceneklereYaz("dingil-govde", secenekler);
  seceneklereYaz("dingil-kol", secenekler);
  const govde = ilk("govde");
  const kol = ilk("kol");
  if (govde) $("dingil-govde").value = String(govde.sira);
  if (kol) $("dingil-kol").value = String(kol.sira);
  seceneklereYaz("dingil-baglanti", sonYukleme.kol_baglantilari);
}

async function dingiliGonder(dingil, kaynak) {
  goster("dingil-hatasi", false);
  try {
    const yanit = await istekGonder(
      `/api/dronelar/${droneKimligi}/sasi/dingil`,
      jsonIstegi("PUT", { dingil_mm: dingil, kaynak })
    );
    sonucuGoster(yanit.olculer);
    // Dingil değişti: üstten görünüş, K5, şartname ve özet yeniden hesaplanır.
    elektronikOzetiniYenile();
  } catch (veri) {
    hataGoster("dingil-hatasi", veri);
  }
}

$("dingil-formu").addEventListener("submit", (olay) => {
  olay.preventDefault();
  const deger = sayiOku($("dingil-girdisi").value);
  if (deger === null || Number.isNaN(deger)) {
    hataGoster("dingil-hatasi", { hata: "Dingil için mm cinsinden bir sayı yazın." });
    return;
  }
  dingiliGonder(deger, "elle");
});

$("dingil-temizle").addEventListener("click", () => dingiliGonder(null, "elle"));

$("dingil-hesapla").addEventListener("click", async () => {
  goster("dingil-hatasi", false);
  goster("dingil-tahmini", false);
  $("dingil-hesapla").disabled = true;
  try {
    const t = await istekGonder(
      `/api/dronelar/${droneKimligi}/sasi/dingil-hesapla`,
      jsonIstegi("POST", {
        kol_sira: Number($("dingil-kol").value),
        govde_sira: Number($("dingil-govde").value),
        baglanti: $("dingil-baglanti").value,
      })
    );
    sonDingilTahmini = t;
    $("dingil-tahmin-degeri").textContent = "≈ " + sayiBicimle(t.dingil_mm, DINGIL_BASAMAK) + " mm";
    $("dingil-tahmin-aciklamasi").textContent = t.aciklama;
    goster("dingil-tahmini", true);
  } catch (veri) {
    hataGoster("dingil-hatasi", veri);
  } finally {
    $("dingil-hesapla").disabled = false;
  }
});

$("dingil-onayla").addEventListener("click", () => {
  if (sonDingilTahmini) dingiliGonder(sonDingilTahmini.dingil_mm, "hesap");
});

$("dingil-vazgec").addEventListener("click", () => {
  sonDingilTahmini = null;
  goster("dingil-tahmini", false);
});

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
