import { create } from 'zustand';
import { persist } from 'zustand/middleware';

import { LOCALE_STORAGE_KEY, type AppLocale, normalizeLocale, resolveInitialLocale } from '../i18n';

interface LocaleState {
  locale: AppLocale;
  setLocale: (locale: AppLocale) => void;
}

export const useLocaleStore = create<LocaleState>()(
  persist(
    (set) => ({
      locale: resolveInitialLocale(),
      setLocale: (locale) => set({ locale: normalizeLocale(locale) }),
    }),
    {
      name: LOCALE_STORAGE_KEY,
    },
  ),
);
