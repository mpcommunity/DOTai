import { $, elements } from './dom.js';
import { OCR_ENDPOINT } from './config.js';
import { showToast } from './ui.js';

function updateStep(index, title, description, percent, label) {
  const steps = Array.from(document.querySelectorAll('.status-item'));
  steps.forEach((item, i) => {
    item.classList.toggle('active', i === index);
    item.classList.toggle('complete', i < index);
    item.querySelector('.status-mark').textContent = i < index ? '✓' : '';
  });

  $('status-title').textContent = title;
  $('status-description').textContent = description;
  $('overall-status').textContent = label;
  $('progress-bar').style.width = percent + '%';
  $('progress-number').textContent = percent + '٪';
  $('progress-label').textContent = label;
}

export async function runOcr(file) {
  const formData = new FormData();
  formData.append('file', file);

  try {
    updateStep(0, 'در حال ارسال و ثبت فایل...',
      'فایل شما برای استخراج متن به سرور ارسال می‌شود.', 20, 'بارگذاری فایل');
    updateStep(1, 'در حال آماده‌سازی صفحات...',
      'سرور فایل را برای تشخیص متن آماده می‌کند.', 40, 'آماده‌سازی فایل');

    const response = await fetch(OCR_ENDPOINT, { method: 'POST', body: formData, credentials: 'same-origin' });
    const responseText = await response.text();
    let result;

    try {
      result = JSON.parse(responseText);
    } catch {
      const preview = responseText.slice(0, 180).replace(/\s+/g, ' ');
      throw new Error(
        `پاسخ سرور JSON نیست (HTTP ${response.status}). ` +
        `احتمالاً درخواست به سرور Flask نرسیده است. پاسخ: ${preview || 'خالی'}`
      );
    }

    if (!response.ok) {
      throw new Error(result.error || `پردازش فایل ناموفق بود (HTTP ${response.status}).`);
    }
    if (typeof result.text !== 'string') {
      throw new Error('پاسخ سرور معتبر نیست؛ فیلد متن استخراج‌شده وجود ندارد.');
    }

    updateStep(2, 'تشخیص دست‌خط انجام شد',
      'متن استخراج‌شده در پایین صفحه نمایش داده شده است.', 80, 'تشخیص متن');
    $('ocr-result').value = result.text || 'متنی از فایل تشخیص داده نشد.';
    $('ocr-result-status').textContent = 'استخراج انجام شد';

    const steps = Array.from(document.querySelectorAll('.status-item'));
    steps[2].classList.remove('active');
    steps[2].classList.add('complete');
    steps[2].querySelector('.status-mark').textContent = '✓';
    steps[3].classList.remove('active', 'complete');
    steps[4].classList.remove('active', 'complete');

    $('main-spinner').classList.add('done');
    $('status-title').textContent = 'استخراج متن تمام شد';
    $('status-description').textContent =
      'متن زیر را بررسی و در صورت نیاز اصلاح کنید. نمره‌دهی خودکار هنوز به این نسخه اضافه نشده است.';
    $('overall-status').textContent = 'استخراج کامل شد';
    $('progress-bar').style.width = '100%';
    $('progress-label').textContent = 'استخراج متن کامل شد';
    $('progress-number').textContent = '۱۰۰٪';
    showToast('متن فایل با موفقیت استخراج شد.');
  } catch (error) {
    $('ocr-result-status').textContent = 'خطا';
    $('status-title').textContent = 'پردازش انجام نشد';
    $('status-description').textContent = error.message || 'ارتباط با سرور برقرار نشد.';
    $('overall-status').textContent = 'خطا';
    showToast(error.message || 'خطا در ارتباط با سرور.');
  }
}
