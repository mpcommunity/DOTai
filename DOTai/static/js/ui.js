import { elements, $ } from './dom.js';

let toastTimer;

export function showToast(message) {
  elements.toast.textContent = message;
  elements.toast.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => elements.toast.classList.remove('show'), 3800);
}

export function showPage(page) {
  [elements.landingPage, elements.uploadPage, elements.processingPage]
    .forEach(section => section.classList.add('hidden'));

  page.classList.remove('hidden');
  elements.accountPanel.classList.add('hidden');
  elements.accountButton.setAttribute('aria-expanded', 'false');
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

export function bindAccountPanel() {
  elements.accountButton.addEventListener('click', () => {
    const willOpen = elements.accountPanel.classList.contains('hidden');
    elements.accountPanel.classList.toggle('hidden', !willOpen);
    elements.accountButton.setAttribute('aria-expanded', String(willOpen));
  });

  document.addEventListener('click', event => {
    if (!event.target.closest('.account-wrap')) {
      elements.accountPanel.classList.add('hidden');
      elements.accountButton.setAttribute('aria-expanded', 'false');
    }
  });
}
