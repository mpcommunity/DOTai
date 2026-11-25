export const $ = (id) => document.getElementById(id);

export const elements = {
  landingPage: $('landing-page'),
  uploadPage: $('upload-page'),
  processingPage: $('processing-page'),
  authModal: $('auth-modal'),
  accountWrap: $('account-wrap'),
  accountButton: $('account-button'),
  accountPanel: $('account-panel'),
  fileInput: $('exam-file'),
  uploadZone: $('upload-zone'),
  selectedFileCard: $('selected-file'),
  continueButton: $('continue-button'),
  toast: $('toast')
};
