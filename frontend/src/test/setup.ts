import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach, beforeEach } from 'vitest';

import i18n, { LOCALE_STORAGE_KEY } from '../i18n';

beforeEach(async () => {
  window.localStorage.removeItem(LOCALE_STORAGE_KEY);
  await i18n.changeLanguage('en');
  document.documentElement.lang = 'en';
});

afterEach(() => {
  cleanup();
});
