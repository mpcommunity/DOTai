import { bindAccountPanel } from './ui.js';
import { initAuth } from './auth.js';
import { initProfile } from './profile.js';
import { initUpload } from './upload.js';

bindAccountPanel();
initAuth();
initProfile();
initUpload();
