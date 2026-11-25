import { $, elements } from './dom.js';
import { showToast } from './ui.js';

let currentUsername = '';

export function setCurrentUsername(username) {
  currentUsername = username;
  $('profile-username').value = username;
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
    message.textContent = editing
      ? 'اطلاعات موردنظر خود را ویرایش کنید.'
      : 'اطلاعات حساب کاربری شما';
  }

  editButton.addEventListener('click', () => {
    usernameInput.value = currentUsername;
    passwordInput.value = '';
    passwordInput.placeholder = 'رمز جدید را وارد کنید';
    setEditMode(true);
  });

  cancelButton.addEventListener('click', () => {
    usernameInput.value = currentUsername;
    passwordInput.value = '********';
    passwordInput.placeholder = '';
    setEditMode(false);
  });

  saveButton.addEventListener('click', () => {
    const newUsername = usernameInput.value.trim();
    const passwordWasEntered = passwordInput.value.length > 0;

    if (!newUsername) {
      showToast('نام کاربری نمی‌تواند خالی باشد.');
      return;
    }

    currentUsername = newUsername;
    usernameInput.value = currentUsername;
    passwordInput.value = '********';
    passwordInput.placeholder = '';
    setEditMode(false);

    showToast(passwordWasEntered
      ? 'نام کاربری تغییر کرد؛ تغییر واقعی رمز نیازمند اتصال به سرور است.'
      : 'نام کاربری با موفقیت تغییر کرد.');
  });
}
