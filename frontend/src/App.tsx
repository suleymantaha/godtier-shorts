import { JobForm } from './components/JobForm';
import { HoloTerminal } from './components/HoloTerminal';
import { ClipGallery } from './components/ClipGallery';
import { JobQueue } from './components/JobQueue';
import { SubtitlePreview } from './components/SubtitlePreview';
import { useWebSocket } from './hooks/useWebSocket';
import { Layers, Github, Twitter, Scissors, Settings, ChevronLeft, Subtitles, Sun, Moon } from 'lucide-react';
import { IconButton } from './components/ui/IconButton';
import { ConnectionChip } from './components/ui/ConnectionChip';
import { Suspense, lazy, useCallback, useEffect, useState } from 'react';
import type { Clip } from './types';
import { useJobStore } from './store/useJobStore';
import { useThemeStore } from './store/useThemeStore';
import { readStored } from './utils/storage';
import { SignedIn, SignedOut, SignIn, UserButton, useAuth } from '@clerk/clerk-react';
import { setApiToken } from './api/client';
import { CLERK_JWT_TEMPLATE } from './config';
const APP_STATE_STORAGE_KEY = 'godtier-app-state';
const DEFAULT_APP_STATE = { viewMode: 'config' as const, editingClip: null as Clip | null };
const ThreeCanvas = lazy(() => import('./components/ThreeCanvas'));
const Editor = lazy(() => import('./components/Editor').then((m) => ({ default: m.Editor })));
const AutoCutEditor = lazy(() => import('./components/AutoCutEditor').then((m) => ({ default: m.AutoCutEditor })));
const SubtitleEditor = lazy(() => import('./components/SubtitleEditor').then((m) => ({ default: m.SubtitleEditor })));

function readAppState(): { viewMode: 'config' | 'manual' | 'subtitle'; editingClip: Clip | null } {
  const parsed = readStored<{ viewMode?: string; editingClip?: Clip | null }>(
    APP_STATE_STORAGE_KEY,
    DEFAULT_APP_STATE
  );
  const mode = parsed.viewMode === 'manual' ? 'manual' : parsed.viewMode === 'subtitle' ? 'subtitle' : 'config';
  return {
    viewMode: mode,
    editingClip: parsed.editingClip ?? null,
  };
}

function App() {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  useWebSocket(isLoaded && isSignedIn);
  const wsStatus = useJobStore(s => s.wsStatus);
  const [viewMode, setViewMode] = useState<'config' | 'manual' | 'subtitle'>(() => readAppState().viewMode);
  const [editingClip, setEditingClip] = useState<Clip | null>(() => readAppState().editingClip);
  const [currentStyle, setCurrentStyle] = useState('TIKTOK');
  const [subtitlesDisabled, setSubtitlesDisabled] = useState(false);
  const { theme, toggleTheme } = useThemeStore();

  const handleStyleChange = useCallback((s: string) => setCurrentStyle(s), []);
  const handleSkipSubtitlesChange = useCallback((v: boolean) => setSubtitlesDisabled(v), []);
  
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  useEffect(() => {
    if (isLoaded && isSignedIn) {
       if (CLERK_JWT_TEMPLATE) {
         getToken({ template: CLERK_JWT_TEMPLATE }).then(token => setApiToken(token));
       } else {
         getToken().then(token => setApiToken(token));
       }
    } else {
       setApiToken(null);
    }
  }, [isLoaded, isSignedIn, getToken]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    window.localStorage.setItem(
      APP_STATE_STORAGE_KEY,
      JSON.stringify({ viewMode, editingClip }),
    );
  }, [viewMode, editingClip]);

  return (
    <>
      <Suspense fallback={null}>
        <ThreeCanvas />
      </Suspense>
      <div className="min-h-screen bg-transparent px-4 py-4 md:px-8 md:py-6 lg:px-12 lg:py-8 space-y-8 mx-auto w-full">
        <SignedOut>
        <div className="flex w-full h-[80vh] items-center justify-center animate-in fade-in duration-1000">
            <SignIn appearance={{
              elements: {
                rootBox: "mx-auto shadow-2xl shadow-primary/20",
                card: "bg-card backdrop-blur-3xl border border-foreground/10 rounded-2xl",
                headerTitle: "text-foreground font-outfit text-2xl font-bold",
                headerSubtitle: "text-muted-foreground",
                socialButtonsBlockButton: "border-border text-foreground hover:bg-foreground/5",
                dividerLine: "bg-border",
                dividerText: "text-muted-foreground",
                formFieldLabel: "text-foreground",
                formFieldInput: "bg-foreground/5 border border-border text-foreground",
                formButtonPrimary: "bg-primary text-primary-foreground hover:bg-primary/90 transition-all font-bold",
                footerActionText: "text-muted-foreground",
                footerActionLink: "text-primary hover:text-primary/80"
              }
            }} />
        </div>
      </SignedOut>

      <SignedIn>
        <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between px-2">
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

        <div className="flex items-center gap-4 sm:gap-6">
          <nav className="flex p-1 glass-card rounded-xl border-accent/20" aria-label="Ana navigasyon">
            <button
              onClick={() => { setViewMode('config'); setEditingClip(null); }}
              aria-current={viewMode === 'config' && !editingClip ? 'page' : undefined}
              className={`px-4 sm:px-6 py-2 rounded-lg text-xs font-mono transition-all duration-300 flex items-center gap-2 ${viewMode === 'config' && !editingClip ? 'bg-accent/20 text-foreground shadow-lg shadow-accent/10 border border-accent/30' : 'text-muted-foreground hover:text-foreground'}`}
            >
              <Settings className="w-3 h-3" aria-hidden="true" />
              CONFIGURE
            </button>
            <button
              onClick={() => { setViewMode('manual'); setEditingClip(null); }}
              aria-current={viewMode === 'manual' && !editingClip ? 'page' : undefined}
              className={`px-4 sm:px-6 py-2 rounded-lg text-xs font-mono transition-all duration-300 flex items-center gap-2 ${viewMode === 'manual' && !editingClip ? 'bg-primary/20 text-foreground shadow-lg shadow-primary/10 border border-primary/30' : 'text-muted-foreground hover:text-foreground'}`}
            >
              <Scissors className="w-3 h-3" aria-hidden="true" />
              AUTO CUT
            </button>
            <button
              onClick={() => { setViewMode('subtitle'); setEditingClip(null); }}
              aria-current={viewMode === 'subtitle' ? 'page' : undefined}
              className={`px-4 sm:px-6 py-2 rounded-lg text-xs font-mono transition-all duration-300 flex items-center gap-2 ${viewMode === 'subtitle' ? 'bg-accent/20 text-foreground shadow-lg shadow-accent/10 border border-accent/30' : 'text-muted-foreground hover:text-foreground'}`}
            >
              <Subtitles className="w-3 h-3" aria-hidden="true" />
              SUBTITLE EDIT
            </button>
          </nav>
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
              <UserButton appearance={{
                elements: {
                  userButtonAvatarBox: "w-8 h-8 ring-2 ring-primary/50 hover:ring-primary transition-all duration-300"
                }
              }} />
            </div>
          </div>
        </div>
      </header>

      <main className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {editingClip ? (
          <div className="lg:col-span-12 space-y-8 animate-in fade-in duration-700">
            <div className="flex items-center gap-4">
              <IconButton
                label="Geri don"
                icon={<ChevronLeft className="w-4 h-4 text-primary" />}
                onClick={() => setEditingClip(null)}
                className="glass-card border-border border rounded-lg"
              />
              <h2 className="text-xl font-bold font-mono text-primary flex items-center gap-3">
                <span className="opacity-40 text-foreground">SYSTEM:EDITING</span> {editingClip.name}
              </h2>
            </div>
            <Suspense fallback={<div className="glass-card p-4 text-xs font-mono">Editor yukleniyor...</div>}>
              <Editor mode="clip" targetClip={editingClip} onClose={() => setEditingClip(null)} />
            </Suspense>
          </div>
        ) : viewMode === 'manual' ? (
          <div className="lg:col-span-12">
            <Suspense fallback={<div className="glass-card p-4 text-xs font-mono">Auto Cut yukleniyor...</div>}>
              <AutoCutEditor />
            </Suspense>
          </div>
        ) : viewMode === 'subtitle' ? (
          <div className="lg:col-span-12">
            <Suspense fallback={<div className="glass-card p-4 text-xs font-mono">Subtitle Editor yukleniyor...</div>}>
              <SubtitleEditor />
            </Suspense>
          </div>
        ) : (
          <>
            {/* Ust satir: Form (sol) + Terminal & JobQueue (sag) */}
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
            {/* Alt satir: ClipGallery tam genislik */}
            <div className="lg:col-span-12">
              <ClipGallery onEditClip={(clip) => setEditingClip(clip)} />
            </div>
          </>
        )}
      </main>

      <footer className="mt-20 pt-8 border-t border-border flex flex-col md:flex-row items-center justify-between gap-4 text-muted-foreground">
        <p className="text-[11px] font-mono uppercase tracking-widest">&copy; 2026 GOD-TIER SHORTS. AI_ARCHITECT_ENABLED</p>
        <ConnectionChip status={wsStatus} />
      </footer>
      </SignedIn>
      </div>
    </>
  );
}

export default App;
