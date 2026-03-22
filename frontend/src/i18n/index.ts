import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

import { en } from './resources/en';
import { tr } from './resources/tr';

export const SUPPORTED_LOCALES = ['en', 'tr'] as const;
export type AppLocale = (typeof SUPPORTED_LOCALES)[number];

export const DEFAULT_LOCALE: AppLocale = 'en';
export const LOCALE_STORAGE_KEY = 'godtier-locale-storage';

export const resources = {
  en: { translation: en },
  tr: { translation: tr },
} as const;

export function getBrowserLocale(): AppLocale {
  if (typeof navigator === 'undefined') {
    return DEFAULT_LOCALE;
  }

  const languages = Array.isArray(navigator.languages) && navigator.languages.length > 0
    ? navigator.languages
    : [navigator.language];

  const normalized = languages
    .filter((value): value is string => typeof value === 'string' && value.length > 0)
    .map((value) => value.toLowerCase());

  if (normalized.some((value) => value.startsWith('tr'))) {
    return 'tr';
  }

  if (normalized.some((value) => value.startsWith('en'))) {
    return 'en';
  }

  return DEFAULT_LOCALE;
}

export function normalizeLocale(value: unknown): AppLocale {
  return value === 'tr' ? 'tr' : 'en';
}

export function readStoredLocale(): AppLocale | null {
  if (typeof window === 'undefined') {
    return null;
  }

  try {
    const raw = window.localStorage.getItem(LOCALE_STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as { state?: { locale?: unknown } } | null;
    return parsed?.state?.locale === 'tr' || parsed?.state?.locale === 'en'
      ? parsed.state.locale
      : null;
  } catch {
    return null;
  }
}

export function resolveInitialLocale(): AppLocale {
  return readStoredLocale() ?? getBrowserLocale();
}

export function getIntlLocale(locale: AppLocale): string {
  return locale === 'tr' ? 'tr-TR' : 'en-US';
}

export function formatDateTime(
  value: Date | number | string,
  locale: AppLocale,
  options?: Intl.DateTimeFormatOptions,
): string {
  const date = value instanceof Date ? value : new Date(value);
  return new Intl.DateTimeFormat(getIntlLocale(locale), options).format(date);
}

export function formatTime(value: Date | number | string, locale: AppLocale): string {
  return formatDateTime(value, locale, {
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function tSafe(key: string, options?: Record<string, unknown>): string {
  try {
    return i18n.t(key, options);
  } catch {
    return typeof options?.defaultValue === 'string' ? options.defaultValue : key;
  }
}

export async function changeAppLanguage(locale: AppLocale): Promise<void> {
  const nextLocale = normalizeLocale(locale);
  if (i18n.language !== nextLocale) {
    await i18n.changeLanguage(nextLocale);
  }

  if (typeof document !== 'undefined') {
    document.documentElement.lang = nextLocale;
  }
}

if (!i18n.isInitialized) {
  void i18n
    .use(initReactI18next)
    .init({
      debug: false,
      fallbackLng: DEFAULT_LOCALE,
      interpolation: {
        escapeValue: false,
      },
      lng: resolveInitialLocale(),
      react: {
        useSuspense: false,
      },
      resources,
      returnEmptyString: false,
      returnNull: false,
    });
}

if (typeof document !== 'undefined') {
  document.documentElement.lang = normalizeLocale(i18n.language);
}

export default i18n;
