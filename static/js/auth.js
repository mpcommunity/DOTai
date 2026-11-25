import { $, elements } from './dom.js';
import { showPage, showToast } from './ui.js';
import { setCurrentUser } from './profile.js';

let authMode = 'login';

function closeAuth() { elements.authModal.classList.add('hidden'); }
function openAuth(mode) {
  authMode = mode;
  $('modal-title').textContent = mode === 'login' ? 'ورود به حساب کاربری' : 'ساخت حساب کاربری';
  $('modal-description').textContent = 'برای ورود به فضای کار دات، اطلاعات خود را وارد کنید.';
  $('auth-submit').textContent = mode === 'login' ? 'ورود و ادامه' : 'ساخت حساب و ادامه';
  $('switch-text').textContent = mode === 'login' ? 'حساب کاربری ندارید؟' : 'از قبل حساب دارید؟';
  $('switch-auth').textContent = mode === 'login' ? 'ثبت‌نام' : 'ورود';
  $('auth-modal').classList.remove('hidden');
}

function setLoggedIn(user) {
  setCurrentUser(user);
  $('login-top').classList.add('hidden');
  $('signup-top').classList.add('hidden');
  elements.accountWrap.classList.remove('hidden');
  showPage(elements.uploadPage);
}

async function request(url, options = {}) {
  const response = await fetch(url, { credentials: 'same-origin', ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) } });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || 'درخواست ناموفق بود.');
  return data;
}

export async function initAuth() {
  $('login-top').addEventListener('click', () => openAuth('login'));
  $('signup-top').addEventListener('click', () => openAuth('signup'));
  $('hero-login').addEventListener('click', () => openAuth('login'));
  $('hero-signup').addEventListener('click', () => openAuth('signup'));
  $('close-modal').addEventListener('click', closeAuth);
  $('switch-auth').addEventListener('click', () => openAuth(authMode === 'login' ? 'signup' : 'login'));
  elements.authModal.addEventListener('click', event => { if (event.target === elements.authModal) closeAuth(); });
  $('brand-home').addEventListener('click', event => { event.preventDefault(); showPage(elements.landingPage); });

  $('auth-form').addEventListener('submit', async event => {
    event.preventDefault();
    const email = $('auth-email').value.trim();
    const password = $('auth-password').value;
    const endpoint = authMode === 'login' ? 'api/login' : 'api/register';
    const button = $('auth-submit');
    button.disabled = true;
    try {
      const data = await request(endpoint, { method: 'POST', body: JSON.stringify({ email, password }) });
      closeAuth();
      $('auth-form').reset();
      setLoggedIn(data.user);
      showToast(authMode === 'login' ? 'با موفقیت وارد شدید.' : 'حساب کاربری ساخته شد.');
    } catch (error) { showToast(error.message); }
    finally { button.disabled = false; }
  });

  $('logout-button').addEventListener('click', async () => {
    try {
      await request('api/logout', { method: 'POST', body: '{}' });
      elements.accountWrap.classList.add('hidden');
      $('login-top').classList.remove('hidden');
      $('signup-top').classList.remove('hidden');
      showPage(elements.landingPage);
      showToast('از حساب خارج شدید.');
    } catch (error) { showToast(error.message); }
  });

  try {
    const data = await request('api/me');
    if (data.user) setLoggedIn(data.user);
  } catch { /* کاربر وارد نشده است؛ صفحه فرود نمایش داده می‌شود. */ }
}
