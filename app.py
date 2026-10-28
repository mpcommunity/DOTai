import cv2
import pytesseract
from PIL import Image

IMAGE_PATH = r"C:\Users\USER\Documents\DATai project\sample-farsi.png"

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

LANG = "fas"

def preprocess_image(path):
    """بهبود تصویر برای دقت بهتر OCR"""
    img = cv2.imread(path)
    if img is None:
        raise FileNotFoundError(f"تصویر پیدا نشد: {path}")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

    gray = cv2.medianBlur(gray, 3)

    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    return Image.fromarray(binary)


def image_to_text(path, lang=LANG):
    img = preprocess_image(path)
    config = "--oem 3 --psm 6"
    return pytesseract.image_to_string(img, lang=lang, config=config)


if __name__ == "__main__":
    text = image_to_text(IMAGE_PATH)
    with open("output.txt", "w", encoding="utf-8") as f:
        f.write(text)