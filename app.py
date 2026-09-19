from flask import Flask, render_template, request, redirect, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from zoneinfo import ZoneInfo

app = Flask(__name__)

app.secret_key = "urfaekmek-gizli-anahtar"

ADMIN_KULLANICI = "admin"
ADMIN_SIFRE = "1234"


# ==================================================
# VERİTABANI
# ==================================================

def veritabani_baglan():
    conn = sqlite3.connect("urfaekmek.db")
    conn.row_factory = sqlite3.Row
    return conn


def veritabani_olustur():
    conn = veritabani_baglan()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS firin_basvurulari (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            firin_adi TEXT NOT NULL,
            yetkili TEXT NOT NULL,
            telefon TEXT NOT NULL,
            adres TEXT NOT NULL,
            saatler TEXT NOT NULL,
            bolgeler TEXT NOT NULL,
            kullanici_adi TEXT NOT NULL,
            sifre TEXT NOT NULL,
            durum TEXT DEFAULT 'Bekliyor'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS kurye_basvurulari (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ad_soyad TEXT NOT NULL,
            telefon TEXT NOT NULL,
            yas TEXT NOT NULL,
            ilce TEXT NOT NULL,
            arac TEXT NOT NULL,
            kullanici_adi TEXT NOT NULL,
            sifre TEXT NOT NULL,
            durum TEXT DEFAULT 'Bekliyor'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS siparisler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ad_soyad TEXT NOT NULL,
            telefon TEXT NOT NULL,
            adres TEXT NOT NULL,
            urunler TEXT NOT NULL,
            urun_toplami REAL NOT NULL,
            kurye_ucreti REAL NOT NULL,
            genel_toplam REAL NOT NULL,
            durum TEXT DEFAULT 'Bekliyor',
            kurye_id INTEGER,
            firin_id INTEGER
        )
    """)

    cursor.execute("PRAGMA table_info(siparisler)")
    sutunlar = [sutun["name"] for sutun in cursor.fetchall()]

    if "firin_id" not in sutunlar:
        cursor.execute("""
            ALTER TABLE siparisler
            ADD COLUMN firin_id INTEGER
        """)

    conn.commit()
    conn.close()


veritabani_olustur()


# ==================================================
# ÜRÜNLER
# ==================================================

def urunleri_getir():
    return [
        {
            "id": 1,
            "ad": "Tırnaklı Ekmek",
            "fiyat": 15,
            "emoji": "🥖"
        },
        {
            "id": 2,
            "ad": "Lavaş",
            "fiyat": 15,
            "emoji": "🫓"
        }
    ]


# ==================================================
# FIRIN
# ==================================================

def firin_getir(firin_id):
    conn = veritabani_baglan()

    firin = conn.execute("""
        SELECT *
        FROM firin_basvurulari
        WHERE id = ?
        AND durum = 'Onaylandı'
    """, (firin_id,)).fetchone()

    conn.close()

    return firin


def firin_acik_mi(saatler):

    if not saatler:
        return False

    try:
        saatler = saatler.strip()

        baslangic, bitis = saatler.split("-")

        baslangic = baslangic.strip().replace(".", ":")
        bitis = bitis.strip().replace(".", ":")

        bas_saat, bas_dakika = map(int, baslangic.split(":"))
        bit_saat, bit_dakika = map(int, bitis.split(":"))

        simdi = datetime.now(ZoneInfo("Europe/Istanbul"))

        mevcut_dakika = simdi.hour * 60 + simdi.minute
        baslangic_dakika = bas_saat * 60 + bas_dakika
        bitis_dakika = bit_saat * 60 + bit_dakika

        # 00:00 - 23:59 gibi normal çalışma saatleri
        if baslangic_dakika <= bitis_dakika:
            return baslangic_dakika <= mevcut_dakika <= bitis_dakika

        # Geceyi aşan saatler, örn. 22:00 - 06:00
        return mevcut_dakika >= baslangic_dakika or mevcut_dakika <= bitis_dakika

    except Exception:
        return False
# ==================================================
# ANA SAYFA
# ==================================================

@app.route("/")
def index():

    conn = veritabani_baglan()

    firinlar = conn.execute("""
        SELECT *
        FROM firin_basvurulari
        WHERE durum = 'Onaylandı'
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "index.html",
        firinlar=firinlar
    )


# ==================================================
# FIRIN SAYFASI
# ==================================================

@app.route("/firin/<int:firin_id>")
def firin(firin_id):

    firin = firin_getir(firin_id)

    if not firin:
        return "Fırın bulunamadı veya onaylanmamış.", 404

    urunler = urunleri_getir()

    acik = firin_acik_mi(
        firin["saatler"]
    )

    return render_template(
        "firin.html",
        firin=firin,
        urunler=urunler,
        firin_acik=acik
    )


# ==================================================
# SEPETE ÜRÜN EKLE
# ==================================================

@app.route(
    "/sepete-ekle/<int:firin_id>/<int:urun_id>",
    methods=["POST"]
)
def sepete_ekle(firin_id, urun_id):

    firin = firin_getir(firin_id)

    if not firin:
        return "Fırın bulunamadı.", 404

    if not firin_acik_mi(
        firin["saatler"]
    ):
        session["sepet_mesaj"] = (
            "Bu fırın şu anda kapalı."
        )

        return redirect(
            "/firin/" + str(firin_id)
        )

    urunler = urunleri_getir()

    urun = next(
        (
            u for u in urunler
            if u["id"] == urun_id
        ),
        None
    )

    if not urun:
        return "Ürün bulunamadı.", 404

    mevcut_firin_id = session.get(
        "sepet_firin_id"
    )

    if mevcut_firin_id is not None:

        if int(mevcut_firin_id) != int(firin_id):

            session["sepet_mesaj"] = (
                "Sepetinizde başka bir fırından "
                "ürün var. Önce sepeti temizleyin."
            )

            return redirect("/sepet")

    session["sepet_firin_id"] = firin_id

    sepet = session.get(
        "sepet",
        {}
    )

    urun_id_str = str(urun_id)

    if urun_id_str in sepet:
        sepet[urun_id_str] += 1
    else:
        sepet[urun_id_str] = 1

    session["sepet"] = sepet

    session.modified = True

    return redirect(
        "/firin/" + str(firin_id)
    )


# ==================================================
# SEPET
# ==================================================

@app.route("/sepet")
def sepet():

    sepet = session.get(
        "sepet",
        {}
    )

    toplam = 0

    sepet_urunleri = []

    urunler = urunleri_getir()

    for urun in urunler:

        urun_id = str(
            urun["id"]
        )

        if urun_id in sepet:

            adet = sepet[urun_id]

            ara_toplam = (
                urun["fiyat"] * adet
            )

            toplam += ara_toplam

            sepet_urunleri.append({
                "id": urun["id"],
                "ad": urun["ad"],
                "fiyat": urun["fiyat"],
                "emoji": urun["emoji"],
                "adet": adet,
                "ara_toplam": ara_toplam
            })

    kurye_ucreti = (
        30 if sepet_urunleri else 0
    )

    genel_toplam = (
        toplam + kurye_ucreti
    )

    firin = None

    firin_id = session.get(
        "sepet_firin_id"
    )

    if firin_id:
        firin = firin_getir(
            firin_id
        )

    mesaj = session.pop(
        "sepet_mesaj",
        None
    )

    return render_template(
        "sepet.html",
        sepet=sepet_urunleri,
        toplam=toplam,
        kurye_ucreti=kurye_ucreti,
        genel_toplam=genel_toplam,
        firin=firin,
        mesaj=mesaj
    )


# ==================================================
# SEPET ARTTIR
# ==================================================

@app.route(
    "/sepet/arttir/<int:urun_id>",
    methods=["POST"]
)
def sepet_arttir(urun_id):

    sepet = session.get(
        "sepet",
        {}
    )

    urun_id_str = str(urun_id)

    if urun_id_str in sepet:
        sepet[urun_id_str] += 1

    session["sepet"] = sepet

    session.modified = True

    return redirect("/sepet")


# ==================================================
# SEPET AZALT
# ==================================================

@app.route(
    "/sepet/azalt/<int:urun_id>",
    methods=["POST"]
)
def sepet_azalt(urun_id):

    sepet = session.get(
        "sepet",
        {}
    )

    urun_id_str = str(urun_id)

    if urun_id_str in sepet:

        sepet[urun_id_str] -= 1

        if sepet[urun_id_str] <= 0:
            del sepet[urun_id_str]

    session["sepet"] = sepet

    session.modified = True

    return redirect("/sepet")


# ==================================================
# SEPETTEN SİL
# ==================================================

@app.route(
    "/sepet/sil/<int:urun_id>",
    methods=["POST"]
)
def sepet_sil(urun_id):

    sepet = session.get(
        "sepet",
        {}
    )

    urun_id_str = str(urun_id)

    if urun_id_str in sepet:
        del sepet[urun_id_str]

    session["sepet"] = sepet

    session.modified = True

    return redirect("/sepet")


# ==================================================
# SEPETİ TEMİZLE
# ==================================================

@app.route(
    "/sepet/temizle",
    methods=["POST"]
)
def sepet_temizle():

    session.pop(
        "sepet",
        None
    )

    session.pop(
        "sepet_firin_id",
        None
    )

    session.pop(
        "sepet_mesaj",
        None
    )

    return redirect("/sepet")


# ==================================================
# SİPARİŞ VER
# ==================================================

@app.route(
    "/siparis-ver",
    methods=["GET", "POST"]
)
def siparis_ver():

    sepet = session.get(
        "sepet",
        {}
    )

    if not sepet:
        return redirect("/sepet")

    firin_id = session.get(
        "sepet_firin_id"
    )

    if not firin_id:
        return redirect("/sepet")

    firin = firin_getir(
        firin_id
    )

    if not firin:
        return "Fırın bulunamadı.", 404

    hata = None

    if request.method == "POST":

        ad_soyad = request.form.get(
            "ad_soyad",
            ""
        ).strip()

        telefon = request.form.get(
            "telefon",
            ""
        ).strip()

        adres = request.form.get(
            "adres",
            ""
        ).strip()

        if not ad_soyad or not telefon or not adres:

            hata = (
                "Lütfen bütün alanları doldurun."
            )

        elif not firin_acik_mi(
            firin["saatler"]
        ):

            hata = (
                "Bu fırın şu anda kapalı. "
                "Sipariş veremezsiniz."
            )

        else:

            urunler = urunleri_getir()

            toplam = 0

            urun_listesi = []

            for urun in urunler:

                urun_id_str = str(
                    urun["id"]
                )

                if urun_id_str in sepet:

                    adet = sepet[
                        urun_id_str
                    ]

                    ara_toplam = (
                        urun["fiyat"] * adet
                    )

                    toplam += ara_toplam

                    urun_listesi.append(
                        f"{urun['emoji']} "
                        f"{urun['ad']} x{adet}"
                    )

            kurye_ucreti = 30

            genel_toplam = (
                toplam + kurye_ucreti
            )

            urunler_yazi = ", ".join(
                urun_listesi
            )

            conn = veritabani_baglan()

            conn.execute("""
                INSERT INTO siparisler
                (
                    ad_soyad,
                    telefon,
                    adres,
                    urunler,
                    urun_toplami,
                    kurye_ucreti,
                    genel_toplam,
                    durum,
                    kurye_id,
                    firin_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ad_soyad,
                telefon,
                adres,
                urunler_yazi,
                toplam,
                kurye_ucreti,
                genel_toplam,
                "Bekliyor",
                None,
                firin_id
            ))

            conn.commit()
            conn.close()

            session.pop(
                "sepet",
                None
            )

            session.pop(
                "sepet_firin_id",
                None
            )

            return render_template(
                "siparis_basarili.html",
                ad_soyad=ad_soyad,
                genel_toplam=genel_toplam
            )

    toplam = 0

    for urun in urunleri_getir():

        urun_id_str = str(
            urun["id"]
        )

        if urun_id_str in sepet:

            toplam += (
                urun["fiyat"]
                * sepet[urun_id_str]
            )

    kurye_ucreti = 30

    genel_toplam = (
        toplam + kurye_ucreti
    )

    return render_template(
        "siparis_ver.html",
        firin=firin,
        toplam=toplam,
        kurye_ucreti=kurye_ucreti,
        genel_toplam=genel_toplam,
        hata=hata
    )


# ==================================================
# FIRIN BAŞVURUSU
# ==================================================

@app.route(
    "/firinci",
    methods=["GET", "POST"]
)
def firinci():

    mesaj = None

    if request.method == "POST":

        firin_adi = request.form.get(
            "firin_adi",
            ""
        ).strip()

        yetkili = request.form.get(
            "yetkili",
            ""
        ).strip()

        telefon = request.form.get(
            "telefon",
            ""
        ).strip()

        adres = request.form.get(
            "adres",
            ""
        ).strip()

        saatler = request.form.get(
            "saatler",
            ""
        ).strip()

        bolgeler = request.form.get(
            "bolgeler",
            ""
        ).strip()

        kullanici_adi = request.form.get(
            "kullanici_adi",
            ""
        ).strip()

        sifre = request.form.get(
            "sifre",
            ""
        ).strip()

        if not all([
            firin_adi,
            yetkili,
            telefon,
            adres,
            saatler,
            bolgeler,
            kullanici_adi,
            sifre
        ]):

            mesaj = (
                "Lütfen bütün alanları doldurun."
            )

        else:

            conn = veritabani_baglan()

            mevcut = conn.execute("""
                SELECT id
                FROM firin_basvurulari
                WHERE kullanici_adi = ?
            """, (
                kullanici_adi,
            )).fetchone()

            if mevcut:

                mesaj = (
                    "Bu kullanıcı adı zaten kullanılıyor."
                )

            else:

                sifre_hash = generate_password_hash(
                    sifre
                )

                conn.execute("""
                    INSERT INTO firin_basvurulari
                    (
                        firin_adi,
                        yetkili,
                        telefon,
                        adres,
                        saatler,
                        bolgeler,
                        kullanici_adi,
                        sifre,
                        durum
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    firin_adi,
                    yetkili,
                    telefon,
                    adres,
                    saatler,
                    bolgeler,
                    kullanici_adi,
                    sifre_hash,
                    "Bekliyor"
                ))

                conn.commit()

                mesaj = (
                    "Başvurunuz alındı. "
                    "Admin onayından sonra "
                    "giriş yapabilirsiniz."
                )

            conn.close()

    return render_template(
        "firinci.html",
        mesaj=mesaj
    )


# ==================================================
# FIRIN GİRİŞ
# ==================================================

@app.route(
    "/firinci-giris",
    methods=["GET", "POST"]
)
def firinci_giris():

    hata = None

    if request.method == "POST":

        kullanici_adi = request.form.get(
            "kullanici_adi",
            ""
        ).strip()

        sifre = request.form.get(
            "sifre",
            ""
        ).strip()

        conn = veritabani_baglan()

        firin = conn.execute("""
            SELECT *
            FROM firin_basvurulari
            WHERE kullanici_adi = ?
            AND durum = 'Onaylandı'
        """, (
            kullanici_adi,
        )).fetchone()

        conn.close()

        if firin and check_password_hash(
            firin["sifre"],
            sifre
        ):

            session["firinci_id"] = firin["id"]

            return redirect(
                "/firinci-panel"
            )

        hata = (
            "Kullanıcı adı veya şifre yanlış."
        )

    return render_template(
        "firinci_giris.html",
        hata=hata
    )


# ==================================================
# FIRIN PANELİ
# ==================================================

@app.route("/firinci-panel")
def firinci_panel():

    firin_id = session.get(
        "firinci_id"
    )

    if not firin_id:
        return redirect(
            "/firinci-giris"
        )

    conn = veritabani_baglan()

    firin = conn.execute("""
        SELECT *
        FROM firin_basvurulari
        WHERE id = ?
        AND durum = 'Onaylandı'
    """, (
        firin_id,
    )).fetchone()

    siparisler = conn.execute("""
        SELECT *
        FROM siparisler
        WHERE firin_id = ?
        ORDER BY id DESC
    """, (
        firin_id,
    )).fetchall()

    conn.close()

    if not firin:

        session.pop(
            "firinci_id",
            None
        )

        return redirect(
            "/firinci-giris"
        )

    return render_template(
        "firinci_panel.html",
        firin=firin,
        siparisler=siparisler
    )


# ==================================================
# FIRIN ÇIKIŞ
# ==================================================

@app.route("/firinci-cikis")
def firinci_cikis():

    session.pop(
        "firinci_id",
        None
    )

    return redirect(
        "/firinci-giris"
    )


# ==================================================
# KURYE BAŞVURUSU
# ==================================================

@app.route(
    "/kurye",
    methods=["GET", "POST"]
)
def kurye():

    mesaj = None

    if request.method == "POST":

        ad_soyad = request.form.get(
            "ad_soyad",
            ""
        ).strip()

        telefon = request.form.get(
            "telefon",
            ""
        ).strip()

        yas = request.form.get(
            "yas",
            ""
        ).strip()

        ilce = request.form.get(
            "ilce",
            ""
        ).strip()

        arac = request.form.get(
            "arac",
            ""
        ).strip()

        kullanici_adi = request.form.get(
            "kullanici_adi",
            ""
        ).strip()

        sifre = request.form.get(
            "sifre",
            ""
        ).strip()

        if not all([
            ad_soyad,
            telefon,
            yas,
            ilce,
            arac,
            kullanici_adi,
            sifre
        ]):

            mesaj = (
                "Lütfen bütün alanları doldurun."
            )

        else:

            conn = veritabani_baglan()

            mevcut = conn.execute("""
                SELECT id
                FROM kurye_basvurulari
                WHERE kullanici_adi = ?
            """, (
                kullanici_adi,
            )).fetchone()

            if mevcut:

                mesaj = (
                    "Bu kullanıcı adı zaten kullanılıyor."
                )

            else:

                sifre_hash = generate_password_hash(
                    sifre
                )

                conn.execute("""
                    INSERT INTO kurye_basvurulari
                    (
                        ad_soyad,
                        telefon,
                        yas,
                        ilce,
                        arac,
                        kullanici_adi,
                        sifre,
                        durum
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    ad_soyad,
                    telefon,
                    yas,
                    ilce,
                    arac,
                    kullanici_adi,
                    sifre_hash,
                    "Bekliyor"
                ))

                conn.commit()

                mesaj = (
                    "Kurye başvurunuz alındı. "
                    "Admin onayından sonra "
                    "giriş yapabilirsiniz."
                )

            conn.close()

    return render_template(
        "kurye.html",
        mesaj=mesaj
    )


# ==================================================
# KURYE GİRİŞ
# ==================================================

@app.route(
    "/kurye-giris",
    methods=["GET", "POST"]
)
def kurye_giris():

    hata = None

    if request.method == "POST":

        kullanici_adi = request.form.get(
            "kullanici_adi",
            ""
        ).strip()

        sifre = request.form.get(
            "sifre",
            ""
        ).strip()

        conn = veritabani_baglan()

        kurye = conn.execute("""
            SELECT *
            FROM kurye_basvurulari
            WHERE kullanici_adi = ?
            AND durum = 'Onaylandı'
        """, (
            kullanici_adi,
        )).fetchone()

        conn.close()

        if kurye and check_password_hash(
            kurye["sifre"],
            sifre
        ):

            session["kurye_id"] = kurye["id"]

            return redirect(
                "/kurye-panel"
            )

        hata = (
            "Kullanıcı adı veya şifre yanlış."
        )

    return render_template(
        "kurye_giris.html",
        hata=hata
    )


# ==================================================
# KURYE PANELİ
# ==================================================

@app.route("/kurye-panel")
def kurye_panel():

    kurye_id = session.get(
        "kurye_id"
    )

    if not kurye_id:
        return redirect(
            "/kurye-giris"
        )

    conn = veritabani_baglan()

    kurye = conn.execute("""
        SELECT *
        FROM kurye_basvurulari
        WHERE id = ?
        AND durum = 'Onaylandı'
    """, (
        kurye_id,
    )).fetchone()

    bekleyen_siparisler = conn.execute("""
        SELECT
            s.*,
            f.firin_adi
        FROM siparisler s
        LEFT JOIN firin_basvurulari f
            ON s.firin_id = f.id
        WHERE s.kurye_id IS NULL
        AND s.durum = 'Bekliyor'
        ORDER BY s.id DESC
    """).fetchall()

    benim_siparislerim = conn.execute("""
        SELECT
            s.*,
            f.firin_adi
        FROM siparisler s
        LEFT JOIN firin_basvurulari f
            ON s.firin_id = f.id
        WHERE s.kurye_id = ?
        ORDER BY s.id DESC
    """, (
        kurye_id,
    )).fetchall()

    conn.close()

    if not kurye:

        session.pop(
            "kurye_id",
            None
        )

        return redirect(
            "/kurye-giris"
        )

    return render_template(
        "kurye_panel.html",
        kurye=kurye,
        bekleyen_siparisler=bekleyen_siparisler,
        benim_siparislerim=benim_siparislerim
    )


# ==================================================
# KURYE SİPARİŞ AL
# ==================================================

@app.route(
    "/kurye/siparis-al/<int:siparis_id>",
    methods=["POST"]
)
def siparis_al(siparis_id):

    kurye_id = session.get(
        "kurye_id"
    )

    if not kurye_id:
        return redirect(
            "/kurye-giris"
        )

    conn = veritabani_baglan()

    siparis = conn.execute("""
        SELECT *
        FROM siparisler
        WHERE id = ?
        AND kurye_id IS NULL
        AND durum = 'Bekliyor'
    """, (
        siparis_id,
    )).fetchone()

    if siparis:

        conn.execute("""
            UPDATE siparisler
            SET kurye_id = ?,
                durum = 'Kurye Aldı'
            WHERE id = ?
            AND kurye_id IS NULL
        """, (
            kurye_id,
            siparis_id
        ))

        conn.commit()

    conn.close()

    return redirect(
        "/kurye-panel"
    )


# ==================================================
# KURYE SİPARİŞ DURUMU
# ==================================================

@app.route(
    "/kurye/siparis-durum/<int:siparis_id>/<durum>",
    methods=["POST"]
)
def kurye_siparis_durum(
    siparis_id,
    durum
):

    kurye_id = session.get(
        "kurye_id"
    )

    if not kurye_id:
        return redirect(
            "/kurye-giris"
        )

    izinli_durumlar = [
        "Hazırlanıyor",
        "Yolda",
        "Teslim Edildi"
    ]

    if durum not in izinli_durumlar:
        return redirect(
            "/kurye-panel"
        )

    conn = veritabani_baglan()

    conn.execute("""
        UPDATE siparisler
        SET durum = ?
        WHERE id = ?
        AND kurye_id = ?
    """, (
        durum,
        siparis_id,
        kurye_id
    ))

    conn.commit()
    conn.close()

    return redirect(
        "/kurye-panel"
    )


# ==================================================
# KURYE ÇIKIŞ
# ==================================================

@app.route("/kurye-cikis")
def kurye_cikis():

    session.pop(
        "kurye_id",
        None
    )

    return redirect(
        "/kurye-giris"
    )


# ==================================================
# ADMIN GİRİŞ
# ==================================================

@app.route(
    "/admin",
    methods=["GET", "POST"]
)
def admin():

    hata = None

    if request.method == "POST":

        kullanici_adi = request.form.get(
            "kullanici_adi",
            ""
        ).strip()

        sifre = request.form.get(
            "sifre",
            ""
        ).strip()

        if (
            kullanici_adi == ADMIN_KULLANICI
            and sifre == ADMIN_SIFRE
        ):

            session["admin"] = True

            return redirect(
                "/admin-panel"
            )

        hata = (
            "Admin kullanıcı adı veya şifre yanlış."
        )

    return render_template(
        "admin_giris.html",
        hata=hata
    )


# ==================================================
# ADMIN PANELİ
# ==================================================

@app.route("/admin-panel")
def admin_panel():

    if not session.get("admin"):
        return redirect("/admin")

    conn = veritabani_baglan()

    firin_basvurulari = conn.execute("""
        SELECT *
        FROM firin_basvurulari
        ORDER BY id DESC
    """).fetchall()

    kurye_basvurulari = conn.execute("""
        SELECT *
        FROM kurye_basvurulari
        ORDER BY id DESC
    """).fetchall()

    siparisler = conn.execute("""
        SELECT
            s.*,
            f.firin_adi
        FROM siparisler s
        LEFT JOIN firin_basvurulari f
            ON s.firin_id = f.id
        ORDER BY s.id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "admin.html",
        firin_basvurulari=firin_basvurulari,
        kurye_basvurulari=kurye_basvurulari,
        siparisler=siparisler
    )


# ==================================================
# ADMIN FIRIN ONAYLA
# ==================================================
@app.route("/admin/firin-onayla/<int:firin_id>")
def firin_onayla(firin_id):

    conn = veritabani_baglan()

    conn.execute("""
        UPDATE firin_basvurulari
        SET durum = 'Onaylandı'
        WHERE id = ?
    """, (firin_id,))

    conn.commit()
    conn.close()

    return redirect("/admin-panel")


@app.route("/admin/firin-reddet/<int:firin_id>")
def firin_reddet(firin_id):

    conn = veritabani_baglan()

    conn.execute("""
        UPDATE firin_basvurulari
        SET durum = 'Reddedildi'
        WHERE id = ?
    """, (firin_id,))

    conn.commit()
    conn.close()

    return redirect("/admin-panel")

# ==================================================
# ADMIN FIRIN KALDIR
# ==================================================

@app.route(
    "/admin/firin-kaldir/<int:firin_id>",
    methods=["POST"]
)
def firin_kaldir(firin_id):

    if not session.get("admin"):
        return redirect("/admin")

    conn = veritabani_baglan()

    conn.execute("""
        DELETE FROM firin_basvurulari
        WHERE id = ?
    """, (
        firin_id,
    ))

    conn.commit()
    conn.close()

    return redirect(
        "/admin-panel"
    )


# ==================================================
# ADMIN KURYE ONAYLA
# ==================================================

@app.route("/admin/kurye-onayla/<int:kurye_id>")
def kurye_onayla(kurye_id):

    if not session.get("admin"):
        return redirect("/admin")

    conn = veritabani_baglan()

    conn.execute("""
        UPDATE kurye_basvurulari
        SET durum = 'Onaylandı'
        WHERE id = ?
    """, (kurye_id,))

    conn.commit()
    conn.close()

    return redirect("/admin-panel")


# ==================================================
# ADMIN KURYE REDDET
# ==================================================

@app.route(
    "/admin/kurye-reddet/<int:kurye_id>",
    methods=["POST"]
)
def kurye_reddet(kurye_id):

    if not session.get("admin"):
        return redirect("/admin")

    conn = veritabani_baglan()

    conn.execute("""
        UPDATE kurye_basvurulari
        SET durum = 'Reddedildi'
        WHERE id = ?
    """, (
        kurye_id,
    ))

    conn.commit()
    conn.close()

    return redirect(
        "/admin-panel"
    )


# ==================================================
# ADMIN ÇIKIŞ
# ==================================================

@app.route("/admin-cikis")
def admin_cikis():

    session.pop(
        "admin",
        None
    )

    return redirect(
        "/admin"
    )


# ==================================================
# UYGULAMAYI ÇALIŞTIR
# ==================================================

if __name__ == "__main__":
    app.run(debug=True)
