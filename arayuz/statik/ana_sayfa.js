// Ana sayfa: üç başlangıç seçeneği, yeni drone formu ve kayıtlı dronelar listesi.
"use strict";

const BASLIKLAR = {
  sifirdan: "Sıfırdan drone yap",
  elimdeki: "Elimdeki drone'u geliştir",
};

let secilenBaslangic = null;

function seceneklereDoldur(seciciKimligi, secenekler) {
  const secici = $(seciciKimligi);
  secici.replaceChildren();
  for (const { deger, ad } of secenekler) {
    const s = document.createElement("option");
    s.value = deger;
    s.textContent = ad;
    secici.append(s);
  }
}

async function formSecenekleriniYukle() {
  const s = await istekGonder("/api/secenekler");
  seceneklereDoldur("drone-turu", s.drone_turleri);
  seceneklereDoldur("drone-amaci", s.amaclar.map((a) => ({ deger: a, ad: a })));
  // Önceden yüklenmiş şartnameler "yeni yükle" seçeneğinin altına eklenir.
  const sartnameler = await istekGonder("/api/sartnameler");
  const secici = $("drone-sartname");
  if (sartnameler.length) {
    const grup = document.createElement("optgroup");
    grup.label = "Önceden yüklenmiş şartnameler";
    for (const sn of sartnameler) grup.append(new Option(`${sn.ad} (${sn.dosya_adi})`, String(sn.kimlik)));
    secici.append(grup);
  }
}

$("drone-sartname").addEventListener("change", () => {
  const yeni = $("drone-sartname").value === "yeni";
  for (const e of document.querySelectorAll(".yeni-sartname-alani")) e.classList.toggle("gizli", !yeni);
  $("yeni-sartname-ad").required = yeni;
  $("yeni-sartname-dosya").required = yeni;
});

// Drone oluşturulduktan sonra seçilen şartname eklenir. Bu adım başarısız olursa drone
// zaten kaydedilmiştir; kullanıcı Şartname sekmesinde tekrar deneyebilir.
async function sartnameyiEkle(droneKimlik) {
  const secim = $("drone-sartname").value;
  if (!secim) return null;
  try {
    if (secim === "yeni") {
      const form = new FormData();
      form.append("dosya", $("yeni-sartname-dosya").files[0]);
      form.append("ad", $("yeni-sartname-ad").value);
      form.append("drone_kimlik", String(droneKimlik));
      await istekGonder("/api/sartnameler", { method: "POST", body: form });
    } else {
      await istekGonder(`/api/dronelar/${droneKimlik}/sartname`, jsonIstegi("PUT", { sartname_kimlik: Number(secim) }));
    }
  } catch (veri) {
    alert(`Drone oluşturuldu ama şartname eklenemedi: ${(veri && veri.hata) || "bilinmeyen hata"}\n` +
      "Drone sayfasındaki Şartname sekmesinden tekrar deneyebilirsiniz.");
  }
  return "#sartname";
}

function secenekVurgula(kimlik) {
  for (const k of ["secenek-sifirdan", "secenek-elimdeki", "secenek-kayitli"]) {
    $(k).classList.toggle("secili", k === kimlik);
  }
}

function yeniDroneFormunuAc(baslangic) {
  secilenBaslangic = baslangic;
  secenekVurgula("secenek-" + baslangic);
  $("yeni-drone-basligi").textContent = BASLIKLAR[baslangic];
  goster("kayitli-karti", false);
  goster("yeni-drone-hatasi", false);
  goster("yeni-drone-karti", true);
  $("drone-adi").focus();
}

$("secenek-sifirdan").addEventListener("click", () => yeniDroneFormunuAc("sifirdan"));
$("secenek-elimdeki").addEventListener("click", () => yeniDroneFormunuAc("elimdeki"));
$("iptal-dugmesi").addEventListener("click", () => {
  goster("yeni-drone-karti", false);
  secenekVurgula(null);
});

$("yeni-drone-formu").addEventListener("submit", async (olay) => {
  olay.preventDefault();
  $("olustur-dugmesi").disabled = true;
  goster("yeni-drone-hatasi", false);
  try {
    const drone = await istekGonder(
      "/api/dronelar",
      jsonIstegi("POST", {
        ad: $("drone-adi").value,
        baslangic_turu: secilenBaslangic,
        drone_turu: $("drone-turu").value,
        amac: $("drone-amaci").value,
      })
    );
    $("olustur-dugmesi").textContent = "Oluşturuluyor…";
    const sekme = await sartnameyiEkle(drone.kimlik);
    window.location.href = `/drone/${drone.kimlik}${sekme || ""}`;
  } catch (veri) {
    hataGoster("yeni-drone-hatasi", veri);
    $("olustur-dugmesi").disabled = false;
  }
});

// ---------- Kayıtlı dronelar ----------

$("secenek-kayitli").addEventListener("click", async () => {
  secenekVurgula("secenek-kayitli");
  goster("yeni-drone-karti", false);
  goster("kayitli-karti", true);
  await kayitlilariYukle();
});

function droneSatiri(d) {
  const satir = document.createElement("div");
  satir.className = "drone-karti";

  const ust = document.createElement("div");
  ust.className = "kart-ust-satir";
  const bilgi = document.createElement("div");
  const ad = document.createElement("div");
  ad.className = "liste-baslik";
  ad.textContent = d.ad;
  const tur = document.createElement("div");
  tur.className = "soluk";
  tur.textContent = `${d.drone_turu_adi} · ${d.amac}`;
  bilgi.append(ad, tur);
  ust.append(droneCizimi("", d.motor_sayisi), bilgi);

  const ozet = document.createElement("div");
  ozet.className = "soluk";
  const agirlik = d.sasi_agirlik_g != null ? `şasi ${sayiBicimle(d.sasi_agirlik_g, 0)} g · ` : "";
  ozet.textContent = `${d.baslangic_turu_adi} · ${agirlik}son değişiklik ${zamanBicimle(d.guncelleme_zamani)}`;

  const dugmeler = document.createElement("div");
  dugmeler.className = "satir";
  const ac = document.createElement("a");
  ac.className = "dugme";
  ac.href = `/drone/${d.kimlik}`;
  ac.textContent = "Aç";
  const sil = document.createElement("button");
  sil.className = "tehlike";
  sil.type = "button";
  sil.textContent = "Sil";
  sil.addEventListener("click", () => droneSil(d));
  dugmeler.append(ac, sil);

  satir.append(ust, ozet, dugmeler);
  return satir;
}

async function kayitlilariYukle() {
  goster("kayitli-hatasi", false);
  try {
    const dronelar = await istekGonder("/api/dronelar");
    $("kayitli-liste").replaceChildren(...dronelar.map(droneSatiri));
    goster("kayitli-bos", dronelar.length === 0);
    $("kayitli-ozet").textContent =
      dronelar.length === 0 ? "Henüz kayıtlı drone yok." : `${dronelar.length} kayıtlı drone`;
  } catch (veri) {
    hataGoster("kayitli-hatasi", veri);
  }
}

async function droneSil(d) {
  // Silme geri alınamaz; şasi dosyası da silinir.
  if (!confirm(`"${d.ad}" silinsin mi? Şasi dosyası dahil tüm bilgileri kalıcı olarak silinir.`)) return;
  try {
    await istekGonder(`/api/dronelar/${d.kimlik}`, { method: "DELETE" });
    await kayitlilariYukle();
  } catch (veri) {
    hataGoster("kayitli-hatasi", veri);
  }
}

// ---------- Başlangıç ----------

formSecenekleriniYukle().catch((veri) => hataGoster("yeni-drone-hatasi", veri));
istekGonder("/api/dronelar")
  .then((d) => {
    $("kayitli-ozet").textContent = d.length === 0 ? "Henüz kayıtlı drone yok." : `${d.length} kayıtlı drone`;
    // Kayıtlı drone varsa liste açılışta görünür; kullanıcı kaldığı yerden hemen devam edebilsin.
    if (d.length) {
      goster("kayitli-karti", true);
      kayitlilariYukle();
    }
  })
  .catch(() => {});
