// Ana sayfanın kenarlarında uçuşan küçük dronelar.
// Dronelar sabit bir katmanda, içeriğin arkasında durur ve tıklamayı engellemez.
// Bilgisayarda "hareketi azalt" ayarı açıksa CSS animasyonları durdurur (stil.css).
"use strict";

// DEĞİŞTİRİLEBİLİR: Her drone için konum, boyut (px), rota animasyonu ve süre (s).
// Rotalar ekranın kenarlarından geçer ki ortadaki içerikle çakışmasın.
const UCAN_DRONELER = [
  { sol: "3vw", ust: "0", boyut: 88, motor: 4, rota: "rota-sol", sure: 26, gecikme: 0 },
  { sol: "90vw", ust: "0", boyut: 76, motor: 6, rota: "rota-sag", sure: 31, gecikme: -9 },
  { sol: "0", ust: "12vh", boyut: 56, motor: 4, rota: "rota-ust", sure: 38, gecikme: -4 },
  { sol: "0", ust: "86vh", boyut: 68, motor: 8, rota: "rota-alt", sure: 34, gecikme: -17 },
  { sol: "6vw", ust: "48vh", boyut: 50, motor: 6, rota: "rota-gezin", sure: 14, gecikme: -3 },
  { sol: "88vw", ust: "62vh", boyut: 54, motor: 4, rota: "rota-gezin", sure: 17, gecikme: -8 },
];

// Hedef izleme etiketindeki tür kısaltmaları.
const ROTOR_KISALTMALARI = { 4: "QUAD", 6: "HEXA", 8: "OKTO" };

function ucanDroneleriYerlestir() {
  const katman = $("drone-katmani");
  if (!katman) return;
  UCAN_DRONELER.forEach((d, sira) => {
    const kap = document.createElement("div");
    kap.className = "ucan-drone";
    // Savunma arayüzlerindeki gibi hedef izleme çerçevesi ve kimlik etiketi (stil.css'te çizilir).
    kap.dataset.etiket = `İHA-${String(sira + 1).padStart(2, "0")} · ${ROTOR_KISALTMALARI[d.motor]}`;
    Object.assign(kap.style, {
      left: d.sol,
      top: d.ust,
      width: `${d.boyut}px`,
      height: `${d.boyut}px`,
      animation: `${d.rota} ${d.sure}s linear ${d.gecikme}s infinite`,
    });
    if (d.rota === "rota-gezin") kap.style.animationTimingFunction = "ease-in-out";
    const cizim = droneCizimi("", d.motor);
    cizim.style.width = "100%";
    cizim.style.height = "100%";
    kap.append(cizim);
    katman.append(kap);
  });
}

ucanDroneleriYerlestir();
