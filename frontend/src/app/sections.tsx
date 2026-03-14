import { SignedIn, SignedOut, SignIn, UserButton } from '@clerk/clerk-react';
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

import { ClipGallery } from '../components/ClipGallery';
import { HoloTerminal } from '../components/HoloTerminal';
import { JobForm } from '../components/JobForm';
import { JobQueue } from '../components/JobQueue';
import { SubtitlePreview } from '../components/SubtitlePreview';
import { ConnectionChip } from '../components/ui/ConnectionChip';
import { IconButton } from '../components/ui/IconButton';
import type { Clip, WsStatus } from '../types';
import { AutoCutEditor, Editor, SubtitleEditor, ThreeCanvas } from './lazyComponents';
import type { AppViewMode } from './helpers';

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

const NAV_ITEMS: Array<{
  activeClass: string;
  icon: LucideIcon;
  label: string;
  mode: AppViewMode;
}> = [
  { activeClass: 'bg-accent/20 text-foreground shadow-lg shadow-accent/10 border border-accent/30', icon: Settings, label: 'CONFIGURE', mode: 'config' },
  { activeClass: 'bg-primary/20 text-foreground shadow-lg shadow-primary/10 border border-primary/30', icon: Scissors, label: 'AUTO CUT', mode: 'manual' },
  { activeClass: 'bg-accent/20 text-foreground shadow-lg shadow-accent/10 border border-accent/30', icon: Subtitles, label: 'SUBTITLE EDIT', mode: 'subtitle' },
];

interface SignedInShellProps {
  closeEditor: () => void;
  currentStyle: string;
  editingClip: Clip | null;
  handleSkipSubtitlesChange: (disabled: boolean) => void;
  handleStyleChange: (styleName: string) => void;
  openClipAdvancedEditor: (clip: Clip) => void;
  openClipSubtitleEditor: (clip: Clip) => void;
  openConfig: () => void;
  openManual: () => void;
  openSubtitle: () => void;
  subtitleTargetClip: Clip | null;
  subtitlesDisabled: boolean;
  theme: string;
  toggleTheme: () => void;
  viewMode: AppViewMode;
  wsStatus: WsStatus;
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
    <SignedOut>
      <div className="flex w-full h-[80vh] items-center justify-center animate-in fade-in duration-1000">
        <SignIn appearance={SIGN_IN_APPEARANCE} />
      </div>
    </SignedOut>
  );
}

export function SignedInShell({
  closeEditor,
  currentStyle,
  editingClip,
  handleSkipSubtitlesChange,
  handleStyleChange,
  openClipAdvancedEditor,
  openClipSubtitleEditor,
  openConfig,
  openManual,
  openSubtitle,
  subtitleTargetClip,
  subtitlesDisabled,
  theme,
  toggleTheme,
  viewMode,
  wsStatus,
}: SignedInShellProps) {
  return (
    <SignedIn>
      <AppHeader
        openConfig={openConfig}
        openManual={openManual}
        openSubtitle={openSubtitle}
        theme={theme}
        toggleTheme={toggleTheme}
        viewMode={viewMode}
      />
      <MainContent
        closeEditor={closeEditor}
        currentStyle={currentStyle}
        editingClip={editingClip}
        handleSkipSubtitlesChange={handleSkipSubtitlesChange}
        handleStyleChange={handleStyleChange}
        openClipAdvancedEditor={openClipAdvancedEditor}
        openClipSubtitleEditor={openClipSubtitleEditor}
        subtitleTargetClip={subtitleTargetClip}
        subtitlesDisabled={subtitlesDisabled}
        viewMode={viewMode}
      />
      <AppFooter wsStatus={wsStatus} />
    </SignedIn>
  );
}

function AppHeader({
  openConfig,
  openManual,
  openSubtitle,
  theme,
  toggleTheme,
  viewMode,
}: {
  openConfig: () => void;
  openManual: () => void;
  openSubtitle: () => void;
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
        <HeaderActions theme={theme} toggleTheme={toggleTheme} />
      </div>
    </header>
  );
}

function BrandPanel() {
  return (
    <div className="flex flex-col">
      <h1 className="text-2xl sm:text-4xl font-black tracking-tighter bg-clip-text text-transparent bg-gradient-to-r from-primary via-secondary to-accent holo-text flex items-center gap-3">
        <div className="w-8 h-8 sm:w-10 sm:h-10 bg-background/50 backdrop-blur-md rounded-xl flex items-center justify-center rotate-45 border-2 border-primary shadow-[0_0_15px_rgba(0,242,255,0.6)] shrink-0 transition-transform duration-700 hover:rotate-90">
          <Layers className="text-primary w-5 h-5 sm:w-6 sm:h-6 -rotate-45" />
        </div>
        GOD-TIER SHORTS
      </h1>
      <div className="flex items-center gap-2 mt-2 px-1">
        <span className="text-[11px] font-mono uppercase tracking-[0.3em] text-primary font-bold animate-pulse">Nebula AI Architect</span>
        <div className="h-[1px] w-8 bg-secondary/50" />
        <span className="text-[11px] font-mono text-muted-foreground holo-text">v1.0.SPACE</span>
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
  const actions = {
    config: openConfig,
    manual: openManual,
    subtitle: openSubtitle,
  };

  return (
    <nav className="flex p-1 glass-card rounded-xl border-accent/20" aria-label="Ana navigasyon">
      {NAV_ITEMS.map(({ activeClass, icon: Icon, label, mode }) => {
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
  theme,
  toggleTheme,
}: {
  theme: string;
  toggleTheme: () => void;
}) {
  return (
    <div className="hidden sm:flex items-center gap-3 border-l border-border pl-4">
      <IconButton
        label="Toggle Theme"
        icon={theme === 'dark' ? <Sun className="w-4 h-4 text-primary" /> : <Moon className="w-4 h-4 text-secondary" />}
        onClick={toggleTheme}
        variant="ghost"
      />
      <IconButton label="GitHub" icon={<Github className="w-4 h-4" />} href="https://github.com" variant="ghost" />
      <IconButton label="Twitter" icon={<Twitter className="w-4 h-4" />} href="https://twitter.com" variant="ghost" />
      <div className="pl-2 flex items-center justify-center">
        <UserButton appearance={{ elements: { userButtonAvatarBox: 'w-8 h-8 ring-2 ring-primary/50 hover:ring-primary transition-all duration-300' } }} />
      </div>
    </div>
  );
}

function MainContent({
  closeEditor,
  currentStyle,
  editingClip,
  handleSkipSubtitlesChange,
  handleStyleChange,
  openClipAdvancedEditor,
  openClipSubtitleEditor,
  subtitleTargetClip,
  subtitlesDisabled,
  viewMode,
}: {
  closeEditor: () => void;
  currentStyle: string;
  editingClip: Clip | null;
  handleSkipSubtitlesChange: (disabled: boolean) => void;
  handleStyleChange: (styleName: string) => void;
  openClipAdvancedEditor: (clip: Clip) => void;
  openClipSubtitleEditor: (clip: Clip) => void;
  subtitleTargetClip: Clip | null;
  subtitlesDisabled: boolean;
  viewMode: AppViewMode;
}) {
  if (editingClip) {
    return <EditorWorkspace closeEditor={closeEditor} editingClip={editingClip} />;
  }

  if (viewMode === 'manual') {
    return <FullWidthWorkspace fallback="Auto Cut yukleniyor..."><AutoCutEditor /></FullWidthWorkspace>;
  }

  if (viewMode === 'subtitle') {
    return (
      <FullWidthWorkspace fallback="Subtitle Editor yukleniyor...">
        <SubtitleEditor targetClip={subtitleTargetClip} lockedToClip={Boolean(subtitleTargetClip)} />
      </FullWidthWorkspace>
    );
  }

  return (
    <ConfigWorkspace
      currentStyle={currentStyle}
      handleSkipSubtitlesChange={handleSkipSubtitlesChange}
      handleStyleChange={handleStyleChange}
      openClipAdvancedEditor={openClipAdvancedEditor}
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
  return (
    <main className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
      <div className="lg:col-span-12 space-y-8 animate-in fade-in duration-700">
        <div className="flex items-center gap-4">
          <IconButton
            label="Geri don"
            icon={<ChevronLeft className="w-4 h-4 text-primary" />}
            onClick={closeEditor}
            className="glass-card border-border border rounded-lg"
          />
          <h2 className="text-xl font-bold font-mono text-primary flex items-center gap-3">
            <span className="opacity-40 text-foreground">SYSTEM:EDITING</span> {editingClip.name}
          </h2>
        </div>
        <Suspense fallback={<LoadingCard label="Editor yukleniyor..." />}>
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
  currentStyle,
  handleSkipSubtitlesChange,
  handleStyleChange,
  openClipAdvancedEditor,
  openClipSubtitleEditor,
  subtitlesDisabled,
}: {
  currentStyle: string;
  handleSkipSubtitlesChange: (disabled: boolean) => void;
  handleStyleChange: (styleName: string) => void;
  openClipAdvancedEditor: (clip: Clip) => void;
  openClipSubtitleEditor: (clip: Clip) => void;
  subtitlesDisabled: boolean;
}) {
  return (
    <main className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
      <div className="lg:col-span-12 grid grid-cols-1 lg:grid-cols-12 gap-8 items-stretch">
        <div className="lg:col-span-5 flex flex-col gap-6">
          <section className="glass-card p-8 border-accent/20 shadow-lg shadow-accent/5 ring-1 ring-accent/10">
            <h2 className="text-xs font-mono uppercase tracking-[0.2em] mb-6 text-accent">Deployment Hub</h2>
            <JobForm onStyleChange={handleStyleChange} onSkipSubtitlesChange={handleSkipSubtitlesChange} />
          </section>
          <SubtitlePreview styleName={currentStyle} disabled={subtitlesDisabled} />
        </div>
        <div className="lg:col-span-7 flex flex-col gap-6">
          <section className="glass-card overflow-hidden opacity-80 hover:opacity-100 transition-opacity duration-300 flex-1 flex flex-col">
            <HoloTerminal />
          </section>
          <JobQueue />
        </div>
      </div>
      <div className="lg:col-span-12">
        <ClipGallery onAdvancedEditClip={openClipAdvancedEditor} onEditClip={openClipSubtitleEditor} />
      </div>
    </main>
  );
}

function AppFooter({ wsStatus }: { wsStatus: WsStatus }) {
  return (
    <footer className="mt-20 pt-8 border-t border-border flex flex-col md:flex-row items-center justify-between gap-4 text-muted-foreground">
      <p className="text-[11px] font-mono uppercase tracking-widest">&copy; 2026 GOD-TIER SHORTS. AI_ARCHITECT_ENABLED</p>
      <ConnectionChip status={wsStatus} />
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
