import os
import re
import io
import sqlite3
from pathlib import Path
from functools import wraps

from flask import Flask, jsonify, request, session, send_from_directory, g
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "dot.db"
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
MAX_FILE_SIZE = 15 * 1024 * 1024
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.config.update(
    SECRET_KEY=os.environ.get("DOT_SECRET_KEY", "CHANGE-THIS-SECRET-KEY-BEFORE-DEPLOYMENT"),
    MAX_CONTENT_LENGTH=MAX_FILE_SIZE,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("DOT_HTTPS", "0") == "1",
)

# OCR dependencies are imported lazily so the web app can start even if OCR
# packages are not installed; /api/ocr will return a clear dependency error.
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    db = sqlite3.connect(DATABASE)
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE COLLATE NOCASE,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS exams (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exam_id INTEGER NOT NULL,
        extracted_text TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(exam_id) REFERENCES exams(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        submission_id INTEGER NOT NULL,
        score REAL,
        feedback TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(submission_id) REFERENCES submissions(id) ON DELETE CASCADE
    );
    """)
    db.commit()
    db.close()

init_db()

def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return get_db().execute(
        "SELECT id, username, email FROM users WHERE id = ?", (user_id,)
    ).fetchone()

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if current_user() is None:
            return jsonify(error="برای انجام این کار ابتدا وارد حساب کاربری شوید."), 401
        return fn(*args, **kwargs)
    return wrapper

def user_json(user):
    return {"id": user["id"], "username": user["username"], "email": user["email"]}

@app.get("/")
def home():
    return send_from_directory(BASE_DIR, "index.html")

@app.get("/health")
def health():
    return jsonify(status="ok", database="connected")

@app.post("/api/register")
def register():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        return jsonify(error="ایمیل معتبر وارد کنید."), 400
    if len(password) < 8:
        return jsonify(error="رمز عبور باید حداقل ۸ کاراکتر باشد."), 400
    username = email.split("@", 1)[0][:100]
    db = get_db()
    try:
        cursor = db.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email, generate_password_hash(password))
        )
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify(error="این ایمیل قبلاً ثبت‌نام کرده است."), 409
    session.clear()
    session["user_id"] = cursor.lastrowid
    return jsonify(user=user_json(current_user())), 201

@app.post("/api/login")
def login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify(error="ایمیل یا رمز عبور اشتباه است."), 401
    session.clear()
    session["user_id"] = user["id"]
    return jsonify(user=user_json(user))

@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(message="خارج شدید.")

@app.get("/api/me")
def me():
    user = current_user()
    return jsonify(user=user_json(user) if user else None)

@app.patch("/api/profile")
@login_required
def update_profile():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    if not username or len(username) > 100:
        return jsonify(error="نام کاربری باید بین ۱ تا ۱۰۰ نویسه باشد."), 400
    db = get_db()
    if password:
        if len(password) < 8:
            return jsonify(error="رمز جدید باید حداقل ۸ کاراکتر باشد."), 400
        db.execute("UPDATE users SET username = ?, password_hash = ? WHERE id = ?",
                   (username, generate_password_hash(password), session["user_id"]))
    else:
        db.execute("UPDATE users SET username = ? WHERE id = ?", (username, session["user_id"]))
    db.commit()
    return jsonify(user=user_json(current_user()))

def ocr_image(image_bytes, filename):
    try:
        import cv2
        import numpy as np
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("برای OCR کتابخانه‌های opencv-python، numpy، pillow و pytesseract لازم‌اند.") from exc

    tesseract_cmd = os.environ.get("TESSERACT_CMD")
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    elif os.name == "nt":
        default_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if Path(default_cmd).exists():
            pytesseract.pytesseract.tesseract_cmd = default_cmd

    lang = os.environ.get("TESSERACT_LANG", "fas")
    array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("تصویر قابل خواندن نیست.")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    gray = cv2.medianBlur(gray, 3)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    pil_image = Image.fromarray(binary)
    return pytesseract.image_to_string(pil_image, lang=lang, config="--oem 3 --psm 6")

def extract_text(file_bytes, filename):
    extension = filename.rsplit(".", 1)[-1].lower()
    if extension != "pdf":
        return ocr_image(file_bytes, filename)
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("برای پردازش PDF کتابخانه PyMuPDF لازم است. آن را با pip install pymupdf نصب کنید.") from exc
    try:
        import pytesseract
        from PIL import Image
        import numpy as np
        import cv2
    except ImportError as exc:
        raise RuntimeError("کتابخانه‌های OCR نصب نیستند؛ تنظیمات نصب را در README ببینید.") from exc
    tesseract_cmd = os.environ.get("TESSERACT_CMD")
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    elif os.name == "nt" and Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe").exists():
        pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    lang = os.environ.get("TESSERACT_LANG", "fas")
    document = fitz.open(stream=file_bytes, filetype="pdf")
    texts = []
    try:
        for page in document:
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            array = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            gray = cv2.cvtColor(array, cv2.COLOR_BGR2GRAY)
            gray = cv2.medianBlur(gray, 3)
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            texts.append(pytesseract.image_to_string(Image.fromarray(binary), lang=lang, config="--oem 3 --psm 6"))
    finally:
        document.close()
    return "\n\n".join(texts)

@app.post("/api/ocr")
@login_required
def ocr_endpoint():
    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        return jsonify(error="فایلی ارسال نشده است."), 400
    filename = secure_filename(uploaded.filename)
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in ALLOWED_EXTENSIONS:
        return jsonify(error="فرمت فایل پشتیبانی نمی‌شود."), 400
    file_bytes = uploaded.read(MAX_FILE_SIZE + 1)
    if len(file_bytes) > MAX_FILE_SIZE:
        return jsonify(error="حجم فایل بیشتر از ۱۵ مگابایت است."), 413
    try:
        extracted = extract_text(file_bytes, filename)
    except Exception as exc:
        app.logger.exception("OCR failed")
        message = str(exc) if isinstance(exc, (RuntimeError, ValueError, FileNotFoundError)) else "خطا در اجرای OCR؛ نصب Tesseract و زبان فارسی را بررسی کنید."
        return jsonify(error=message), 500

    db = get_db()
    exam_cursor = db.execute("INSERT INTO exams (user_id, filename) VALUES (?, ?)",
                              (session["user_id"], filename))
    submission_cursor = db.execute("INSERT INTO submissions (exam_id, extracted_text) VALUES (?, ?)",
                                   (exam_cursor.lastrowid, extracted))
    db.commit()
    return jsonify(text=extracted, filename=filename, exam_id=exam_cursor.lastrowid,
                   submission_id=submission_cursor.lastrowid)

@app.errorhandler(413)
def too_large(_error):
    return jsonify(error="حجم فایل بیشتر از ۱۵ مگابایت است."), 413

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)
