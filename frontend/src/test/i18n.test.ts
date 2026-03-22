import { describe, expect, it, vi } from 'vitest';

import i18n, {
  LOCALE_STORAGE_KEY,
  changeAppLanguage,
  getBrowserLocale,
  normalizeLocale,
  readStoredLocale,
  resolveInitialLocale,
} from '../i18n';

describe('i18n helpers', () => {
  it('normalizes unknown locales to english', () => {
    expect(normalizeLocale('tr')).toBe('tr');
    expect(normalizeLocale('en')).toBe('en');
    expect(normalizeLocale('de')).toBe('en');
  });

  it('prefers stored locale over browser locale', () => {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, JSON.stringify({ state: { locale: 'tr' }, version: 0 }));
    expect(readStoredLocale()).toBe('tr');
    expect(resolveInitialLocale()).toBe('tr');
  });

  it('falls back to browser locale when no stored locale exists', () => {
    window.localStorage.removeItem(LOCALE_STORAGE_KEY);

    const navigatorSpy = vi.spyOn(window.navigator, 'languages', 'get').mockReturnValue(['tr-TR', 'en-US']);
    expect(getBrowserLocale()).toBe('tr');
    expect(resolveInitialLocale()).toBe('tr');
    navigatorSpy.mockRestore();
  });

  it('falls back to english when browser locale is unsupported', () => {
    window.localStorage.removeItem(LOCALE_STORAGE_KEY);

    const navigatorSpy = vi.spyOn(window.navigator, 'languages', 'get').mockReturnValue(['de-DE']);
    expect(getBrowserLocale()).toBe('en');
    navigatorSpy.mockRestore();
  });

  it('updates i18n language and document lang when the app language changes', async () => {
    await changeAppLanguage('tr');
    expect(i18n.language).toBe('tr');
    expect(document.documentElement.lang).toBe('tr');

    await changeAppLanguage('en');
    expect(i18n.language).toBe('en');
    expect(document.documentElement.lang).toBe('en');
  });
});
