import { useState, useEffect, useRef, useCallback } from 'react';
import { Video, Download, Edit3, RefreshCw, AlertCircle } from 'lucide-react';
import { clipsApi } from '../api/client';
import { getClipUrl } from '../utils/url';
import type { Clip } from '../types';
import { useJobStore } from '../store/useJobStore';
import { IconButton } from './ui/IconButton';
import { LazyVideo } from './ui/LazyVideo';

interface ClipGalleryProps {
    onEditClip?: (clip: Clip) => void;
}

type GalleryState = 'loading' | 'error' | 'empty' | 'ready';

const POLL_INTERVAL_MS = 30000;

export const ClipGallery = ({ onEditClip }: ClipGalleryProps) => {
    const [clips, setClips] = useState<Clip[]>([]);
    const [state, setState] = useState<GalleryState>('loading');
    const [errorMsg, setErrorMsg] = useState<string | null>(null);
    const hasLoadedOnce = useRef(false);
    const [retryTick, setRetryTick] = useState(0);
    const refreshClipsTrigger = useJobStore((s) => s.refreshClipsTrigger);

    const cancelledRef = useRef(false);
    const fetchClips = useCallback(async () => {
        try {
            const data = await clipsApi.list();
            if (cancelledRef.current) return;
            hasLoadedOnce.current = data.clips.length > 0;
            setClips(data.clips);
            setState(data.clips.length > 0 ? 'ready' : 'empty');
            setErrorMsg(null);
        } catch (err) {
            if (cancelledRef.current) return;
            const msg = err instanceof Error ? err.message : 'Klipler yuklenemedi.';
            setErrorMsg(msg);
            if (!hasLoadedOnce.current) {
                setState('error');
            }
        }
    }, []);

    useEffect(() => {
        cancelledRef.current = false;
        const initialFetchTimer = window.setTimeout(() => {
            void fetchClips();
        }, 0);
        const interval = setInterval(() => void fetchClips(), POLL_INTERVAL_MS);
        return () => {
            cancelledRef.current = true;
            clearTimeout(initialFetchTimer);
            clearInterval(interval);
        };
    }, [retryTick, fetchClips]);

    useEffect(() => {
        if (refreshClipsTrigger <= 0) {
            return;
        }
        const refreshTimer = window.setTimeout(() => {
            void fetchClips();
        }, 0);
        return () => {
            clearTimeout(refreshTimer);
        };
    }, [refreshClipsTrigger, fetchClips]);

    const handleRetry = useCallback(() => {
        setState('loading');
        setRetryTick(t => t + 1);
    }, []);

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h2 className="text-xl font-bold tracking-tighter flex items-center gap-2">
                    <Video className="w-5 h-5 text-primary" aria-hidden="true" />
                    GENERATED CLIPS
                </h2>
                <div className="flex items-center gap-2 bg-primary/5 px-3 py-1 rounded-full border border-primary/10">
                    <span className="w-2 h-2 bg-primary animate-pulse rounded-full" />
                    <span className="text-[11px] font-mono text-primary uppercase">Neural Sync Active</span>
                </div>
            </div>

            {state === 'loading' && (
                <div className="h-40 glass-card flex items-center justify-center" aria-live="polite">
                    <span className="animate-pulse text-xs font-mono text-muted-foreground uppercase tracking-widest">
                        Scanning Outputs...
                    </span>
                </div>
            )}

            {state === 'error' && (
                <div role="alert" className="h-40 glass-card flex flex-col items-center justify-center gap-3 border-red-500/20">
                    <div className="flex items-center gap-2 text-xs text-red-400 font-mono">
                        <AlertCircle className="w-4 h-4" aria-hidden="true" />
                        {errorMsg ?? 'Baglanti hatasi'}
                    </div>
                    <button
                        onClick={handleRetry}
                        className="px-4 py-2 rounded-lg bg-white/5 border border-white/10 hover:bg-white/10 text-xs font-mono uppercase transition-colors flex items-center gap-2"
                        aria-label="Tekrar dene"
                    >
                        <RefreshCw className="w-3 h-3" aria-hidden="true" />
                        Tekrar Dene
                    </button>
                </div>
            )}

            {state === 'empty' && (
                <div className="h-40 glass-card flex flex-col items-center justify-center text-muted-foreground border-dashed border-2">
                    <div className="text-xs font-mono uppercase tracking-widest opacity-60">No viral content detected yet...</div>
                </div>
            )}

            {state === 'ready' && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {clips.map((clip) => (
                        <div key={clip.name} className="glass-card group hover:border-primary/40 transition-all duration-500 overflow-hidden">
                            <div className="aspect-[9/16] bg-black/60 relative overflow-hidden">
                                <LazyVideo
                                    src={getClipUrl(clip)}
                                    className="w-full h-full"
                                />
                                <div className="absolute inset-x-0 bottom-0 p-4 bg-gradient-to-t from-black/80 to-transparent">
                                    <div className="flex items-center justify-between">
                                        <div className="flex flex-col gap-0.5 min-w-0">
                                            {clip.ui_title && (
                                                <div className="text-[11px] font-black text-primary leading-tight truncate uppercase italic">
                                                    {clip.ui_title}
                                                </div>
                                            )}
                                            <div className="text-[11px] font-mono text-white/60 truncate uppercase">{clip.name}</div>
                                        </div>
                                        <div className="flex gap-2">
                                            <IconButton
                                                label="Altyazi duzenle"
                                                icon={<Edit3 className="w-3.5 h-3.5" />}
                                                onClick={() => onEditClip?.(clip)}
                                                variant="primary"
                                            />
                                            <IconButton
                                                label="Indir"
                                                icon={<Download className="w-3.5 h-3.5" />}
                                                href={getClipUrl(clip)}
                                                download
                                                variant="subtle"
                                            />
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};
