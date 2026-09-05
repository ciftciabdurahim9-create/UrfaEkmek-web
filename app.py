from flask import Flask, render_template, request, redirect, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

DATABASE = "urfaekmek.db"

app.secret_key = "urfaekmek-gizli-anahtar"

ADMIN_KULLANICI = "admin"
ADMIN_SIFRE = "1234"


def veritabani_olustur():

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # =========================
    # FIRIN TABLOSU
    # =========================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS firin_basvurulari (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            firin_adi TEXT NOT NULL,
            yetkili TEXT NOT NULL,
            telefon TEXT NOT NULL,
            adres TEXT NOT NULL,
            saatler TEXT NOT NULL,
            bolgeler TEXT NOT NULL,
            kullanici_adi TEXT UNIQUE,
            sifre TEXT,
            durum TEXT DEFAULT 'Bekliyor'
        )
    """)

    # Eski veritabanına yeni sütunları ekle

    cursor.execute("PRAGMA table_info(firin_basvurulari)")

    firin_sutunlari = [
        sutun[1]
        for sutun in cursor.fetchall()
    ]

    if "kullanici_adi" not in firin_sutunlari:
        cursor.execute("""
            ALTER TABLE firin_basvurulari
            ADD COLUMN kullanici_adi TEXT
        """)

    if "sifre" not in firin_sutunlari:
        cursor.execute("""
            ALTER TABLE firin_basvurulari
            ADD COLUMN sifre TEXT
        """)


    # =========================
    # KURYE TABLOSU
    # =========================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS kurye_basvurulari (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ad_soyad TEXT NOT NULL,
            telefon TEXT NOT NULL,
            yas TEXT NOT NULL,
            ilce TEXT NOT NULL,
            arac TEXT NOT NULL,
            kullanici_adi TEXT UNIQUE,
            sifre TEXT,
            durum TEXT DEFAULT 'Bekliyor'
        )
    """)

    cursor.execute("PRAGMA table_info(kurye_basvurulari)")

    kurye_sutunlari = [
        sutun[1]
        for sutun in cursor.fetchall()
    ]

    if "kullanici_adi" not in kurye_sutunlari:
        cursor.execute("""
            ALTER TABLE kurye_basvurulari
            ADD COLUMN kullanici_adi TEXT
        """)

    if "sifre" not in kurye_sutunlari:
        cursor.execute("""
            ALTER TABLE kurye_basvurulari
            ADD COLUMN sifre TEXT
        """)


    # =========================
    # SİPARİŞ TABLOSU
    # =========================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS siparisler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ad_soyad TEXT NOT NULL,
            telefon TEXT NOT NULL,
            adres TEXT NOT NULL,
            urunler TEXT NOT NULL,
            urun_toplami INTEGER NOT NULL,
            kurye_ucreti INTEGER NOT NULL,
            genel_toplam INTEGER NOT NULL,
            durum TEXT DEFAULT 'Bekliyor',
            kurye_id INTEGER
        )
    """)

    cursor.execute("PRAGMA table_info(siparisler)")

    siparis_sutunlari = [
        sutun[1]
        for sutun in cursor.fetchall()
    ]

    if "kurye_id" not in siparis_sutunlari:
        cursor.execute("""
            ALTER TABLE siparisler
            ADD COLUMN kurye_id INTEGER
        """)

    conn.commit()
    conn.close()


# ==================================================
# ANA SAYFA
# ==================================================

@app.route("/")
def ana_sayfa():

    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM firin_basvurulari
        WHERE durum = 'Onaylandı'
        ORDER BY id DESC
    """)

    firinlar = cursor.fetchall()

    conn.close()

    return render_template(
        "index.html",
        firinlar=firinlar
    )


# ==================================================
# FIRIN SAYFASI
# ==================================================

@app.route("/firin/<int:id>")
def firin(id):

    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM firin_basvurulari
        WHERE id = ?
        AND durum = 'Onaylandı'
    """, (id,))

    firin_bilgisi = cursor.fetchone()

    conn.close()

    if not firin_bilgisi:
        return "Fırın bulunamadı."

    urunler = [
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

    return render_template(
        "firin.html",
        firin=firin_bilgisi,
        urunler=urunler
    )


# ==================================================
# SEPETE EKLE
# ==================================================

@app.route("/sepete-ekle/<int:urun_id>", methods=["POST"])
def sepete_ekle(urun_id):

    urunler = {
        1: {
            "id": 1,
            "ad": "Tırnaklı Ekmek",
            "fiyat": 15,
            "emoji": "🥖"
        },
        2: {
            "id": 2,
            "ad": "Lavaş",
            "fiyat": 15,
            "emoji": "🫓"
        }
    }

    if urun_id not in urunler:
        return "Ürün bulunamadı."

    sepet = session.get("sepet", {})

    urun_id_str = str(urun_id)

    if urun_id_str in sepet:

        sepet[urun_id_str]["adet"] += 1

    else:

        urun = urunler[urun_id]

        sepet[urun_id_str] = {
            "ad": urun["ad"],
            "fiyat": urun["fiyat"],
            "emoji": urun["emoji"],
            "adet": 1
        }

    session["sepet"] = sepet

    return redirect("/sepet")


# ==================================================
# SEPET
# ==================================================

@app.route("/sepet")
def sepet():

    sepet = session.get("sepet", {})

    toplam = 0

    for urun in sepet.values():

        toplam += (
            urun["fiyat"]
            * urun["adet"]
        )

    kurye_ucreti = 30 if sepet else 0

    genel_toplam = toplam + kurye_ucreti

    return render_template(
        "sepet.html",
        sepet=sepet,
        toplam=toplam,
        kurye_ucreti=kurye_ucreti,
        genel_toplam=genel_toplam
    )


# ==================================================
# SEPET ARTIR
# ==================================================

@app.route("/sepet/arttir/<urun_id>", methods=["POST"])
def sepet_arttir(urun_id):

    sepet = session.get("sepet", {})

    if urun_id in sepet:
        sepet[urun_id]["adet"] += 1

    session["sepet"] = sepet

    return redirect("/sepet")


# ==================================================
# SEPET AZALT
# ==================================================

@app.route("/sepet/azalt/<urun_id>", methods=["POST"])
def sepet_azalt(urun_id):

    sepet = session.get("sepet", {})

    if urun_id in sepet:

        sepet[urun_id]["adet"] -= 1

        if sepet[urun_id]["adet"] <= 0:
            del sepet[urun_id]

    session["sepet"] = sepet

    return redirect("/sepet")


# ==================================================
# SEPET SİL
# ==================================================

@app.route("/sepet/sil/<urun_id>", methods=["POST"])
def sepet_sil(urun_id):

    sepet = session.get("sepet", {})

    if urun_id in sepet:
        del sepet[urun_id]

    session["sepet"] = sepet

    return redirect("/sepet")


# ==================================================
# SEPET TEMİZLE
# ==================================================

@app.route("/sepet/temizle", methods=["POST"])
def sepet_temizle():

    session["sepet"] = {}

    return redirect("/sepet")


# ==================================================
# SİPARİŞ VER
# ==================================================

@app.route("/siparis-ver", methods=["GET", "POST"])
def siparis_ver():

    sepet = session.get("sepet", {})

    if not sepet:
        return redirect("/sepet")

    toplam = 0

    for urun in sepet.values():

        toplam += (
            urun["fiyat"]
            * urun["adet"]
        )

    kurye_ucreti = 30

    genel_toplam = toplam + kurye_ucreti

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

            return render_template(
                "siparis_ver.html",
                hata="Lütfen bütün alanları doldurun.",
                toplam=toplam,
                kurye_ucreti=kurye_ucreti,
                genel_toplam=genel_toplam
            )

        urun_listesi = []

        for urun in sepet.values():

            urun_listesi.append(
                f"{urun['emoji']} "
                f"{urun['ad']} x "
                f"{urun['adet']}"
            )

        urunler = ", ".join(urun_listesi)

        conn = sqlite3.connect(DATABASE)

        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO siparisler
            (
                ad_soyad,
                telefon,
                adres,
                urunler,
                urun_toplami,
                kurye_ucreti,
                genel_toplam,
                durum
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ad_soyad,
            telefon,
            adres,
            urunler,
            toplam,
            kurye_ucreti,
            genel_toplam,
            "Bekliyor"
        ))

        conn.commit()
        conn.close()

        session["sepet"] = {}

        return render_template(
            "siparis_basarili.html",
            genel_toplam=genel_toplam
        )

    return render_template(
        "siparis_ver.html",
        hata="",
        toplam=toplam,
        kurye_ucreti=kurye_ucreti,
        genel_toplam=genel_toplam
    )


# ==================================================
# FIRINCI BAŞVURUSU
# ==================================================

@app.route("/firinci", methods=["GET", "POST"])
def firinci():

    mesaj = ""

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
        )

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

            mesaj = "Lütfen bütün alanları doldurun."

            return render_template(
                "firinci.html",
                mesaj=mesaj
            )

        if len(sifre) < 6:

            mesaj = "Şifre en az 6 karakter olmalıdır."

            return render_template(
                "firinci.html",
                mesaj=mesaj
            )

        sifre_hash = generate_password_hash(sifre)

        conn = sqlite3.connect(DATABASE)

        cursor = conn.cursor()

        try:

            cursor.execute("""
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
                "Fırın başvurunuz alındı! "
                "Admin onayından sonra giriş yapabilirsiniz. 🥖"
            )

        except sqlite3.IntegrityError:

            mesaj = (
                "Bu kullanıcı adı zaten kullanılıyor."
            )

        conn.close()

    return render_template(
        "firinci.html",
        mesaj=mesaj
    )


# ==================================================
# FIRINCI GİRİŞ
# ==================================================

@app.route("/firinci-giris", methods=["GET", "POST"])
def firinci_giris():

    if session.get("firin_id"):

        return redirect(
            "/firinci-panel"
        )

    hata = ""

    if request.method == "POST":

        kullanici_adi = request.form.get(
            "kullanici_adi",
            ""
        ).strip()

        sifre = request.form.get(
            "sifre",
            ""
        )

        conn = sqlite3.connect(DATABASE)

        conn.row_factory = sqlite3.Row

        cursor = conn.cursor()

        cursor.execute("""
            SELECT *
            FROM firin_basvurulari
            WHERE kullanici_adi = ?
            AND durum = 'Onaylandı'
        """, (
            kullanici_adi,
        ))

        firin = cursor.fetchone()

        conn.close()

        if firin and firin["sifre"]:

            if check_password_hash(
                firin["sifre"],
                sifre
            ):

                session["firin_id"] = firin["id"]

                session["firin_adi"] = (
                    firin["firin_adi"]
                )

                return redirect(
                    "/firinci-panel"
                )

        hata = (
            "Kullanıcı adı veya şifre yanlış "
            "ya da hesabınız henüz onaylanmadı."
        )

    return render_template(
        "firinci_giris.html",
        hata=hata
    )


# ==================================================
# FIRINCI PANELİ
# ==================================================

@app.route("/firinci-panel")
def firinci_panel():

    firin_id = session.get(
        "firin_id"
    )

    if not firin_id:

        return redirect(
            "/firinci-giris"
        )

    conn = sqlite3.connect(DATABASE)

    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM firin_basvurulari
        WHERE id = ?
    """, (
        firin_id,
    ))

    firin = cursor.fetchone()

    conn.close()

    if not firin:

        session.pop("firin_id", None)
        session.pop("firin_adi", None)

        return redirect(
            "/firinci-giris"
        )

    return render_template(
        "firinci_panel.html",
        firin=firin
    )


# ==================================================
# FIRINCI ÇIKIŞ
# ==================================================

@app.route("/firinci-cikis")
def firinci_cikis():

    session.pop(
        "firin_id",
        None
    )

    session.pop(
        "firin_adi",
        None
    )

    return redirect(
        "/firinci-giris"
    )


# ==================================================
# KURYE BAŞVURUSU
# ==================================================

@app.route("/kurye", methods=["GET", "POST"])
def kurye():

    mesaj = ""

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
        )

        if not all([
            ad_soyad,
            telefon,
            yas,
            ilce,
            arac,
            kullanici_adi,
            sifre
        ]):

            mesaj = "Lütfen bütün alanları doldurun."

            return render_template(
                "kurye.html",
                mesaj=mesaj
            )

        try:

            yas_sayi = int(yas)

            if yas_sayi < 18:

                mesaj = (
                    "Kurye başvurusu için "
                    "en az 18 yaşında olmalısınız."
                )

                return render_template(
                    "kurye.html",
                    mesaj=mesaj
                )

        except ValueError:

            mesaj = "Geçerli bir yaş girin."

            return render_template(
                "kurye.html",
                mesaj=mesaj
            )

        if len(sifre) < 6:

            mesaj = "Şifre en az 6 karakter olmalıdır."

            return render_template(
                "kurye.html",
                mesaj=mesaj
            )

        sifre_hash = generate_password_hash(sifre)

        conn = sqlite3.connect(DATABASE)

        cursor = conn.cursor()

        try:

            cursor.execute("""
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
                "Kurye başvurunuz alındı! "
                "Admin onayından sonra giriş yapabilirsiniz. 🛵"
            )

        except sqlite3.IntegrityError:

            mesaj = (
                "Bu kullanıcı adı zaten kullanılıyor."
            )

        conn.close()

    return render_template(
        "kurye.html",
        mesaj=mesaj
    )


# ==================================================
# KURYE GİRİŞ
# ==================================================

@app.route("/kurye-giris", methods=["GET", "POST"])
def kurye_giris():

    if session.get("kurye_id"):

        return redirect(
            "/kurye-panel"
        )

    hata = ""

    if request.method == "POST":

        kullanici_adi = request.form.get(
            "kullanici_adi",
            ""
        ).strip()

        sifre = request.form.get(
            "sifre",
            ""
        )

        conn = sqlite3.connect(DATABASE)

        conn.row_factory = sqlite3.Row

        cursor = conn.cursor()

        cursor.execute("""
            SELECT *
            FROM kurye_basvurulari
            WHERE kullanici_adi = ?
            AND durum = 'Onaylandı'
        """, (
            kullanici_adi,
        ))

        kurye = cursor.fetchone()

        conn.close()

        if kurye and kurye["sifre"]:

            if check_password_hash(
                kurye["sifre"],
                sifre
            ):

                session["kurye_id"] = kurye["id"]

                session["kurye_adi"] = (
                    kurye["ad_soyad"]
                )

                return redirect(
                    "/kurye-panel"
                )

        hata = (
            "Kullanıcı adı veya şifre yanlış "
            "ya da hesabınız henüz onaylanmadı."
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

    conn = sqlite3.connect(DATABASE)

    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM siparisler
        WHERE kurye_id IS NULL
        AND durum = 'Bekliyor'
        ORDER BY id DESC
    """)

    bekleyen_siparisler = cursor.fetchall()

    cursor.execute("""
        SELECT *
        FROM siparisler
        WHERE kurye_id = ?
        ORDER BY id DESC
    """, (
        kurye_id,
    ))

    benim_siparislerim = cursor.fetchall()

    conn.close()

    return render_template(
        "kurye_panel.html",
        kurye_adi=session.get(
            "kurye_adi"
        ),
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
def kurye_siparis_al(siparis_id):

    kurye_id = session.get(
        "kurye_id"
    )

    if not kurye_id:

        return redirect(
            "/kurye-giris"
        )

    conn = sqlite3.connect(DATABASE)

    cursor = conn.cursor()

    cursor.execute("""
        UPDATE siparisler
        SET kurye_id = ?,
            durum = 'Kurye Aldı'
        WHERE id = ?
        AND kurye_id IS NULL
        AND durum = 'Bekliyor'
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

        return "Geçersiz durum."

    conn = sqlite3.connect(DATABASE)

    cursor = conn.cursor()

    cursor.execute("""
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

    session.pop(
        "kurye_adi",
        None
    )

    return redirect(
        "/kurye-giris"
    )


# ==================================================
# ADMIN GİRİŞ
# ==================================================

@app.route("/admin", methods=["GET", "POST"])
def admin():

    if session.get("admin_giris"):

        return admin_paneli()

    hata = ""

    if request.method == "POST":

        kullanici = request.form.get(
            "kullanici",
            ""
        )

        sifre = request.form.get(
            "sifre",
            ""
        )

        if (
            kullanici == ADMIN_KULLANICI
            and
            sifre == ADMIN_SIFRE
        ):

            session["admin_giris"] = True

            return redirect(
                "/admin"
            )

        hata = (
            "❌ Kullanıcı adı veya şifre yanlış!"
        )

    return render_template(
        "admin_giris.html",
        hata=hata
    )


# ==================================================
# ADMIN PANELİ
# ==================================================

def admin_paneli():

    conn = sqlite3.connect(DATABASE)

    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM firin_basvurulari
        ORDER BY id DESC
    """)

    firinlar = cursor.fetchall()

    cursor.execute("""
        SELECT *
        FROM kurye_basvurulari
        ORDER BY id DESC
    """)

    kuryeler = cursor.fetchall()

    cursor.execute("""
        SELECT *
        FROM siparisler
        ORDER BY id DESC
    """)

    siparisler = cursor.fetchall()

    conn.close()

    return render_template(
        "admin.html",
        basvurular=firinlar,
        kuryeler=kuryeler,
        siparisler=siparisler
    )


# ==================================================
# ADMIN ÇIKIŞ
# ==================================================

@app.route("/admin/cikis")
def admin_cikis():

    session.pop(
        "admin_giris",
        None
    )

    return redirect(
        "/admin"
    )


# ==================================================
# FIRIN ONAY / RED
# ==================================================

@app.route(
    "/admin/durum/<int:id>/<durum>"
)
def durum_degistir(
    id,
    durum
):

    if not session.get(
        "admin_giris"
    ):

        return redirect(
            "/admin"
        )

    if durum not in [
        "Onaylandı",
        "Reddedildi"
    ]:

        return "Geçersiz işlem"

    conn = sqlite3.connect(DATABASE)

    cursor = conn.cursor()

    cursor.execute("""
        UPDATE firin_basvurulari
        SET durum = ?
        WHERE id = ?
    """, (
        durum,
        id
    ))

    conn.commit()

    conn.close()

    return redirect(
        "/admin"
    )


# ==================================================
# ONAYLI FIRIN KALDIR
# ==================================================

@app.route(
    "/admin/firin-kaldir/<int:id>",
    methods=["POST"]
)
def firin_kaldir(id):

    if not session.get(
        "admin_giris"
    ):

        return redirect(
            "/admin"
        )

    conn = sqlite3.connect(DATABASE)

    cursor = conn.cursor()

    cursor.execute("""
        UPDATE firin_basvurulari
        SET durum = 'Reddedildi'
        WHERE id = ?
        AND durum = 'Onaylandı'
    """, (
        id,
    ))

    conn.commit()

    conn.close()

    return redirect(
        "/admin"
    )


# ==================================================
# KURYE ONAY / RED
# ==================================================

@app.route(
    "/admin/kurye/<int:id>/<durum>"
)
def kurye_durum_degistir(
    id,
    durum
):

    if not session.get(
        "admin_giris"
    ):

        return redirect(
            "/admin"
        )

    if durum not in [
        "Onaylandı",
        "Reddedildi"
    ]:

        return "Geçersiz işlem"

    conn = sqlite3.connect(DATABASE)

    cursor = conn.cursor()

    cursor.execute("""
        UPDATE kurye_basvurulari
        SET durum = ?
        WHERE id = ?
    """, (
        durum,
        id
    ))

    conn.commit()

    conn.close()

    return redirect(
        "/admin"
    )


# ==================================================
# BAŞLAT
# ==================================================

if __name__ == "__main__":

    veritabani_olustur()

    app.run(
        debug=True
    )