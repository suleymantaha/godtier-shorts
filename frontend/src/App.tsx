import { JobForm } from './components/JobForm';
import { HoloTerminal } from './components/HoloTerminal';
import { ClipGallery } from './components/ClipGallery';
import { JobQueue } from './components/JobQueue';
import { Editor } from './components/Editor';
import { AutoCutEditor } from './components/AutoCutEditor';
import { SubtitleEditor } from './components/SubtitleEditor';
import { SubtitlePreview } from './components/SubtitlePreview';
import { useWebSocket } from './hooks/useWebSocket';
import { Layers, Github, Twitter, Scissors, Settings, ChevronLeft, Subtitles } from 'lucide-react';
import { IconButton } from './components/ui/IconButton';
import { ConnectionChip } from './components/ui/ConnectionChip';
import { useCallback, useEffect, useState } from 'react';
import type { Clip } from './types';
import { useJobStore } from './store/useJobStore';
import { readStored } from './utils/storage';

const APP_STATE_STORAGE_KEY = 'godtier-app-state';
const DEFAULT_APP_STATE = { viewMode: 'config' as const, editingClip: null as Clip | null };

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
  useWebSocket();
  const wsStatus = useJobStore(s => s.wsStatus);
  const [viewMode, setViewMode] = useState<'config' | 'manual' | 'subtitle'>(() => readAppState().viewMode);
  const [editingClip, setEditingClip] = useState<Clip | null>(() => readAppState().editingClip);
  const [currentStyle, setCurrentStyle] = useState('TIKTOK');
  const [subtitlesDisabled, setSubtitlesDisabled] = useState(false);

  const handleStyleChange = useCallback((s: string) => setCurrentStyle(s), []);
  const handleSkipSubtitlesChange = useCallback((v: boolean) => setSubtitlesDisabled(v), []);

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
    <div className="min-h-screen bg-transparent px-4 py-4 md:px-8 md:py-6 lg:px-12 lg:py-8 space-y-8 mx-auto w-full">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between px-2">
        <div className="flex flex-col">
          <h1 className="text-2xl sm:text-4xl font-black tracking-tighter bg-clip-text text-transparent bg-gradient-to-r from-white via-white to-white/40 flex items-center gap-3">
            <div className="w-8 h-8 sm:w-10 sm:h-10 bg-primary rounded-xl flex items-center justify-center rotate-3 border-r-4 border-b-4 border-white shrink-0">
              <Layers className="text-black w-5 h-5 sm:w-6 sm:h-6" />
            </div>
            GOD-TIER SHORTS
          </h1>
          <div className="flex items-center gap-2 mt-1 px-1">
            <span className="text-[11px] font-mono uppercase tracking-[0.3em] text-accent/80 font-bold">AI Video Architect</span>
            <div className="h-[1px] w-8 bg-accent/30" />
            <span className="text-[11px] font-mono text-muted-foreground">V 1.0</span>
          </div>
        </div>

        <div className="flex items-center gap-4 sm:gap-6">
          <nav className="flex p-1 glass-card rounded-xl border-accent/20" aria-label="Ana navigasyon">
            <button
              onClick={() => { setViewMode('config'); setEditingClip(null); }}
              aria-current={viewMode === 'config' && !editingClip ? 'page' : undefined}
              className={`px-4 sm:px-6 py-2 rounded-lg text-xs font-mono transition-all duration-300 flex items-center gap-2 ${viewMode === 'config' && !editingClip ? 'bg-accent/20 text-white shadow-lg shadow-accent/10 border border-accent/30' : 'text-white/60 hover:text-white/80'}`}
            >
              <Settings className="w-3 h-3" aria-hidden="true" />
              CONFIGURE
            </button>
            <button
              onClick={() => { setViewMode('manual'); setEditingClip(null); }}
              aria-current={viewMode === 'manual' && !editingClip ? 'page' : undefined}
              className={`px-4 sm:px-6 py-2 rounded-lg text-xs font-mono transition-all duration-300 flex items-center gap-2 ${viewMode === 'manual' && !editingClip ? 'bg-primary/20 text-white shadow-lg shadow-primary/10 border border-primary/30' : 'text-white/60 hover:text-white/80'}`}
            >
              <Scissors className="w-3 h-3" aria-hidden="true" />
              AUTO CUT
            </button>
            <button
              onClick={() => { setViewMode('subtitle'); setEditingClip(null); }}
              aria-current={viewMode === 'subtitle' ? 'page' : undefined}
              className={`px-4 sm:px-6 py-2 rounded-lg text-xs font-mono transition-all duration-300 flex items-center gap-2 ${viewMode === 'subtitle' ? 'bg-accent/20 text-white shadow-lg shadow-accent/10 border border-accent/30' : 'text-white/60 hover:text-white/80'}`}
            >
              <Subtitles className="w-3 h-3" aria-hidden="true" />
              SUBTITLE EDIT
            </button>
          </nav>
          <div className="hidden sm:flex gap-2 border-l border-white/10 pl-4">
            <IconButton label="GitHub" icon={<Github className="w-4 h-4" />} href="https://github.com" variant="ghost" />
            <IconButton label="Twitter" icon={<Twitter className="w-4 h-4" />} href="https://twitter.com" variant="ghost" />
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
                className="glass-card border-white/10 border rounded-lg"
              />
              <h2 className="text-xl font-bold font-mono text-primary flex items-center gap-3">
                <span className="opacity-40 text-white">SYSTEM:EDITING</span> {editingClip.name}
              </h2>
            </div>
            <Editor mode="clip" targetClip={editingClip} onClose={() => setEditingClip(null)} />
          </div>
        ) : viewMode === 'manual' ? (
          <div className="lg:col-span-12">
            <AutoCutEditor />
          </div>
        ) : viewMode === 'subtitle' ? (
          <div className="lg:col-span-12">
            <SubtitleEditor />
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

      <footer className="mt-20 pt-8 border-t border-white/5 flex flex-col md:flex-row items-center justify-between gap-4 text-muted-foreground">
        <p className="text-[11px] font-mono uppercase tracking-widest">&copy; 2026 GOD-TIER SHORTS. AI_ARCHITECT_ENABLED</p>
        <ConnectionChip status={wsStatus} />
      </footer>
    </div>
  );
}

export default App;
