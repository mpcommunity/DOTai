import { $, elements } from './dom.js';
import { showToast } from './ui.js';

let currentUser = null;
export function setCurrentUser(user) {
  currentUser = user;
  $('profile-username').value = user.username || user.email || '';
}

export function initProfile() {
  const usernameInput = $('profile-username');
  const passwordInput = $('profile-password');
  const editButton = $('edit-profile');
  const saveButton = $('save-profile');
  const cancelButton = $('cancel-profile');
  const message = $('profile-message');
  function setEditMode(editing) {
    usernameInput.readOnly = !editing;
    passwordInput.readOnly = !editing;
    editButton.classList.toggle('hidden', editing);
    saveButton.classList.toggle('hidden', !editing);
    cancelButton.classList.toggle('hidden', !editing);
    message.textContent = editing ? 'اطلاعات موردنظر خود را ویرایش کنید.' : 'اطلاعات حساب کاربری شما';
  }
  editButton.addEventListener('click', () => {
    usernameInput.value = currentUser?.username || '';
    passwordInput.value = '';
    passwordInput.placeholder = 'رمز جدید (اختیاری)';
    setEditMode(true);
  });
  cancelButton.addEventListener('click', () => {
    usernameInput.value = currentUser?.username || '';
    passwordInput.value = '********';
    passwordInput.placeholder = '';
    setEditMode(false);
  });
  saveButton.addEventListener('click', async () => {
    const username = usernameInput.value.trim();
    const password = passwordInput.value;
    if (!username) return showToast('نام کاربری نمی‌تواند خالی باشد.');
    try {
      const response = await fetch('api/profile', { method: 'PATCH', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username, password }) });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error || 'ذخیره اطلاعات انجام نشد.');
      setCurrentUser(data.user);
      passwordInput.value = '********';
      passwordInput.placeholder = '';
      setEditMode(false);
      showToast('اطلاعات حساب ذخیره شد.');
    } catch (error) { showToast(error.message); }
  });
}
