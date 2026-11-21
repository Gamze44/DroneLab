// DroneLab Asistan paneli: her sayfada sağdan açılan, açık drone'un verilerini bilen sohbet.
// Açma: başlıktaki "Asistan" düğmesi, sağ alttaki yuvarlak düğme veya Ctrl+K; Esc kapatır.
// Yanıt sunucudan akış (Server-Sent Events) olarak gelir; kullanıcı metni ve model yanıtı yalnızca
// textContent / DOM düğümleriyle yazılır (innerHTML kullanılmaz).
// Bütün kod kendi kapsamında durur: sayfadaki diğer betiklerle ad çakışması olmasın diye.
"use strict";

(() => {
  // DEĞİŞTİRİLEBİLİR: Pencere bu genişlikten (px) genişse panel içeriği sola iter, değilse üstüne açılır.
  // Panelin genişliği stil.css'teki --asistan-genislik değişkenidir.
  const ITME_ESIGI = 1100;
  const SOHBET_ADRESI = "/api/asistan/sohbet";
  const GECMIS_ADRESI = "/api/asistan/gecmis";
  const ONERI_ADRESI = "/api/asistan/oneriler";
  const AYAR_ADRESI = "/api/ayarlar/yapay-zeka";
  const ANAHTAR_SAYFASI = "/ayarlar#ay-anahtar";
  // Adreste ?asistan=ac varsa panel açık başlar (bağlantıyla açmak için).
  const ACIK_BASLAT_PARAMETRESI = "asistan";
  const ACIK_BASLAT_DEGERI = "ac";
  const KISAYOL_TUSU = "k";
  // DEĞİŞTİRİLEBİLİR: Yanıt bu kadar saniye gecikirse balonda geçen süre gösterilir; YAVAS_UYARI_SN'den
  // sonra modelin yavaş olduğu da yazılır (ekran donmuş sanılmasın).
  const BEKLEME_GOSTERME_SN = 2;
  const YAVAS_UYARI_SN = 20;
  const SANIYE_MS = 1000;
  const YETKISIZ = 401;
  const SSE_AYRACI = "\n\n";
  const SSE_VERI_ONEKI = "data: ";

  // DEĞİŞTİRİLEBİLİR: Ekrana göre panelde görünen hazır sorular (en çok 3).
  const HAZIR_SORULAR = {
    ana_sayfa: ["Bu programla neler yapabilirim?", "Yeni bir FPV yarış dronuna nereden başlamalıyım?", "Uyum kontrolleri neyi denetliyor?"],
    ayarlar: ["Gemini API anahtarını nereden alırım?", "Günlük istek sınırı ne işe yarar?", "Otomatik model seçimi nasıl çalışır?"],
    sasi: ["Şasi ağırlığı toplamın ne kadarı?", "Bu şasiye en büyük kaç inç pervane sığar?", "Şasi ölçüleri makul görünüyor mu?"],
    elektronik: ["Eksik zorunlu parça var mı?", "Uyum uyarılarının nedeni ne?", "Ağırlığı en çok hangi parça artırıyor?"],
    hedefler: ["Uçuş süresi hedefime nasıl ulaşırım?", "Yük eklersem itki/ağırlık ne olur?", "Bütçem yeterli mi?"],
    uyum: ["Uygunsuz kontrolleri nasıl düzeltirim?", "Uyarılar uçuşu etkiler mi?", "Hangi değerler eksik olduğu için bilinmiyor?"],
    ucus: ["Uçuş süresini artırmak için ne yapmalıyım?", "Asılı kalma gazı neden bu seviyede?", "Daha büyük pil takarsam ne olur?"],
    maliyet: ["Maliyeti düşürmek için ne önerirsin?", "Fiyatı eksik kalemler hangileri?", "Bütçeyi aşıyor muyum?"],
    sartname: ["Şartnameye uymayan maddeler neler?", "Ağırlık sınırına ne kadar payım var?", "Hangi maddeler tahmini değerlere dayanıyor?"],
  };
  const KARSILAMA_DRONE =
    "Merhaba! Açık drone'un parçalarını, uyum kontrollerini ve uçuş hesabını bilen asistanım. " +
    "Sayıları programın kendi hesaplarından veririm; bir değişiklik önerirsem siz **Uygula** demeden hiçbir şey değişmez.";
  const KARSILAMA_GENEL =
    "Merhaba! DroneLab ve kayıtlı dronelarınız hakkındaki sorularınızı yanıtlarım. Bir drone'un ayrıntıları " +
    "(parçalar, uyum, uçuş hesabı) ve değişiklik önerileri için o drone'un sayfasında bana sorun.";
  // Öneri kartındaki önce/sonra satırları: [alan, başlık, birim, ondalık].
  const KARSILASTIRMA_SATIRLARI = [
    ["toplam_agirlik_g", "Toplam ağırlık", " g", 1],
    ["itki_agirlik_orani", "İtki / ağırlık", "", 1],
    ["ucus_suresi_dk", "Uçuş süresi", " dk", 1],
    ["asili_gaz_yuzde", "Asılı kalma gazı", " %", 0],
    ["toplam_maks_akim_a", "Tam gaz akımı", " A", 0],
  ];
  const UYUM_ADLARI = { uygun: "uygun", uyari: "uyarı", uygunsuz: "uygunsuz", bilinmiyor: "bilinmiyor" };
  const ONERI_DURUM_ADLARI = { uygulandi: "✓ Uygulandı", vazgecildi: "Vazgeçildi" };

  const durum = { acik: false, gecmisYuklendi: false, istek: null, sonSoru: "", oncekiOdak: null };
  let ogeler = null;

  // ---------- Bağlam: hangi sayfa / sekmedeyiz ----------

  function acikDroneKimligi() {
    return typeof droneKimligi !== "undefined" && droneKimligi ? droneKimligi : null;
  }

  function ekran() {
    if (acikDroneKimligi()) {
      const aktif = document.querySelector(".sekme.aktif");
      const ad = aktif && aktif.querySelector(".adim-adi");
      return { anahtar: aktif ? aktif.dataset.sekme : "sasi", ad: ad ? ad.textContent.trim() : "Şasi" };
    }
    if (window.location.pathname.startsWith("/ayarlar")) return { anahtar: "ayarlar", ad: "Ayarlar" };
    return { anahtar: "ana_sayfa", ad: "Ana sayfa" };
  }

  function karsilamaMetni() {
    return acikDroneKimligi() ? KARSILAMA_DRONE : KARSILAMA_GENEL;
  }

  function gecmisSorgusu() {
    const kimlik = acikDroneKimligi();
    return kimlik ? `?drone_kimlik=${kimlik}` : "";
  }

  function baglamiGuncelle() {
    const e = ekran();
    ogeler.baglam.textContent = `Bağlam: ${e.ad}`;
    ogeler.hazirSorular.replaceChildren(...(HAZIR_SORULAR[e.anahtar] || []).map((soru) => {
      const d = dugme(soru, "", () => gonder(soru));
      return d;
    }));
  }

  // ---------- DOM yardımcıları ----------

  function dugme(metin, sinif, tiklaninca) {
    const d = document.createElement("button");
    d.type = "button";
    if (sinif) d.className = sinif;
    d.textContent = metin;
    if (tiklaninca) d.addEventListener("click", tiklaninca);
    return d;
  }

  // **kalın** ve `kod` biçimini güvenli DOM düğümlerine çevirir.
  function satirIci(metin) {
    const parcalar = [];
    let son = 0;
    for (const e of metin.matchAll(/(\*\*[^*]+\*\*|`[^`]+`)/g)) {
      if (e.index > son) parcalar.push(document.createTextNode(metin.slice(son, e.index)));
      const kalin = e[0].startsWith("**");
      const oge = document.createElement(kalin ? "strong" : "code");
      oge.textContent = kalin ? e[0].slice(2, -2) : e[0].slice(1, -1);
      parcalar.push(oge);
      son = e.index + e[0].length;
    }
    if (son < metin.length) parcalar.push(document.createTextNode(metin.slice(son)));
    return parcalar;
  }

  // Model metnini paragraf, madde listesi ve başlık satırlarına böler.
  function bicimliYaz(kap, metin) {
    const bloklar = [];
    let liste = null;
    for (const ham of metin.split("\n")) {
      const satir = ham.trimEnd();
      const madde = satir.match(/^\s*(?:[-*•]|(\d+)[.)])\s+(.*)$/);
      if (madde) {
        const sirali = Boolean(madde[1]);
        if (!liste || liste.sirali !== sirali) {
          liste = { oge: document.createElement(sirali ? "ol" : "ul"), sirali };
          bloklar.push(liste.oge);
        }
        const li = document.createElement("li");
        li.append(...satirIci(madde[2]));
        liste.oge.append(li);
        continue;
      }
      liste = null;
      if (!satir.trim()) continue;
      const baslik = satir.match(/^#{1,4}\s+(.*)$/);
      const p = document.createElement("p");
      if (baslik) p.className = "asistan-baslik-satiri";
      p.append(...satirIci(baslik ? baslik[1] : satir));
      bloklar.push(p);
    }
    kap.replaceChildren(...bloklar);
  }

  function asagiKaydir() {
    ogeler.mesajlar.scrollTop = ogeler.mesajlar.scrollHeight;
  }

  function mesajBalonu(rol) {
    const balon = ogeAc("div", `asistan-mesaj ${rol}`);
    balon.araclar = ogeAc("div", "asistan-araclar");
    balon.govde = ogeAc("div", "asistan-mesaj-govde");
    balon.append(balon.araclar, balon.govde);
    ogeler.mesajlar.append(balon);
    return balon;
  }

  function ogeAc(etiket, sinif, metin) {
    const oge = document.createElement(etiket);
    if (sinif) oge.className = sinif;
    if (metin !== undefined) oge.textContent = metin;
    return oge;
  }

  function kullaniciMesaji(metin) {
    const balon = ogeAc("div", "asistan-mesaj kullanici", metin);
    ogeler.mesajlar.append(balon);
  }

  function asistanMesaji(metin, model) {
    const balon = mesajBalonu("asistan");
    bicimliYaz(balon.govde, metin);
    if (model) balon.append(ogeAc("div", "asistan-not", model));
    return balon;
  }

  // Hata kutusu: anahtar yoksa Ayarlar bağlantısı, her durumda "Tekrar dene".
  function hataKutusu(kap, veri) {
    const kutu = ogeAc("div", "kutu-hata", (veri && veri.hata) || "Programın sunucusuna ulaşılamadı. Program kapanmış olabilir.");
    const satir = ogeAc("div", "satir");
    if (veri && veri.kod === YETKISIZ) {
      const baglanti = ogeAc("a", "", "Ayarlar'a git");
      baglanti.href = ANAHTAR_SAYFASI;
      satir.append(baglanti);
    }
    if (durum.sonSoru) satir.append(dugme("Tekrar dene", "ikincil", () => gonder(durum.sonSoru)));
    kutu.append(satir);
    kap.append(kutu);
  }

  // ---------- Öneri kartı ----------

  function degerMetni(h, birim, basamak) {
    if (!h || h.deger === null || h.deger === undefined) return "–";
    return `${sayiBicimle(h.deger, basamak)}${birim}${h.tahmini ? " (tahmini)" : ""}`;
  }

  function uyumMetni(sayilar) {
    return Object.entries(UYUM_ADLARI)
      .filter(([anahtar]) => sayilar && sayilar[anahtar])
      .map(([anahtar, ad]) => `${sayilar[anahtar]} ${ad}`)
      .join(", ") || "–";
  }

  function oneriKarti(o) {
    const kart = ogeAc("div", "asistan-oneri");
    kart.setAttribute("role", "group");
    kart.setAttribute("aria-label", "Değişiklik önerisi");
    kart.append(ogeAc("div", "ust-etiket", "// DEĞİŞİKLİK ÖNERİSİ"));
    if (o.gerekce) kart.append(ogeAc("p", "", o.gerekce));
    const liste = ogeAc("ul");
    for (const a of o.aciklamalar || []) liste.append(ogeAc("li", "", a));
    kart.append(liste);

    const tablo = ogeAc("table");
    const baslik = ogeAc("tr");
    baslik.append(ogeAc("th", "", ""), ogeAc("th", "", "ŞU AN"), ogeAc("th", "", "SONRA"));
    tablo.append(baslik);
    for (const [alan, ad, birim, basamak] of KARSILASTIRMA_SATIRLARI) {
      const tr = ogeAc("tr");
      tr.append(ogeAc("td", "", ad), ogeAc("td", "", degerMetni(o.once[alan], birim, basamak)),
        ogeAc("td", "", degerMetni(o.sonra[alan], birim, basamak)));
      tablo.append(tr);
    }
    const uyum = ogeAc("tr");
    uyum.append(ogeAc("td", "", "Uyum"), ogeAc("td", "", uyumMetni(o.once.uyum)), ogeAc("td", "", uyumMetni(o.sonra.uyum)));
    tablo.append(uyum);
    kart.append(tablo);

    if (o.uyum_degisimleri && o.uyum_degisimleri.length) {
      const degisen = ogeAc("ul");
      for (const u of o.uyum_degisimleri) {
        degisen.append(ogeAc("li", "", `${u.kod} ${u.baslik}: ${UYUM_ADLARI[u.once] || "–"} → ${UYUM_ADLARI[u.sonra]} (${u.aciklama})`));
      }
      kart.append(degisen);
    }
    const eksik = (o.sonra.eksik_zorunlu_parcalar || []);
    if (eksik.length) kart.append(ogeAc("div", "asistan-not", `Sonrasında eksik zorunlu parça: ${eksik.join(", ")}`));

    const satir = ogeAc("div", "satir");
    if (o.durum === "bekliyor") {
      satir.append(
        dugme("Uygula", "", () => oneriIslemi(o, kart, "uygula")),
        dugme("Vazgeç", "ikincil", () => oneriIslemi(o, kart, "vazgec")),
      );
    } else {
      satir.append(ogeAc("span", "etiket", ONERI_DURUM_ADLARI[o.durum] || o.durum));
    }
    kart.append(satir);
    return kart;
  }

  async function oneriIslemi(o, kart, islem) {
    for (const d of kart.querySelectorAll("button")) d.disabled = true;
    try {
      const yanit = await istekGonder(`${ONERI_ADRESI}/${o.kimlik}/${islem}`, { method: "POST" });
      kart.replaceWith(oneriKarti(yanit.oneri));
      if (islem === "uygula") await sayfayiYenile();
    } catch (veri) {
      for (const d of kart.querySelectorAll("button")) d.disabled = false;
      kart.append(ogeAc("div", "kutu-hata", (veri && veri.hata) || "İşlem yapılamadı."));
    }
  }

  // Uygulanan değişiklik drone sayfasındaki özet ve açık sekmeye yansısın.
  async function sayfayiYenile() {
    if (typeof elektronikOzetiniYenile === "function") await elektronikOzetiniYenile();
    const aktif = document.querySelector(".sekme.aktif");
    if (aktif && typeof sekmeAc === "function") sekmeAc(aktif.dataset.sekme);
  }

  // ---------- Sohbet ----------

  // Sunucunun SSE akışını okur; her olay için isle(olay) çağrılır.
  async function akisiOku(yanit, isle) {
    const okuyucu = yanit.body.getReader();
    const cozucu = new TextDecoder();
    let tampon = "";
    for (;;) {
      const { value, done } = await okuyucu.read();
      if (done) break;
      tampon += cozucu.decode(value, { stream: true });
      let ayrac;
      while ((ayrac = tampon.indexOf(SSE_AYRACI)) >= 0) {
        const blok = tampon.slice(0, ayrac);
        tampon = tampon.slice(ayrac + SSE_AYRACI.length);
        const veri = blok.split("\n").filter((s) => s.startsWith(SSE_VERI_ONEKI)).map((s) => s.slice(SSE_VERI_ONEKI.length)).join("\n");
        if (veri) isle(JSON.parse(veri));
      }
    }
  }

  function istekSuruyor(suruyor) {
    goster(ogeler.gonder.id, !suruyor);
    goster(ogeler.durdur.id, suruyor);
    for (const d of ogeler.hazirSorular.querySelectorAll("button")) d.disabled = suruyor;
  }

  async function gonder(metin) {
    metin = (metin || "").trim();
    if (!metin || durum.istek) return;
    durum.sonSoru = metin;
    ogeler.girdi.value = "";
    kullaniciMesaji(metin);
    const balon = mesajBalonu("asistan");
    balon.classList.add("yaziyor");
    asagiKaydir();
    let yazilan = "";
    const istek = new AbortController();
    durum.istek = istek;
    istekSuruyor(true);
    // Bekleme göstergesi: ilk metin, öneri veya hata gelene kadar geçen süreyi yazar.
    const bekleme = ogeAc("div", "asistan-bekleme");
    balon.araclar.append(bekleme);
    const baslangic = Date.now();
    const sayac = setInterval(() => {
      const sn = Math.round((Date.now() - baslangic) / SANIYE_MS);
      if (sn >= BEKLEME_GOSTERME_SN) {
        bekleme.textContent = `Yanıt hazırlanıyor… ${sn} sn${sn >= YAVAS_UYARI_SN ? " (Gemini şu an yavaş yanıt veriyor)" : ""}`;
      }
    }, SANIYE_MS);
    const beklemeyiBitir = () => {
      clearInterval(sayac);
      bekleme.remove();
    };
    try {
      const govde = { mesaj: metin, drone_kimlik: acikDroneKimligi(), ekran: ekran().anahtar };
      const yanit = await fetch(SOHBET_ADRESI, { ...jsonIstegi("POST", govde), signal: istek.signal });
      if (!yanit.ok) {
        const veri = await yanit.json().catch(() => ({}));
        throw { ...veri, kod: yanit.status };
      }
      await akisiOku(yanit, (olay) => {
        if (["metin", "oneri", "hata", "bitti"].includes(olay.tur)) beklemeyiBitir();
        if (olay.tur === "metin") {
          yazilan += olay.metin;
          bicimliYaz(balon.govde, yazilan);
        } else if (olay.tur === "arac") {
          // Araç satırları bekleme göstergesinin üstüne eklenir; gösterge hep en altta kalır.
          balon.araclar.insertBefore(ogeAc("div", "", `${olay.aciklama}…`), bekleme.parentNode ? bekleme : null);
        } else if (olay.tur === "oneri") {
          balon.append(oneriKarti(olay.oneri));
        } else if (olay.tur === "sifirla") {
          yazilan = "";
          balon.govde.replaceChildren();
          balon.araclar.replaceChildren(bekleme);
          for (const k of balon.querySelectorAll(".asistan-oneri")) k.remove();
        } else if (olay.tur === "hata") {
          hataKutusu(balon, olay);
        } else if (olay.tur === "bitti") {
          ogeler.durum.textContent = `${olay.model} · bugün ${olay.bugun_kullanilan}/${olay.gunluk_sinir} istek`;
          balon.append(ogeAc("div", "asistan-not", olay.model));
        }
        asagiKaydir();
      });
    } catch (veri) {
      if (veri && veri.name === "AbortError") {
        balon.append(ogeAc("div", "asistan-not", "Yanıt durduruldu."));
      } else {
        hataKutusu(balon, veri);
      }
    } finally {
      beklemeyiBitir();
      durum.istek = null;
      balon.classList.remove("yaziyor");
      if (!yazilan && !balon.querySelector(".asistan-oneri, .kutu-hata, .asistan-not")) balon.remove();
      istekSuruyor(false);
      asagiKaydir();
    }
  }

  async function gecmisiYukle() {
    durum.gecmisYuklendi = true;
    try {
      const veri = await istekGonder(`${GECMIS_ADRESI}${gecmisSorgusu()}`);
      ogeler.mesajlar.replaceChildren();
      if (!veri.mesajlar.length) asistanMesaji(karsilamaMetni());
      for (const m of veri.mesajlar) {
        if (m.rol === "kullanici") {
          kullaniciMesaji(m.metin);
        } else {
          const balon = asistanMesaji(m.metin, m.model);
          for (const o of m.oneriler) balon.append(oneriKarti(o));
        }
      }
      asagiKaydir();
    } catch (veri) {
      durum.gecmisYuklendi = false;
      hataKutusu(ogeler.mesajlar, veri);
    }
  }

  async function anahtariDenetle() {
    try {
      const ayar = await istekGonder(AYAR_ADRESI);
      goster(ogeler.anahtarUyarisi.id, !ayar.anahtar_var);
      ogeler.girdi.disabled = !ayar.anahtar_var;
      if (ayar.anahtar_var && !ogeler.durum.textContent) {
        ogeler.durum.textContent = `bugün ${ayar.bugun_kullanilan}/${ayar.gunluk_sinir} istek`;
      }
    } catch {
      // Ayar okunamazsa panel yine açılır; gönderimde sunucu hatayı söyler.
    }
  }

  async function yeniSohbet() {
    if (durum.istek || !confirm("Bu sohbetin geçmişi silinsin mi?")) return;
    try {
      await istekGonder(`${GECMIS_ADRESI}${gecmisSorgusu()}`, { method: "DELETE" });
      ogeler.mesajlar.replaceChildren();
      asistanMesaji(karsilamaMetni());
    } catch (veri) {
      hataKutusu(ogeler.mesajlar, veri);
    }
  }

  // ---------- Açma / kapama ----------

  function duzeniGuncelle() {
    document.body.classList.toggle("asistan-acik", durum.acik);
    document.body.classList.toggle("asistan-itiyor", durum.acik && window.innerWidth >= ITME_ESIGI);
  }

  function ac() {
    if (durum.acik) return;
    durum.acik = true;
    durum.oncekiOdak = document.activeElement;
    ogeler.panel.classList.add("acik");
    ogeler.panel.inert = false;
    ogeler.panel.removeAttribute("aria-hidden");
    for (const d of ogeler.acmaDugmeleri) d.setAttribute("aria-expanded", "true");
    duzeniGuncelle();
    baglamiGuncelle();
    if (!durum.gecmisYuklendi) gecmisiYukle();
    anahtariDenetle();
    ogeler.girdi.focus();
  }

  function kapat() {
    if (!durum.acik) return;
    durum.acik = false;
    ogeler.panel.classList.remove("acik");
    ogeler.panel.inert = true;
    ogeler.panel.setAttribute("aria-hidden", "true");
    for (const d of ogeler.acmaDugmeleri) d.setAttribute("aria-expanded", "false");
    duzeniGuncelle();
    const hedef = durum.oncekiOdak;
    if (hedef && typeof hedef.focus === "function" && document.contains(hedef)) hedef.focus();
  }

  function acKapat() {
    if (durum.acik) kapat();
    else ac();
  }

  // ---------- Kurulum ----------

  function sohbetSimgesi() {
    return svgOge("svg", { viewBox: "0 0 24 24", "aria-hidden": "true", fill: "none", stroke: "currentColor", "stroke-width": 1.8,
      "stroke-linecap": "round", "stroke-linejoin": "round" },
    svgOge("path", { d: "M4 5h16v11H9l-5 4z" }),
    svgOge("path", { d: "M8 9.5h8M8 12.5h5" }));
  }

  function kur() {
    const panel = ogeAc("aside", "asistan-paneli");
    panel.id = "asistan-paneli";
    panel.setAttribute("role", "complementary");
    panel.setAttribute("aria-label", "DroneLab Asistan");
    panel.setAttribute("aria-hidden", "true");
    panel.inert = true;

    const baslik = ogeAc("div", "asistan-baslik");
    const baslikMetni = ogeAc("div");
    const baglam = ogeAc("div", "asistan-baglam");
    baslikMetni.append(ogeAc("div", "ust-etiket", "// DRONELAB ASİSTAN"), baglam);
    const baslikDugmeleri = ogeAc("div", "asistan-baslik-dugmeleri");
    const kapatDugmesi = dugme("✕", "ikincil", kapat);
    kapatDugmesi.setAttribute("aria-label", "Asistanı kapat (Esc)");
    baslikDugmeleri.append(dugme("Yeni sohbet", "ikincil", yeniSohbet), kapatDugmesi);
    baslik.append(baslikMetni, baslikDugmeleri);

    const mesajlar = ogeAc("div", "asistan-mesajlar");
    mesajlar.setAttribute("role", "log");
    mesajlar.setAttribute("aria-live", "polite");
    mesajlar.setAttribute("aria-label", "Sohbet");

    const anahtarUyarisi = ogeAc("div", "kutu-uyari gizli", "Asistanı kullanmak için Ayarlar'dan Gemini API anahtarı girin. ");
    anahtarUyarisi.id = "asistan-anahtar-uyarisi";
    const ayarBaglantisi = ogeAc("a", "", "Ayarlar'a git");
    ayarBaglantisi.href = ANAHTAR_SAYFASI;
    anahtarUyarisi.append(ayarBaglantisi);

    const hazirSorular = ogeAc("div", "asistan-hazir-sorular");
    hazirSorular.setAttribute("aria-label", "Hazır sorular");

    const form = ogeAc("form", "asistan-formu");
    const girdi = ogeAc("textarea");
    girdi.rows = 2;
    girdi.maxLength = 4000;
    girdi.placeholder = "Sorunuzu yazın (Enter gönderir, Shift+Enter yeni satır)";
    girdi.setAttribute("aria-label", "Asistana sorunuz");
    const satir = ogeAc("div", "satir");
    const durumYazisi = ogeAc("span", "asistan-durum");
    const gonderDugmesi = ogeAc("button", "", "Gönder");
    gonderDugmesi.type = "submit";
    gonderDugmesi.id = "asistan-gonder";
    const durdurDugmesi = dugme("Durdur", "tehlike gizli", () => durum.istek && durum.istek.abort());
    durdurDugmesi.id = "asistan-durdur";
    satir.append(durumYazisi, durdurDugmesi, gonderDugmesi);
    form.append(girdi, satir);
    form.addEventListener("submit", (olay) => {
      olay.preventDefault();
      gonder(girdi.value);
    });
    girdi.addEventListener("keydown", (olay) => {
      if (olay.key === "Enter" && !olay.shiftKey && !olay.isComposing) {
        olay.preventDefault();
        form.requestSubmit();
      }
    });

    panel.append(baslik, anahtarUyarisi, mesajlar, hazirSorular, form);
    document.body.append(panel);

    const ustDugme = dugme("Asistan", "asistan-ust-dugme", acKapat);
    ustDugme.title = "DroneLab Asistan (Ctrl+K)";
    const sistemDurumu = document.querySelector("header .sistem-durumu");
    if (sistemDurumu) sistemDurumu.before(ustDugme);
    else if (document.querySelector("header")) document.querySelector("header").append(ustDugme);

    const yuvarlak = dugme("", "asistan-yuvarlak", acKapat);
    yuvarlak.append(sohbetSimgesi());
    yuvarlak.setAttribute("aria-label", "DroneLab Asistan'ı aç (Ctrl+K)");
    document.body.append(yuvarlak);

    const acmaDugmeleri = [ustDugme, yuvarlak];
    for (const d of acmaDugmeleri) {
      d.setAttribute("aria-controls", panel.id);
      d.setAttribute("aria-expanded", "false");
    }
    ogeler = {
      panel, baglam, mesajlar, anahtarUyarisi, hazirSorular, girdi, gonder: gonderDugmesi, durdur: durdurDugmesi,
      durum: durumYazisi, acmaDugmeleri,
    };

    document.addEventListener("keydown", (olay) => {
      if ((olay.ctrlKey || olay.metaKey) && !olay.altKey && olay.key.toLowerCase() === KISAYOL_TUSU) {
        olay.preventDefault();
        acKapat();
      } else if (olay.key === "Escape" && durum.acik) {
        olay.preventDefault();
        kapat();
      }
    });
    // Drone sayfasında sekme değişince (tıklamayla da, adresteki #sekme ile de) bağlam ve hazır
    // sorular güncellenir: etkin sekmenin "aktif" sınıfı izlenir.
    const adimMenusu = document.querySelector(".adim-menusu");
    if (adimMenusu) {
      new MutationObserver(() => {
        if (durum.acik) baglamiGuncelle();
      }).observe(adimMenusu, { subtree: true, attributes: true, attributeFilter: ["class"] });
    }
    window.addEventListener("resize", duzeniGuncelle);

    if (new URLSearchParams(window.location.search).get(ACIK_BASLAT_PARAMETRESI) === ACIK_BASLAT_DEGERI) ac();
  }

  kur();
})();
