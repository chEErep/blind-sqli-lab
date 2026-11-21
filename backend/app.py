"""
Переключатель SAFE_MODE (переменная окружения):
  SAFE_MODE=true  -> безопасная (параметризованная) версия;
  SAFE_MODE=false -> уязвимая версия
"""
import os
import re
import secrets
from datetime import datetime, timedelta
from urllib.parse import quote

import pymysql
from flask import (
    Flask, request, render_template, redirect, url_for, session, flash,
    send_from_directory,
)
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-lab-secret-change-me")

DB_CONFIG = dict(
    host=os.getenv("DB_HOST", "127.0.0.1"),
    port=int(os.getenv("DB_PORT", "3306")),
    user=os.getenv("DB_USER", "appuser"),
    password=os.getenv("DB_PASSWORD", "apppass"),
    database=os.getenv("DB_NAME", "appdb"),
    cursorclass=pymysql.cursors.DictCursor,
    autocommit=True,
)

SAFE_MODE = os.getenv("SAFE_MODE", "true").lower() == "true"

MUSIC_DIR = os.getenv("MUSIC_DIR", os.path.join(os.path.dirname(__file__), "music"))
IMG_EXT = {".jpg", ".jpeg", ".png", ".webp"}
AUDIO_EXT = {".mp3", ".m4a", ".ogg", ".wav"}


def _media_url(*parts):
    return "/media/" + "/".join(quote(p) for p in parts)


def _clean_track(fname):
    name = os.path.splitext(fname)[0].replace("_", " ")
    name = re.sub(r"\(hitmos\.fm\)", "", name, flags=re.I)
    name = re.sub(r"\s*\d{5,}\s*$", "", name)      # убрать хвостовой id вида 80858207
    name = re.sub(r"\s+", " ", name).strip()
    if " - " in name:
        artist, title = name.split(" - ", 1)
    else:
        artist, title = "", name
    return artist.strip(), title.strip()


def scan_music():
    """Собирает плейлисты из MUSIC_DIR: каждая подпапка = плейлист"""
    playlists, egg_gifs = [], []
    if not os.path.isdir(MUSIC_DIR):
        return playlists, egg_gifs
    for pl in sorted(os.listdir(MUSIC_DIR)):
        pdir = os.path.join(MUSIC_DIR, pl)
        if not os.path.isdir(pdir):
            continue
        cover, tracks, gifs = None, [], []
        for f in sorted(os.listdir(pdir)):
            ext = os.path.splitext(f)[1].lower()
            if ext in IMG_EXT and cover is None:
                cover = _media_url(pl, f)
            elif ext == ".gif":
                gifs.append(_media_url(pl, f))
            elif ext in AUDIO_EXT:
                artist, title = _clean_track(f)
                egg = "gazan" in f.lower() and "67" in f
                tracks.append({"title": title, "artist": artist,
                               "src": _media_url(pl, f), "egg": egg})
        if gifs and any(t["egg"] for t in tracks):
            egg_gifs = gifs
        playlists.append({"name": pl, "cover": cover, "tracks": tracks})
    return playlists, egg_gifs


@app.route("/media/<path:relpath>")
def media(relpath):
    # раздаёт обложки, mp3 и гифки из папки music (только чтение)
    return send_from_directory(MUSIC_DIR, relpath, conditional=True)


def get_db():
    return pymysql.connect(**DB_CONFIG)


#  УЯЗВИМОЕ МЕСТО — поиск пользователя по email в форме "забыли пароль"
def find_user_by_email_safe(email):
    """
    БЕЗОПАСНЫЙ вариант: email передаётся параметром (%s) -> инъекция невозможна.
    """
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, username FROM users WHERE email = %s", (email,))
            return cur.fetchone()
    finally:
        conn.close()


def find_user_by_email_vulnerable(email):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            # УЯЗВИМО: email вставляется в строку SQL напрямую (f-string),
            # без параметризации. Любой SQL-код в email попадёт в запрос.
            sql = f"SELECT id, username FROM users WHERE email = '{email}'"
            cur.execute(sql)
            return cur.fetchone()
    finally:
        conn.close()


def find_user_by_email(email):
    return find_user_by_email_safe(email) if SAFE_MODE else find_user_by_email_vulnerable(email)

#  Маршруты
@app.route("/")
def index():
    if session.get("username"):
        return redirect(url_for("dashboard"))
    return render_template("index.html", safe_mode=SAFE_MODE)


@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username", "")
    password = request.form.get("password", "")
    conn = get_db()
    try:
        with conn.cursor() as cur:
            # Логин НЕ уязвим — запрос параметризован.
            cur.execute(
                "SELECT id, username, password FROM users WHERE username = %s",
                (username,),
            )
            user = cur.fetchone()
    finally:
        conn.close()

    if user and check_password_hash(user["password"], password):
        session["uid"] = user["id"]
        session["username"] = user["username"]
        return redirect(url_for("dashboard"))
    flash("Неверный логин или пароль.")
    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/dashboard")
def dashboard():
    if not session.get("username"):
        return redirect(url_for("index"))
    playlists, egg_gifs = scan_music()
    return render_template(
        "dashboard.html",
        username=session["username"],
        playlists=playlists,
        egg_gifs=egg_gifs,
    )


@app.route("/forgot", methods=["GET", "POST"])
def forgot():
    if request.method == "GET":
        return render_template("forgot.html")

    email = request.form.get("email", "")
    try:
        user = find_user_by_email(email)
    except NotImplementedError:
        # Сработает при SAFE_MODE=false, пока не дописана уязвимая версия.
        user = None

    if user:
        # Генерируем токен и кладём в базу (этот UPDATE параметризован).
        token = secrets.token_hex(8)
        expires = datetime.utcnow() + timedelta(hours=1)
        conn = get_db()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET reset_token=%s, reset_expires=%s WHERE id=%s",
                    (token, expires, user["id"]),
                )
        finally:
            conn.close()
        # "Письмо" не шлём — пишем ссылку в лог (для своего теста смотри:
        #   docker compose logs backend). Пользователю ссылку НЕ показываем.
        app.logger.info("Reset link for %s: /reset?token=%s", user["username"], token)

    # Ответ ВСЕГДА одинаковый -> инъекция слепая.
    flash("Если такой email зарегистрирован, мы отправили ссылку для сброса пароля.")
    return render_template("forgot.html")


@app.route("/reset", methods=["GET", "POST"])
def reset():
    if request.method == "GET":
        return render_template("reset.html", token=request.args.get("token", ""))

    token = request.form.get("token", "")
    new_password = request.form.get("password", "")
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM users WHERE reset_token=%s AND reset_expires > NOW()",
                (token,),
            )
            row = cur.fetchone()
            if not row:
                flash("Токен недействителен или истёк.")
                return redirect(url_for("reset", token=token))
            cur.execute(
                "UPDATE users SET password=%s, reset_token=NULL, reset_expires=NULL WHERE id=%s",
                (generate_password_hash(new_password), row["id"]),
            )
    finally:
        conn.close()
    flash("Пароль изменён. Теперь можно войти.")
    return redirect(url_for("index"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    if not username or not email or not password:
        flash("Заполни все поля.")
        return redirect(url_for("register"))

    conn = get_db()
    try:
        with conn.cursor() as cur:
            # Регистрация безопасна (параметризация) — уязвимость только в /forgot.
            cur.execute(
                "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
                (username, email, generate_password_hash(password)),
            )
    except pymysql.err.IntegrityError:
        flash("Такой логин или email уже заняты.")
        return redirect(url_for("register"))
    finally:
        conn.close()

    flash("Аккаунт создан, теперь войди.")
    return redirect(url_for("index"))


@app.route("/profile")
def profile():
    if not session.get("username"):
        return redirect(url_for("index"))
    return render_template("profile.html")


@app.route("/health")
def health():
    try:
        get_db().close()
        return {"status": "ok", "safe_mode": SAFE_MODE}
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "detail": str(e)}, 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
