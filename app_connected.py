import io
import os
from pathlib import Path

import cv2
import numpy as np
import pytesseract
from flask import Flask, jsonify, request, send_from_directory
from PIL import Image, ImageOps, UnidentifiedImageError
from pytesseract import Output

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None


BASE_DIR = Path(__file__).resolve().parent
LANG = os.getenv("TESSERACT_LANG", "fas")

# در ویندوز، در صورت نیاز مسیر Tesseract را در متغیر محیطی TESSERACT_CMD قرار دهید.
tesseract_cmd = os.getenv("TESSERACT_CMD")
if tesseract_cmd:
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf"}
MAX_IMAGE_PIXELS = 25_000_000
MAX_PDF_PAGES = 30


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def load_image(image):
    """اصلاح جهت عکس و محدود کردن ابعاد برای جلوگیری از مصرف بیش از حد حافظه."""
    image = ImageOps.exif_transpose(image).convert("RGB")
    if image.width * image.height > MAX_IMAGE_PIXELS:
        scale = (MAX_IMAGE_PIXELS / (image.width * image.height)) ** 0.5
        new_size = (max(1, int(image.width * scale)),
                    max(1, int(image.height * scale)))
        image = image.resize(new_size, Image.Resampling.LANCZOS)
    return image


def make_image_variants(image):
    """
    چند نسخه از تصویر می‌سازد؛ چون آستانه‌گذاری سیاه‌وسفید برای همه دست‌خط‌ها
    مناسب نیست، نسخه خاکستری نیز حفظ می‌شود.
    """
    rgb = np.array(load_image(image))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

    # بزرگ‌نمایی برای کمک به تشخیص حروف ریز
    height, width = gray.shape
    if max(height, width) < 2200:
        gray = cv2.resize(
            gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC
        )

    # کاهش نویز ملایم؛ نسخه اصلی خاکستری هم نگه داشته می‌شود.
    denoised = cv2.bilateralFilter(gray, 5, 35, 35)

    # افزایش ملایم کنتراست
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(denoised)

    # دو روش متفاوت آستانه‌گذاری
    _, otsu = cv2.threshold(
        enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )
    adaptive = cv2.adaptiveThreshold(
        enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 31, 11
    )

    return [
        ("gray", Image.fromarray(gray)),
        ("enhanced", Image.fromarray(enhanced)),
        ("otsu", Image.fromarray(otsu)),
        ("adaptive", Image.fromarray(adaptive)),
    ]


def run_ocr(image, psm):
    config = f"--oem 3 --psm {psm}"
    data = pytesseract.image_to_data(
        image, lang=LANG, config=config, output_type=Output.DICT
    )

    words = []
    confidences = []
    for word, confidence in zip(data["text"], data["conf"]):
        word = word.strip()
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            continue
        if word and confidence >= 0:
            words.append(word)
            confidences.append(confidence)

    text = pytesseract.image_to_string(
        image, lang=LANG, config=config
    ).strip()

    # امتیاز بر اساس اطمینان کلمات؛ تعداد کلمات نیز اندکی اثر دارد.
    if confidences:
        score = (sum(confidences) / len(confidences)) + min(len(words), 20) * 0.25
    else:
        score = 0

    return text, score


def image_to_text(image):
    variants = make_image_variants(image)
    # 6: متن با چینش معمول، 11: متن پراکنده، 4: یک ستون متن
    page_modes = (6, 11, 4)

    best_text = ""
    best_score = -1

    for _, variant in variants:
        for psm in page_modes:
            text, score = run_ocr(variant, psm)
            if text and score > best_score:
                best_text = text
                best_score = score

    return best_text


def extract_from_pdf(file_bytes):
    if fitz is None:
        raise RuntimeError(
            "برای پردازش PDF، بستهٔ PyMuPDF را نصب کنید: pip install pymupdf"
        )

    document = fitz.open(stream=file_bytes, filetype="pdf")
    output = []
    try:
        if document.page_count > MAX_PDF_PAGES:
            raise ValueError("تعداد صفحات PDF نباید بیشتر از ۳۰ صفحه باشد.")

        for page in document:
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image = Image.open(io.BytesIO(pix.tobytes("png")))
            output.append(image_to_text(image))
    finally:
        document.close()

    return "\n\n".join(output).strip()


@app.get("/")
def home():
    return send_from_directory(str(BASE_DIR), "index.html")


@app.post("/api/ocr")
def ocr_endpoint():
    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        return jsonify(error="لطفاً یک فایل انتخاب کنید."), 400

    if not allowed_file(uploaded.filename):
        return jsonify(error="فرمت مجاز: PDF، PNG، JPG یا JPEG."), 400

    data = uploaded.read()
    if not data:
        return jsonify(error="فایل خالی است."), 400

    try:
        extension = uploaded.filename.rsplit(".", 1)[1].lower()

        if extension == "pdf":
            text = extract_from_pdf(data)
        else:
            image = Image.open(io.BytesIO(data))
            text = image_to_text(image)

        return jsonify(text=text, filename=uploaded.filename)

    except pytesseract.TesseractNotFoundError:
        return jsonify(
            error="Tesseract نصب نیست یا مسیر آن درست تنظیم نشده است."
        ), 500
    except pytesseract.TesseractError as exc:
        return jsonify(error=f"خطای OCR: {exc}"), 500
    except UnidentifiedImageError:
        return jsonify(error="فایل تصویر معتبر نیست یا قابل خواندن نیست."), 400
    except (ValueError, RuntimeError) as exc:
        return jsonify(error=str(exc)), 400
    except Exception:
        app.logger.exception("خطا هنگام پردازش فایل OCR")
        return jsonify(error="هنگام خواندن فایل خطای پیش‌بینی‌نشده‌ای رخ داد."), 500


@app.errorhandler(413)
def file_too_large(_error):
    return jsonify(error="حجم فایل نباید بیشتر از ۱۵ مگابایت باشد."), 413


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=int(os.getenv("PORT", "5000")),
        debug=False
    )
