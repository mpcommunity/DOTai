import io
import os
from pathlib import Path

import cv2
import numpy as np
import pytesseract
from flask import Flask, jsonify, request, send_from_directory
from PIL import Image, ImageOps

try:
    import fitz  # PyMuPDF: PDF pages to images
except ImportError:
    fitz = None

BASE_DIR = Path(__file__).resolve().parent
LANG = os.getenv("TESSERACT_LANG", "fas")

# در ویندوز، در صورت نیاز مسیر Tesseract را در متغیر محیطی TESSERACT_CMD قرار دهید.
tesseract_cmd = os.getenv("TESSERACT_CMD")
if tesseract_cmd:
    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024  # حداکثر ۱۵ مگابایت
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def preprocess_image(image):
    """بهبود کنتراست و اندازهٔ تصویر برای OCR."""
    rgb = ImageOps.exif_transpose(image).convert("RGB")
    img = cv2.cvtColor(np.array(rgb), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    gray = cv2.medianBlur(gray, 3)
    _, binary = cv2.threshold(
        gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )
    return Image.fromarray(binary)


def image_to_text(image):
    prepared = preprocess_image(image)
    config = "--oem 3 --psm 6"
    return pytesseract.image_to_string(prepared, lang=LANG, config=config)


def extract_from_pdf(file_bytes):
    if fitz is None:
        raise RuntimeError("برای پردازش PDF، بستهٔ PyMuPDF را نصب کنید: pip install pymupdf")
    document = fitz.open(stream=file_bytes, filetype="pdf")
    output = []
    try:
        if document.page_count > 30:
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
    return send_from_directory(BASE_DIR, "index.html")


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
        return jsonify(error="Tesseract نصب نیست یا مسیر آن درست تنظیم نشده است."), 500
    except pytesseract.TesseractError as exc:
        return jsonify(error=f"خطای OCR: {exc}"), 500
    except Exception as exc:
        return jsonify(error=str(exc) or "خواندن فایل ناموفق بود."), 500


@app.errorhandler(413)
def file_too_large(_error):
    return jsonify(error="حجم فایل نباید بیشتر از ۱۵ مگابایت باشد."), 413


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=False)
