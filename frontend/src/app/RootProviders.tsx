import { ClerkProvider } from '@clerk/clerk-react';
import { enUS, trTR } from '@clerk/localizations';
import { StrictMode, useEffect } from 'react';
import { I18nextProvider } from 'react-i18next';

import App from '../App';
import { CLERK_PUBLISHABLE_KEY } from '../config';
import i18n, { changeAppLanguage } from '../i18n';
import { useLocaleStore } from '../store/useLocaleStore';

function MissingClerkPublishableKey() {
  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex items-center justify-center p-6">
      <div className="max-w-lg rounded-2xl border border-amber-500/40 bg-zinc-900/90 p-6 shadow-xl">
        <h1 className="text-lg font-semibold text-amber-200">Clerk yapılandırması eksik</h1>
        <p className="mt-3 text-sm leading-relaxed text-zinc-300">
          Arayüz için{' '}
          <code className="rounded bg-zinc-800 px-1 py-0.5 text-xs">VITE_CLERK_PUBLISHABLE_KEY</code>{' '}
          tanımlı olmalı. Değeri Clerk Dashboard → API Keys bölümünden alıp{' '}
          <strong className="text-zinc-100">proje kökündeki</strong> <code className="text-xs">.env</code> dosyasına
          ekleyin (Vite bu dosyayı okur). Geliştirme sunucusunu yeniden başlatın.
        </p>
        <p className="mt-4 text-xs text-zinc-500">
          İlgili: <code className="text-zinc-400">VITE_CLERK_JWT_TEMPLATE</code>, backend{' '}
          <code className="text-zinc-400">CLERK_ISSUER_URL</code> / <code className="text-zinc-400">CLERK_AUDIENCE</code>
        </p>
      </div>
    </div>
  );
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
        publishableKey={CLERK_PUBLISHABLE_KEY}
      >
        <App />
      </ClerkProvider>
    </I18nextProvider>
  );
}

export function RootProviders() {
  return (
    <StrictMode>
      {CLERK_PUBLISHABLE_KEY ? <RootProvidersContent /> : <MissingClerkPublishableKey />}
    </StrictMode>
  );
}
