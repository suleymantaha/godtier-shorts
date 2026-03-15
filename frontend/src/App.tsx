import { AppBackground, SignedInShell, SignedOutScreen } from './app/sections';
import { useAppShellController } from './app/useAppShellController';
import { useResilientAuth } from './auth/useResilientAuth';
import { SystemStatusBanner } from './components/ui/SystemStatusBanner';

function AuthStateCard({
  message,
  title,
}: {
  message: string;
  title: string;
}) {
  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <div className="glass-card max-w-xl rounded-3xl border border-white/10 px-6 py-8 text-center shadow-2xl shadow-black/30">
        <p className="text-[11px] font-mono uppercase tracking-[0.28em] text-primary">{title}</p>
        <p className="mt-4 text-sm leading-7 text-muted-foreground">{message}</p>
      </div>
    </div>
  );
}

function App() {
  const auth = useResilientAuth();
  const controller = useAppShellController(auth.canUseBackend, auth.identityKey);

  return (
    <>
      <AppBackground />
      <div className="min-h-screen bg-transparent px-4 py-4 md:px-8 md:py-6 lg:px-12 lg:py-8 space-y-8 mx-auto w-full">
        {auth.notice ? <SystemStatusBanner {...auth.notice} /> : null}
        {auth.status === 'loading' ? (
          <AuthStateCard
            title="AUTH CHECK"
            message="Oturum ve baglanti durumu kontrol ediliyor. Bu adim uzarsa Clerk veya internet erisimi gecici olarak sorun yasiyor olabilir."
          />
        ) : null}
        {auth.status === 'error' ? (
          <AuthStateCard
            title="AUTH ERROR"
            message={auth.error?.message ?? 'Kimlik dogrulama sirasinda beklenmeyen bir hata olustu.'}
          />
        ) : null}
        {auth.status === 'signed_out' ? <SignedOutScreen /> : null}
        {auth.canAccessApp ? (
          <SignedInShell
            {...controller}
            backendAuthStatus={auth.backendAuthStatus}
            authStatus={auth.status}
            isOnline={auth.isOnline}
            pauseReason={auth.pauseReason}
            showUserMenu={auth.showUserMenu}
          />
        ) : null}
      </div>
    </>
  );
}

export default App;
