"""
Yerel SQLite veritabanı bağlantısı ve şeması.

Veritabanı tek bir dosyadır (veri/dronelar.sqlite3); sunucu gerekmez.
Şema sürümü PRAGMA user_version ile tutulur. Her sürümün değişiklikleri
GOCLER sözlüğünde ayrı durur; eski bir dosya açıldığında yalnızca eksik
sürümler sırayla uygulanır, böylece kayıtlı dronelar kaybolmaz.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Final

from cekirdek.hatalar import DroneProgramHatasi

# Bir bağlantının, başka bir işlemin yazma kilidini bırakmasını en çok bekleyeceği süre
# (saniye). sqlite3'ün varsayılanı 5 sn; 30-40 eşzamanlı yazmada yetmeyip
# "database is locked" hatası veriyordu.
KILIT_BEKLEME_SN: Final[float] = 30.0
# WAL kipinde okuyanlar yazanı, yazan okuyanları beklemez; yalnızca iki yazma sıraya girer.
# Kip dosyaya kaydedilir; veritabanının yanında -wal ve -shm dosyaları görünür.
GUNLUK_KIPI: Final[str] = "WAL"

# Sürüm 1: dronelar ve şasiler.
SEMA_V1: Final[str] = """
CREATE TABLE IF NOT EXISTS dronelar (
    kimlik             INTEGER PRIMARY KEY AUTOINCREMENT,
    ad                 TEXT    NOT NULL,
    baslangic_turu     TEXT    NOT NULL,
    drone_turu         TEXT    NOT NULL,
    amac               TEXT    NOT NULL,
    sasi_agirlik_g     REAL,
    olusturma_zamani   TEXT    NOT NULL,
    guncelleme_zamani  TEXT    NOT NULL
);

-- Şasi geometrisi JSON olarak saklanır: okuyuculara yeni alan eklendiğinde
-- tablo şemasını değiştirmek gerekmesin diye.
CREATE TABLE IF NOT EXISTS sasiler (
    drone_kimlik    INTEGER PRIMARY KEY REFERENCES dronelar(kimlik) ON DELETE CASCADE,
    saklanan_dosya  TEXT NOT NULL,
    geometri_json   TEXT NOT NULL,
    olculer_json    TEXT
);
"""

# Sürüm 2: elektronik parça kataloğu ve drone–parça bağı.
# Teknik değerler parça türüne göre değiştiği için JSON olarak saklanır; arama ve
# tekrar kaydı önleme için gereken alanlar (tür, üretici, model, anahtar) ayrı sütundur.
SEMA_V2: Final[str] = """
CREATE TABLE IF NOT EXISTS parcalar (
    kimlik             INTEGER PRIMARY KEY AUTOINCREMENT,
    tur                TEXT    NOT NULL,
    alt_tur            TEXT,
    uretici            TEXT    NOT NULL,
    model              TEXT    NOT NULL,
    ad                 TEXT,
    arama_anahtari     TEXT    NOT NULL UNIQUE,
    arama_metni        TEXT    NOT NULL,
    agirlik_g          REAL,
    teknik_json        TEXT    NOT NULL,
    dogrulandi         INTEGER NOT NULL DEFAULT 0,
    kaynak_url         TEXT,
    notlar             TEXT,
    olusturma_zamani   TEXT    NOT NULL,
    guncelleme_zamani  TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS parcalar_tur ON parcalar (tur, alt_tur);

-- Parçanın bir drone'daki durumu (elimde / önerilen / planlanan) bu tabloda durur;
-- çünkü katalog tüm dronelar arasında ortaktır. Katalogdaki bir parça bir drone'da
-- kullanılıyorsa silinemez (RESTRICT); drone silinince bağları da silinir (CASCADE).
CREATE TABLE IF NOT EXISTS drone_parcalari (
    kimlik          INTEGER PRIMARY KEY AUTOINCREMENT,
    drone_kimlik    INTEGER NOT NULL REFERENCES dronelar(kimlik) ON DELETE CASCADE,
    parca_kimlik    INTEGER NOT NULL REFERENCES parcalar(kimlik) ON DELETE RESTRICT,
    adet            INTEGER NOT NULL CHECK (adet > 0),
    durum           TEXT    NOT NULL,
    eklenme_zamani  TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS drone_parcalari_drone ON drone_parcalari (drone_kimlik);
"""

# Sürüm 3: yapay zeka isteklerinin günlük sayımı (ücretsiz kotayı aşmamak için günlük sınır).
SEMA_V3: Final[str] = """
CREATE TABLE IF NOT EXISTS yapay_zeka_kullanimi (
    gun           TEXT    PRIMARY KEY,
    istek_sayisi  INTEGER NOT NULL DEFAULT 0
);
"""

# Sürüm 4: maliyet. Fiyatlar parça tablosuna sütun olarak değil ayrı tablolarda durur;
# böylece parça kataloğu ve drone kaydı kodu değişmeden kalır.
SEMA_V4: Final[str] = """
-- Katalog parçasının birim (1 adet) fiyatı; katalog ortak olduğu için tüm dronelarda geçerlidir.
CREATE TABLE IF NOT EXISTS parca_fiyatlari (
    parca_kimlik       INTEGER PRIMARY KEY REFERENCES parcalar(kimlik) ON DELETE CASCADE,
    tutar              REAL    NOT NULL CHECK (tutar >= 0),
    para_birimi        TEXT    NOT NULL,
    guncelleme_zamani  TEXT    NOT NULL
);

-- Drone'a özel maliyet bilgisi: şasi fiyatı ve şasinin elde olup olmadığı.
CREATE TABLE IF NOT EXISTS drone_maliyetleri (
    drone_kimlik       INTEGER PRIMARY KEY REFERENCES dronelar(kimlik) ON DELETE CASCADE,
    sasi_tutari        REAL    CHECK (sasi_tutari IS NULL OR sasi_tutari >= 0),
    sasi_para_birimi   TEXT,
    sasi_elimde        INTEGER NOT NULL DEFAULT 0
);

-- TCMB'den alınan son kurlar (para biriminin 1 biriminin TL karşılığı).
CREATE TABLE IF NOT EXISTS kurlar (
    para_birimi   TEXT PRIMARY KEY,
    tl_karsiligi  REAL NOT NULL,
    kur_tarihi    TEXT NOT NULL,
    alinma_gunu   TEXT NOT NULL
);
"""

# Sürüm 5: drone hedefleri (istenen uçuş süresi, yük, bütçe); hepsi isteğe bağlı.
SEMA_V5: Final[str] = """
CREATE TABLE IF NOT EXISTS drone_hedefleri (
    drone_kimlik    INTEGER PRIMARY KEY REFERENCES dronelar(kimlik) ON DELETE CASCADE,
    ucus_suresi_dk  REAL,
    yuk_g           REAL,
    butce_tl        REAL
);
"""

# Sürüm 6: yarışma şartnameleri. Şartname ve maddeleri bir kütüphanede durur; birden çok
# drone aynı şartnameyi kullanabilir. Kullanılan şartname silinemez (RESTRICT).
SEMA_V6: Final[str] = """
CREATE TABLE IF NOT EXISTS sartnameler (
    kimlik           INTEGER PRIMARY KEY AUTOINCREMENT,
    ad               TEXT    NOT NULL,
    dosya_adi        TEXT    NOT NULL,
    saklanan_dosya   TEXT    NOT NULL,
    metin            TEXT    NOT NULL,
    yuklenme_zamani  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS sartname_maddeleri (
    kimlik           INTEGER PRIMARY KEY AUTOINCREMENT,
    sartname_kimlik  INTEGER NOT NULL REFERENCES sartnameler(kimlik) ON DELETE CASCADE,
    sira             INTEGER NOT NULL,
    madde_no         TEXT,
    sayfa            INTEGER,
    aciklama         TEXT    NOT NULL,
    buyukluk         TEXT    NOT NULL,
    sinir_turu       TEXT    NOT NULL,
    deger            REAL,
    sinif            TEXT    NOT NULL,
    onaylandi        INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS sartname_maddeleri_sartname ON sartname_maddeleri (sartname_kimlik, sira);

CREATE TABLE IF NOT EXISTS drone_sartnamesi (
    drone_kimlik     INTEGER PRIMARY KEY REFERENCES dronelar(kimlik) ON DELETE CASCADE,
    sartname_kimlik  INTEGER NOT NULL REFERENCES sartnameler(kimlik) ON DELETE RESTRICT
);
"""

# Sürüm 7: DroneLab Asistan sohbet geçmişi ve değişiklik önerileri. Sohbet drone'a bağlıdır
# (drone silinince silinir); drone_kimlik NULL ise ana sayfa/ayarlar "genel sohbet"idir.
# Öneri, kullanıcı "Uygula"ya basana kadar "bekliyor" durumunda kalır.
SEMA_V7: Final[str] = """
CREATE TABLE IF NOT EXISTS asistan_mesajlari (
    kimlik        INTEGER PRIMARY KEY AUTOINCREMENT,
    drone_kimlik  INTEGER REFERENCES dronelar(kimlik) ON DELETE CASCADE,
    rol           TEXT    NOT NULL,
    metin         TEXT    NOT NULL,
    model         TEXT,
    zaman         TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS asistan_mesajlari_drone ON asistan_mesajlari (drone_kimlik, kimlik);

CREATE TABLE IF NOT EXISTS asistan_onerileri (
    kimlik              INTEGER PRIMARY KEY AUTOINCREMENT,
    drone_kimlik        INTEGER NOT NULL REFERENCES dronelar(kimlik) ON DELETE CASCADE,
    mesaj_kimlik        INTEGER REFERENCES asistan_mesajlari(kimlik) ON DELETE CASCADE,
    gerekce             TEXT    NOT NULL,
    degisiklikler_json  TEXT    NOT NULL,
    sonuc_json          TEXT    NOT NULL,
    durum               TEXT    NOT NULL,
    zaman               TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS asistan_onerileri_drone ON asistan_onerileri (drone_kimlik, kimlik);
"""

# Sürüm numarası -> o sürüme geçmek için çalıştırılacak SQL. Yeni sürüm eklenince
# buraya bir satır eklenir; mevcut satırlar asla değiştirilmez.
GOCLER: Final[dict[int, str]] = {
    1: SEMA_V1, 2: SEMA_V2, 3: SEMA_V3, 4: SEMA_V4, 5: SEMA_V5, 6: SEMA_V6, 7: SEMA_V7,
}
SEMA_SURUMU: Final[int] = max(GOCLER)


class Veritabani:
    """
    SQLite dosyasına bağlantı açar ve şemanın var olduğundan emin olur.

    Parametreler:
        yol: Veritabanı dosyasının yolu; klasör yoksa oluşturulur.
    """

    def __init__(self, yol: Path) -> None:
        self.yol: Path = yol
        yol.parent.mkdir(parents=True, exist_ok=True)
        self._gunluk_kipini_ayarla()
        self._semayi_olustur()

    @contextmanager
    def baglanti(self) -> Iterator[sqlite3.Connection]:
        """
        Bir işlem (transaction) için bağlantı açar; hata yoksa kaydeder, varsa geri alır.

        Her işlemde yeni bağlantı açılır: FastAPI uçları farklı iş parçacıklarında
        çalıştığı için tek bir bağlantıyı paylaşmak güvenli değildir.

        Dönüş:
            Satırları sözlük gibi okunabilen sqlite3 bağlantısı.
        """
        bag = sqlite3.connect(self.yol, timeout=KILIT_BEKLEME_SN)
        bag.row_factory = sqlite3.Row
        # SQLite yabancı anahtarları varsayılan olarak denetlemez; drone silinince
        # şasi kaydının da silinmesi (CASCADE) için açılması gerekir.
        bag.execute("PRAGMA foreign_keys = ON")
        try:
            yield bag
            bag.commit()
        except Exception:
            bag.rollback()
            raise
        finally:
            bag.close()

    def _gunluk_kipini_ayarla(self) -> None:
        """
        Veritabanını WAL kipine alır (eşzamanlı okuma/yazma için).

        Kip dosyada saklandığı için her açılışta yeniden ayarlamak zararsızdır.
        """
        with self.baglanti() as bag:
            bag.execute(f"PRAGMA journal_mode = {GUNLUK_KIPI}")

    def _semayi_olustur(self) -> None:
        """
        Dosyanın şema sürümünü okur ve eksik sürümleri sırayla uygular.

        Yeni dosyada (sürüm 0) tüm sürümler, sürüm 1 dosyada yalnızca sürüm 2
        uygulanır. Her adımdan sonra sürüm numarası yazılır; böylece bir adım
        yarıda kalırsa bir sonraki açılışta o adımdan devam edilir.

        Hatalar:
            DroneProgramHatasi: Dosya programın daha yeni bir sürümüyle oluşturulmuşsa.
        """
        with self.baglanti() as bag:
            surum = bag.execute("PRAGMA user_version").fetchone()[0]
            if surum > SEMA_SURUMU:
                raise DroneProgramHatasi(
                    "Kayıt dosyası programın daha yeni bir sürümüyle oluşturulmuş. Lütfen programı güncelleyin."
                )
            for hedef in sorted(s for s in GOCLER if s > surum):
                bag.executescript(GOCLER[hedef])
                bag.execute(f"PRAGMA user_version = {hedef}")
