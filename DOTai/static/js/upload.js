import { $, elements } from './dom.js';
import { MAX_FILE_SIZE } from './config.js';
import { showToast, showPage } from './ui.js';
import { runOcr } from './ocr.js';

let selectedFile = null;
let fileUrl = null;

function readableSize(bytes) {
  if (bytes < 1024 * 1024) return Math.max(1, Math.round(bytes / 1024)) + ' کیلوبایت';
  return (bytes / (1024 * 1024)).toFixed(2) + ' مگابایت';
}

function isSupported(file) {
  return file && /\.(pdf|png|jpe?g)$/i.test(file.name);
}

function setFile(file) {
  if (!isSupported(file)) {
    showToast('لطفاً فایل PDF یا تصویر JPG، JPEG و PNG انتخاب کنید.');
    return;
  }
  if (file.size > MAX_FILE_SIZE) {
    showToast('حجم فایل نباید بیشتر از ۱۵ مگابایت باشد.');
    return;
  }

  if (fileUrl) URL.revokeObjectURL(fileUrl);
  selectedFile = file;
  fileUrl = URL.createObjectURL(file);
  elements.selectedFileCard.classList.remove('hidden');
  $('selected-file-name').textContent = file.name;
  $('selected-file-size').textContent = readableSize(file.size);
  $('selected-file-icon').textContent = /\.pdf$/i.test(file.name) ? 'PDF' : 'IMG';
  elements.continueButton.disabled = false;
  showToast('فایل انتخاب شد. برای رفتن به مرحلهٔ بعد، روی «ادامه و پردازش» بزنید.');
}

function renderPreview() {
  const preview = $('file-preview');
  preview.replaceChildren();
  $('preview-file-name').textContent = selectedFile
    ? selectedFile.name : 'فایلی انتخاب نشده است';
  $('file-type-tag').textContent =
    selectedFile && /\.pdf$/i.test(selectedFile.name) ? 'PDF' : 'تصویر';

  if (!selectedFile || !fileUrl) {
    const fallback = document.createElement('div');
    fallback.className = 'pdf-fallback';
    fallback.textContent = 'پیش‌نمایش فایل در دسترس نیست.';
    preview.appendChild(fallback);
    return;
  }

  if (/\.pdf$/i.test(selectedFile.name)) {
    const iframe = document.createElement('iframe');
    iframe.title = 'پیش‌نمایش فایل PDF';
    iframe.src = fileUrl;
    preview.appendChild(iframe);
  } else {
    const img = document.createElement('img');
    img.alt = 'پیش‌نمایش برگهٔ آزمون';
    img.src = fileUrl;
    preview.appendChild(img);
  }
  $('open-file').onclick = () => window.open(fileUrl, '_blank', 'noopener');
}

function resetStatus() {
  document.querySelectorAll('.status-item').forEach((item, index) => {
    item.classList.toggle('active', index === 0);
    item.classList.remove('complete');
    item.querySelector('.status-mark').textContent = '';
  });
  $('main-spinner').classList.remove('done');
  $('status-title').textContent = 'در حال بارگذاری و ثبت فایل...';
  $('status-description').textContent =
    'لطفاً منتظر بمانید. پس از آماده‌شدن پردازش، وضعیت مراحل در همین صفحه به‌روزرسانی می‌شود.';
  $('overall-status').textContent = 'در صف پردازش';
  $('progress-bar').style.width = '15%';
  $('progress-label').textContent = 'آماده‌سازی فایل';
  $('progress-number').textContent = '۱۵٪';
  $('wait-note').textContent =
    'فایل برای استخراج متن به سرور ارسال می‌شود. این مرحله فقط متن دست‌نویس را استخراج می‌کند و هنوز نمره‌دهی انجام نمی‌دهد.';
}

function clearSelectedFile() {
  selectedFile = null;
  elements.fileInput.value = '';
  elements.selectedFileCard.classList.add('hidden');
  elements.continueButton.disabled = true;
  if (fileUrl) URL.revokeObjectURL(fileUrl);
  fileUrl = null;
}

export function initUpload() {
  elements.fileInput.addEventListener('change', () => {
    if (elements.fileInput.files?.[0]) setFile(elements.fileInput.files[0]);
  });

  $('remove-file').addEventListener('click', clearSelectedFile);

  ['dragenter', 'dragover'].forEach(name => elements.uploadZone.addEventListener(name, event => {
    event.preventDefault();
    elements.uploadZone.classList.add('dragover');
  }));

  ['dragleave', 'drop'].forEach(name => elements.uploadZone.addEventListener(name, event => {
    event.preventDefault();
    elements.uploadZone.classList.remove('dragover');
  }));

  elements.uploadZone.addEventListener('drop', event => {
    const file = event.dataTransfer.files?.[0];
    if (file) setFile(file);
  });

  elements.continueButton.addEventListener('click', async () => {
    if (!selectedFile) {
      showToast('لطفاً ابتدا یک فایل انتخاب کنید.');
      return;
    }

    renderPreview();
    resetStatus();
    $('ocr-result').value = '';
    $('ocr-result-status').textContent = 'در حال پردازش';
    showPage(elements.processingPage);
    elements.continueButton.disabled = true;

    try {
      await runOcr(selectedFile);
    } finally {
      elements.continueButton.disabled = false;
    }
  });

  $('back-to-upload').addEventListener('click', () => showPage(elements.uploadPage));

  $('new-exam').addEventListener('click', () => {
    clearSelectedFile();
    $('ocr-result').value = '';
    $('ocr-result-status').textContent = 'منتظر فایل';
    showPage(elements.uploadPage);
  });
}
