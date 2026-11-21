// Drone çalışma sayfası: drone bilgisini yükler, sekmeleri yönetir,
// şasi (sasi.js) ve elektronik (elektronik.js) bölümlerini başlatır.
"use strict";

const droneKimligi = Number((window.location.pathname.match(/\/drone\/(\d+)/) || [])[1]);
// Programın adı sayfaya sunucu tarafından yazılır (cekirdek/ayarlar.py → PROGRAM_ADI).
const programAdi = document.querySelector('meta[name="program-adi"]').content;

let mevcutDrone = null; // sunucudan gelen son drone bilgisi; diğer sekmeler ekrandaki metni ayrıştırmasın diye

// Drone'un kısa tanımı: "tür · amaç · başlangıç". Başlıkta ve Hedefler sekmesinde aynı görünsün diye tek yerde.
function droneTanimi(drone) {
  return `${drone.drone_turu_adi} · ${drone.amac} · ${drone.baslangic_turu_adi}`;
}

// Drone bilgisi değiştiğinde (ör. ağırlık kaydedildi) başlık ve elektronik özeti yenilenir.
function droneGuncellendi(drone) {
  mevcutDrone = drone;
  document.title = `${drone.ad} – ${programAdi}`;
  $("drone-adi").textContent = drone.ad;
  $("drone-kayit-no").textContent =
    `// KAYIT #${String(drone.kimlik).padStart(4, "0")} · ${drone.motor_sayisi} ROTOR · ${drone.drone_turu.toUpperCase()}`;
  $("drone-cizimi").replaceChildren(droneCizimi("", drone.motor_sayisi));
  $("drone-ozet").textContent = `${droneTanimi(drone)} · son değişiklik ${zamanBicimle(drone.guncelleme_zamani)}`;

  const agirlikMetni = drone.sasi_agirlik_g != null ? `${sayiBicimle(drone.sasi_agirlik_g, 1)} g` : "girilmedi";
  $("kayitli-agirlik").textContent = agirlikMetni;
  // Şasi ağırlığı toplam ağırlığa girdiği için elektronik özeti de yenilenir.
  elektronikOzetiniYenile();
}

function sekmeAc(ad) {
  for (const dugme of document.querySelectorAll(".sekme")) {
    dugme.classList.toggle("aktif", dugme.dataset.sekme === ad);
  }
  for (const dugme of document.querySelectorAll(".sekme")) {
    goster(`sekme-${dugme.dataset.sekme}`, dugme.dataset.sekme === ad);
  }
  // Parça listesi Elektronik sekmesinde değişmiş olabilir; bu sekmeler her açılışta yeniden kurulur.
  if (ad === "maliyet") maliyetiYenile();
  if (ad === "hedefler") hedeflerSekmesiniAc();
  if (ad === "sartname") sartnameSekmesiniAc();
}

for (const dugme of document.querySelectorAll(".sekme")) {
  dugme.addEventListener("click", () => sekmeAc(dugme.dataset.sekme));
}

// Başlık çubuğundaki oklu "Özet" düğmesi beş özet kutusunu açar/kapatır (ana sayfa kartları gibi).
$("ozet-dugmesi").addEventListener("click", (olay) => {
  const dugme = olay.currentTarget;
  kartiAcKapat(dugme, dugme.getAttribute("aria-expanded") !== "true");
});

async function sayfayiYukle() {
  if (!droneKimligi) {
    hataGoster("sayfa-hatasi", { hata: "Adreste drone numarası yok. Ana sayfaya dönüp bir drone seçin." });
    return;
  }
  try {
    const ayrinti = await istekGonder(`/api/dronelar/${droneKimligi}`);
    await elektronikBolumunuBaslat();
    droneGuncellendi(ayrinti.drone);
    sasiBolumunuBaslat(ayrinti.sasi);
    goster("calisma-alani", true);
    // Adres "#sartname" gibi bir sekme adıyla açıldıysa o sekmeye geçilir (ör. ana sayfadan oluşturduktan sonra).
    const istenen = window.location.hash.slice(1);
    if (document.querySelector(`.sekme[data-sekme="${CSS.escape(istenen)}"]`)) sekmeAc(istenen);
  } catch (veri) {
    hataGoster("sayfa-hatasi", veri);
  }
}

sayfayiYukle();
