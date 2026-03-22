import { SignIn, UserButton } from '@clerk/clerk-react';
import {
  ChevronLeft,
  Github,
  Layers,
  Moon,
  Scissors,
  Settings,
  Subtitles,
  Sun,
  Twitter,
  type LucideIcon,
} from 'lucide-react';
import { Suspense } from 'react';
import { useTranslation } from 'react-i18next';

import { ClipGallery } from '../components/ClipGallery';
import { HoloTerminal } from '../components/HoloTerminal';
import { JobForm } from '../components/JobForm';
import { JobQueue } from '../components/JobQueue';
import { SubtitlePreview } from '../components/SubtitlePreview';
import { AccountDeletionCard } from '../components/AccountDeletionCard';
import { ConnectionChip } from '../components/ui/ConnectionChip';
import { IconButton } from '../components/ui/IconButton';
import { Select } from '../components/ui/Select';
import type { SubtitleAnimationType } from '../config/subtitleStyles';
import type { AppLocale } from '../i18n';
import type { Clip, WsStatus } from '../types';
import { AutoCutEditor, Editor, SubtitleEditor, ThreeCanvas } from './lazyComponents';
import type { AppViewMode } from './helpers';
import type { ResilientAuthState, ResilientAuthStatus } from '../auth/useResilientAuth';

const SIGN_IN_APPEARANCE = {
  elements: {
    rootBox: 'mx-auto shadow-2xl shadow-primary/20',
    card: 'bg-card backdrop-blur-3xl border border-foreground/10 rounded-2xl',
    headerTitle: 'text-foreground font-outfit text-2xl font-bold',
    headerSubtitle: 'text-muted-foreground',
    socialButtonsBlockButton: 'border-border text-foreground hover:bg-foreground/5',
    dividerLine: 'bg-border',
    dividerText: 'text-muted-foreground',
    formFieldLabel: 'text-foreground',
    formFieldInput: 'bg-foreground/5 border border-border text-foreground',
    formButtonPrimary: 'bg-primary text-primary-foreground hover:bg-primary/90 transition-all font-bold',
    footerActionText: 'text-muted-foreground',
    footerActionLink: 'text-primary hover:text-primary/80',
  },
};

interface SignedInShellProps {
  backendAuthStatus: ResilientAuthState['backendAuthStatus'];
  canUseBackend: boolean;
  authStatus: ResilientAuthStatus;
  closeEditor: () => void;
  currentAnimationType: SubtitleAnimationType;
  currentStyle: string;
  editingClip: Clip | null;
  handleAnimationChange: (animationType: SubtitleAnimationType) => void;
  handleSkipSubtitlesChange: (disabled: boolean) => void;
  handleStyleChange: (styleName: string) => void;
  openClipSubtitleEditor: (clip: Clip) => void;
  openConfig: () => void;
  openManual: () => void;
  openSubtitle: () => void;
  pauseReason: ResilientAuthState['pauseReason'];
  locale: AppLocale;
  setLocale: (locale: AppLocale) => void;
  showUserMenu: boolean;
  subtitleSessionNonce: number;
  subtitleTargetClip: Clip | null;
  subtitlesDisabled: boolean;
  theme: string;
  toggleTheme: () => void;
  viewMode: AppViewMode;
  wsStatus: WsStatus;
  isOnline: boolean;
}

export function AppBackground() {
  return (
    <Suspense fallback={null}>
      <ThreeCanvas />
    </Suspense>
  );
}

export function SignedOutScreen() {
  return (
    <div className="flex w-full h-[80vh] items-center justify-center animate-in fade-in duration-1000">
      <SignIn appearance={SIGN_IN_APPEARANCE} />
    </div>
  );
}

export function SignedInShell({
  backendAuthStatus,
  canUseBackend,
  authStatus,
  closeEditor,
  currentAnimationType,
  currentStyle,
  editingClip,
  handleAnimationChange,
  handleSkipSubtitlesChange,
  handleStyleChange,
  openClipSubtitleEditor,
  openConfig,
  openManual,
  openSubtitle,
  pauseReason,
  locale,
  setLocale,
  showUserMenu,
  subtitleSessionNonce,
  subtitleTargetClip,
  subtitlesDisabled,
  theme,
  toggleTheme,
  viewMode,
  wsStatus,
  isOnline,
}: SignedInShellProps) {
  return (
    <>
      <AppHeader
        authStatus={authStatus}
        openConfig={openConfig}
        openManual={openManual}
        openSubtitle={openSubtitle}
        locale={locale}
        setLocale={setLocale}
        showUserMenu={showUserMenu}
        theme={theme}
        toggleTheme={toggleTheme}
        viewMode={viewMode}
      />
      <MainContent
        closeEditor={closeEditor}
        currentAnimationType={currentAnimationType}
        currentStyle={currentStyle}
        editingClip={editingClip}
        handleAnimationChange={handleAnimationChange}
        handleSkipSubtitlesChange={handleSkipSubtitlesChange}
        handleStyleChange={handleStyleChange}
        openConfig={openConfig}
        openClipSubtitleEditor={openClipSubtitleEditor}
        subtitleSessionNonce={subtitleSessionNonce}
        subtitleTargetClip={subtitleTargetClip}
        subtitlesDisabled={subtitlesDisabled}
        viewMode={viewMode}
      />
      <AppFooter
        backendAuthStatus={backendAuthStatus}
        canUseBackend={canUseBackend}
        isOnline={isOnline}
        pauseReason={pauseReason}
        wsStatus={wsStatus}
      />
    </>
  );
}

function AppHeader({
  authStatus,
  locale,
  openConfig,
  openManual,
  openSubtitle,
  setLocale,
  showUserMenu,
  theme,
  toggleTheme,
  viewMode,
}: {
  authStatus: ResilientAuthStatus;
  locale: AppLocale;
  openConfig: () => void;
  openManual: () => void;
  openSubtitle: () => void;
  setLocale: (locale: AppLocale) => void;
  showUserMenu: boolean;
  theme: string;
  toggleTheme: () => void;
  viewMode: AppViewMode;
}) {
  return (
    <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between px-2">
      <BrandPanel />
      <div className="flex items-center gap-4 sm:gap-6">
        <ViewNavigation
          openConfig={openConfig}
          openManual={openManual}
          openSubtitle={openSubtitle}
          viewMode={viewMode}
        />
        <HeaderActions
          authStatus={authStatus}
          locale={locale}
          setLocale={setLocale}
          showUserMenu={showUserMenu}
          theme={theme}
          toggleTheme={toggleTheme}
        />
      </div>
    </header>
  );
}

function BrandPanel() {
  const { t } = useTranslation();

  return (
    <div className="flex flex-col">
      <h1 className="text-2xl sm:text-4xl font-black tracking-tighter bg-clip-text text-transparent bg-gradient-to-r from-primary via-secondary to-accent holo-text flex items-center gap-3">
        <div className="w-8 h-8 sm:w-10 sm:h-10 bg-background/50 backdrop-blur-md rounded-xl flex items-center justify-center rotate-45 border-2 border-primary shadow-[0_0_15px_rgba(0,242,255,0.6)] shrink-0 transition-transform duration-700 hover:rotate-90">
          <Layers className="text-primary w-5 h-5 sm:w-6 sm:h-6 -rotate-45" />
        </div>
        GOD-TIER SHORTS
      </h1>
      <div className="flex items-center gap-2 mt-2 px-1">
        <span className="text-[11px] font-mono uppercase tracking-[0.3em] text-primary font-bold animate-pulse">{t('app.brand.subtitle')}</span>
        <div className="h-[1px] w-8 bg-secondary/50" />
        <span className="text-[11px] font-mono text-muted-foreground holo-text">{t('app.brand.version')}</span>
      </div>
    </div>
  );
}

function ViewNavigation({
  openConfig,
  openManual,
  openSubtitle,
  viewMode,
}: {
  openConfig: () => void;
  openManual: () => void;
  openSubtitle: () => void;
  viewMode: AppViewMode;
}) {
  const { t } = useTranslation();
  const navItems: Array<{
    activeClass: string;
    icon: LucideIcon;
    label: string;
    mode: AppViewMode;
  }> = [
    { activeClass: 'bg-accent/20 text-foreground shadow-lg shadow-accent/10 border border-accent/30', icon: Settings, label: t('app.nav.configure'), mode: 'config' },
    { activeClass: 'bg-primary/20 text-foreground shadow-lg shadow-primary/10 border border-primary/30', icon: Scissors, label: t('app.nav.autoCut'), mode: 'manual' },
    { activeClass: 'bg-accent/20 text-foreground shadow-lg shadow-accent/10 border border-accent/30', icon: Subtitles, label: t('app.nav.subtitleEdit'), mode: 'subtitle' },
  ];
  const actions = {
    config: openConfig,
    manual: openManual,
    subtitle: openSubtitle,
  };

  return (
    <nav className="flex p-1 glass-card rounded-xl border-accent/20" aria-label={t('app.nav.ariaLabel')}>
      {navItems.map(({ activeClass, icon: Icon, label, mode }) => {
        const isActive = viewMode === mode;
        return (
          <button
            key={mode}
            onClick={actions[mode]}
            aria-current={isActive ? 'page' : undefined}
            className={resolveNavButtonClass(isActive, activeClass)}
          >
            <Icon className="w-3 h-3" aria-hidden="true" />
            {label}
          </button>
        );
      })}
    </nav>
  );
}

function HeaderActions({
  authStatus,
  locale,
  setLocale,
  showUserMenu,
  theme,
  toggleTheme,
}: {
  authStatus: ResilientAuthStatus;
  locale: AppLocale;
  setLocale: (locale: AppLocale) => void;
  showUserMenu: boolean;
  theme: string;
  toggleTheme: () => void;
}) {
  const { t } = useTranslation();
  const localeOptions = [
    { label: t('common.locale.en'), value: 'en' },
    { label: t('common.locale.tr'), value: 'tr' },
  ];

  return (
    <div className="flex items-center gap-3 border-l border-border pl-4">
      <Select
        ariaLabel={t('common.labels.language')}
        className="w-32"
        onChange={(value) => setLocale(value === 'tr' ? 'tr' : 'en')}
        options={localeOptions}
        value={locale}
      />
      <IconButton
        label={t('app.header.themeToggle')}
        icon={theme === 'dark' ? <Sun className="w-4 h-4 text-primary" /> : <Moon className="w-4 h-4 text-secondary" />}
        onClick={toggleTheme}
        variant="ghost"
      />
      <IconButton label={t('app.header.github')} icon={<Github className="w-4 h-4" />} href="https://github.com" variant="ghost" />
      <IconButton label={t('app.header.twitter')} icon={<Twitter className="w-4 h-4" />} href="https://twitter.com" variant="ghost" />
      {showUserMenu ? (
        <div className="pl-2 flex items-center justify-center">
          <UserButton appearance={{ elements: { userButtonAvatarBox: 'w-8 h-8 ring-2 ring-primary/50 hover:ring-primary transition-all duration-300' } }} />
        </div>
      ) : (
        <div className="rounded-full border border-amber-500/30 bg-amber-500/10 px-3 py-1 text-[10px] font-mono uppercase tracking-[0.22em] text-amber-100">
          {authStatus === 'offline_authenticated' ? t('app.header.offlineSession') : t('app.header.authFallback')}
        </div>
      )}
    </div>
  );
}

function MainContent({
  closeEditor,
  currentAnimationType,
  currentStyle,
  editingClip,
  handleAnimationChange,
  handleSkipSubtitlesChange,
  handleStyleChange,
  openConfig,
  openClipSubtitleEditor,
  subtitleSessionNonce,
  subtitleTargetClip,
  subtitlesDisabled,
  viewMode,
}: {
  closeEditor: () => void;
  currentAnimationType: SubtitleAnimationType;
  currentStyle: string;
  editingClip: Clip | null;
  handleAnimationChange: (animationType: SubtitleAnimationType) => void;
  handleSkipSubtitlesChange: (disabled: boolean) => void;
  handleStyleChange: (styleName: string) => void;
  openConfig: () => void;
  openClipSubtitleEditor: (clip: Clip) => void;
  subtitleSessionNonce: number;
  subtitleTargetClip: Clip | null;
  subtitlesDisabled: boolean;
  viewMode: AppViewMode;
}) {
  const { t } = useTranslation();

  if (editingClip) {
    return <EditorWorkspace closeEditor={closeEditor} editingClip={editingClip} />;
  }

  if (viewMode === 'manual') {
    return <FullWidthWorkspace fallback={t('app.autoCut.loading')}><AutoCutEditor onOpenLibrary={openConfig} /></FullWidthWorkspace>;
  }

  if (viewMode === 'subtitle') {
    return (
      <FullWidthWorkspace fallback={t('app.subtitleEditor.loading')}>
        <SubtitleEditor
          key={subtitleTargetClip ? `${subtitleSessionNonce}:${subtitleTargetClip.project ?? 'legacy'}:${subtitleTargetClip.name}` : `subtitle:${subtitleSessionNonce}`}
          targetClip={subtitleTargetClip}
          lockedToClip={Boolean(subtitleTargetClip)}
        />
      </FullWidthWorkspace>
    );
  }

  return (
    <ConfigWorkspace
      currentAnimationType={currentAnimationType}
      currentStyle={currentStyle}
      handleAnimationChange={handleAnimationChange}
      handleSkipSubtitlesChange={handleSkipSubtitlesChange}
      handleStyleChange={handleStyleChange}
      openClipSubtitleEditor={openClipSubtitleEditor}
      subtitlesDisabled={subtitlesDisabled}
    />
  );
}

function EditorWorkspace({
  closeEditor,
  editingClip,
}: {
  closeEditor: () => void;
  editingClip: Clip;
}) {
  const { t } = useTranslation();

  return (
    <main className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
      <div className="lg:col-span-12 space-y-8 animate-in fade-in duration-700">
        <div className="flex items-center gap-4">
          <IconButton
            label={t('common.actions.back')}
            icon={<ChevronLeft className="w-4 h-4 text-primary" />}
            onClick={closeEditor}
            className="glass-card border-border border rounded-lg"
          />
          <h2 className="text-xl font-bold font-mono text-primary flex items-center gap-3">
            <span className="opacity-40 text-foreground">{t('app.editor.systemEditing')}</span> {editingClip.name}
          </h2>
        </div>
        <Suspense fallback={<LoadingCard label={t('app.editor.loading')} />}>
          <Editor mode="clip" targetClip={editingClip} onClose={closeEditor} />
        </Suspense>
      </div>
    </main>
  );
}

function FullWidthWorkspace({
  children,
  fallback,
}: {
  children: React.ReactNode;
  fallback: string;
}) {
  return (
    <main className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
      <div className="lg:col-span-12">
        <Suspense fallback={<LoadingCard label={fallback} />}>
          {children}
        </Suspense>
      </div>
    </main>
  );
}

function ConfigWorkspace({
  currentAnimationType,
  currentStyle,
  handleAnimationChange,
  handleSkipSubtitlesChange,
  handleStyleChange,
  openClipSubtitleEditor,
  subtitlesDisabled,
}: {
  currentAnimationType: SubtitleAnimationType;
  currentStyle: string;
  handleAnimationChange: (animationType: SubtitleAnimationType) => void;
  handleSkipSubtitlesChange: (disabled: boolean) => void;
  handleStyleChange: (styleName: string) => void;
  openClipSubtitleEditor: (clip: Clip) => void;
  subtitlesDisabled: boolean;
}) {
  const { t } = useTranslation();

  return (
    <main className="grid grid-cols-1 gap-8 items-start">
      <div className="grid grid-cols-1 gap-6 items-stretch lg:grid-cols-[minmax(0,0.96fr)_minmax(300px,0.82fr)]">
        <section className="glass-card h-full min-w-0 self-start p-5 sm:p-6 border-accent/20 shadow-lg shadow-accent/5 ring-1 ring-accent/10 lg:col-start-1 lg:row-start-1">
          <h2 className="mb-4 text-xs font-mono uppercase tracking-[0.2em] text-accent">{t('app.nav.configure')}</h2>
          <JobForm
            onAnimationChange={handleAnimationChange}
            onStyleChange={handleStyleChange}
            onSkipSubtitlesChange={handleSkipSubtitlesChange}
          />
        </section>
        <div className="flex h-full min-w-0 items-center justify-center px-2 py-3 sm:px-4 sm:py-4 lg:col-start-2 lg:row-start-1 lg:min-h-0 lg:px-0 lg:py-0">
          <SubtitlePreview
            animationType={currentAnimationType}
            cutAsShort={true}
            disabled={subtitlesDisabled}
            showLegend={false}
            size="tall"
            styleName={currentStyle}
            variant="device"
          />
        </div>
        <section className="glass-card h-full min-w-0 w-full max-w-full min-h-[192px] overflow-hidden border-white/10 shadow-lg shadow-black/20 lg:col-span-2 lg:row-start-2">
          <HoloTerminal compact />
        </section>
      </div>
      <div className="min-w-0">
        <JobQueue />
      </div>
      <div className="min-w-0">
        <ClipGallery onEditClip={openClipSubtitleEditor} />
      </div>
      <div className="min-w-0">
        <AccountDeletionCard />
      </div>
    </main>
  );
}

function AppFooter({
  backendAuthStatus,
  canUseBackend,
  isOnline,
  pauseReason,
  wsStatus,
}: {
  backendAuthStatus: ResilientAuthState['backendAuthStatus'];
  canUseBackend: boolean;
  isOnline: boolean;
  pauseReason: ResilientAuthState['pauseReason'];
  wsStatus: WsStatus;
}) {
  const { t } = useTranslation();

  return (
    <footer className="mt-20 pt-8 border-t border-border flex flex-col md:flex-row items-center justify-between gap-4 text-muted-foreground">
      <p className="text-[11px] font-mono uppercase tracking-widest">{t('footer.signature')}</p>
      <ConnectionChip
        backendAuthStatus={backendAuthStatus}
        canUseProtectedRequests={canUseBackend}
        isOnline={isOnline}
        pauseReason={pauseReason}
        status={wsStatus}
      />
    </footer>
  );
}

function LoadingCard({ label }: { label: string }) {
  return <div className="glass-card p-4 text-xs font-mono">{label}</div>;
}

function resolveNavButtonClass(isActive: boolean, activeClass: string) {
  return [
    'px-4 sm:px-6 py-2 rounded-lg text-xs font-mono transition-all duration-300 flex items-center gap-2',
    isActive ? activeClass : 'text-muted-foreground hover:text-foreground',
  ].join(' ');
}
