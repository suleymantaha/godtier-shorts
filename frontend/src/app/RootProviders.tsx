import { ClerkProvider } from '@clerk/clerk-react';
import { enUS, trTR } from '@clerk/localizations';
import { StrictMode, useEffect } from 'react';
import { I18nextProvider } from 'react-i18next';

import App from '../App';
import i18n, { changeAppLanguage } from '../i18n';
import { useLocaleStore } from '../store/useLocaleStore';

const PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;

if (!PUBLISHABLE_KEY) {
  throw new Error('Missing Publishable Key');
}

function RootProvidersContent() {
  const locale = useLocaleStore((store) => store.locale);

  useEffect(() => {
    void changeAppLanguage(locale);
  }, [locale]);

  return (
    <I18nextProvider i18n={i18n}>
      <ClerkProvider
        afterSignOutUrl="/"
        localization={locale === 'tr' ? trTR : enUS}
        publishableKey={PUBLISHABLE_KEY}
      >
        <App />
      </ClerkProvider>
    </I18nextProvider>
  );
}

export function RootProviders() {
  return (
    <StrictMode>
      <RootProvidersContent />
    </StrictMode>
  );
}
