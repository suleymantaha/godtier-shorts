import { useState, useId, useEffect } from 'react';
import type { FormEvent } from 'react';
import { useJobStore } from '../store/useJobStore';
import { jobsApi } from '../api/client';
import { STYLE_OPTIONS, STYLE_LABELS } from '../config/subtitleStyles';
import type { StyleName } from '../config/subtitleStyles';
import { Play, Sparkles, Cpu, Zap, AlertCircle, Subtitles } from 'lucide-react';

interface JobFormProps {
    onStyleChange?: (style: string) => void;
    onSkipSubtitlesChange?: (skip: boolean) => void;
}

export const JobForm = ({ onStyleChange, onSkipSubtitlesChange }: JobFormProps = {}) => {
    const [url, setUrl] = useState('');
    const [style, setStyle] = useState<StyleName>('TIKTOK');
    const [engine, setEngine] = useState('local');
    const [skipSubtitles, setSkipSubtitles] = useState(false);
    const [numClips, setNumClips] = useState(8);
    const [autoMode, setAutoMode] = useState(true);
    const [durationMin, setDurationMin] = useState(120);
    const [durationMax, setDurationMax] = useState(180);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const { fetchJobs } = useJobStore();

    const urlId = useId();
    const styleId = useId();
    const engineId = useId();
    const numClipsId = useId();
    const durationMinId = useId();
    const durationMaxId = useId();

    useEffect(() => { onStyleChange?.(style); }, [style, onStyleChange]);
    useEffect(() => { onSkipSubtitlesChange?.(skipSubtitles); }, [skipSubtitles, onSkipSubtitlesChange]);

    const handleStart = async (e: FormEvent) => {
        e.preventDefault();
        if (!url || isSubmitting) return;

        setIsSubmitting(true);
        setError(null);

        try {
            const duration_min = autoMode ? 120 : durationMin;
            const duration_max = autoMode ? 180 : durationMax;
            await jobsApi.start({
                youtube_url: url,
                style_name: style,
                ai_engine: engine,
                skip_subtitles: skipSubtitles,
                num_clips: numClips,
                auto_mode: autoMode,
                duration_min,
                duration_max,
            });
            await fetchJobs();
            setUrl('');
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Job baslatilamadi.';
            setError(message);
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <form onSubmit={handleStart} className="space-y-6">
            <div className="space-y-2">
                <label htmlFor={urlId} className="text-sm font-medium text-muted-foreground uppercase tracking-widest ml-1">
                    YouTube URL
                </label>
                <div className="relative group">
                    <input
                        id={urlId}
                        type="url"
                        value={url}
                        onChange={(e) => setUrl(e.target.value)}
                        placeholder="https://youtube.com/watch?v=..."
                        className="input-field w-full pl-12 group-hover:border-primary/30 transition-all"
                        disabled={isSubmitting}
                        autoComplete="url"
                    />
                    <Play className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-primary/50 pointer-events-none" aria-hidden="true" />
                </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-2">
                    <div className="flex items-center justify-between">
                        <label htmlFor={styleId} className="text-sm font-medium text-muted-foreground uppercase tracking-widest ml-1">
                            Visual Style
                        </label>
                        <button
                            type="button"
                            role="switch"
                            aria-checked={skipSubtitles}
                            aria-label="Altyazi islemeyi atla"
                            onClick={() => setSkipSubtitles(prev => !prev)}
                            className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border-2 transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary ${skipSubtitles ? 'bg-red-500/30 border-red-500/50' : 'bg-primary/20 border-primary/40'}`}
                        >
                            <span
                                className={`pointer-events-none inline-block h-4 w-4 rounded-full shadow-sm transition-transform ${skipSubtitles ? 'translate-x-5 bg-red-400' : 'translate-x-0.5 bg-primary'}`}
                            />
                        </button>
                    </div>
                    <div className="relative">
                        <select
                            id={styleId}
                            value={style}
                            onChange={(e) => setStyle(e.target.value as StyleName)}
                            className={`input-field w-full appearance-none pr-10 transition-opacity ${skipSubtitles ? 'opacity-40 cursor-not-allowed' : ''}`}
                            disabled={isSubmitting || skipSubtitles}
                        >
                            {STYLE_OPTIONS.filter((s) => s !== 'CUSTOM').map((s) => (
                                <option key={s} value={s}>{STYLE_LABELS[s]}</option>
                            ))}
                        </select>
                        <Sparkles className="absolute right-4 top-1/2 -translate-y-1/2 w-4 h-4 text-secondary/50 pointer-events-none" aria-hidden="true" />
                    </div>
                    {skipSubtitles && (
                        <div className="flex items-center gap-1.5 text-[11px] font-mono text-red-400/80">
                            <Subtitles className="w-3 h-3" aria-hidden="true" />
                            Altyazi devre disi
                        </div>
                    )}
                </div>

                <div className="space-y-2">
                    <label htmlFor={engineId} className="text-sm font-medium text-muted-foreground uppercase tracking-widest ml-1">
                        AI Engine
                    </label>
                    <div className="relative">
                        <select
                            id={engineId}
                            value={engine}
                            onChange={(e) => setEngine(e.target.value)}
                            className="input-field w-full appearance-none pr-10"
                            disabled={isSubmitting}
                        >
                            <option value="local">Local (Ollama)</option>
                            <option value="lmstudio">Local (LM Studio)</option>
                            <option value="cloud">Cloud (OpenAI API)</option>
                        </select>
                        <Cpu className="absolute right-4 top-1/2 -translate-y-1/2 w-4 h-4 text-accent/50 pointer-events-none" aria-hidden="true" />
                    </div>
                </div>
            </div>

            <div className="space-y-2">
                <label htmlFor={numClipsId} className="text-sm font-medium text-muted-foreground uppercase tracking-widest ml-1">
                    Video Sayısı
                </label>
                <input
                    id={numClipsId}
                    type="number"
                    min={1}
                    max={20}
                    value={numClips}
                    onChange={(e) => setNumClips(Math.min(20, Math.max(1, Number(e.target.value) || 1)))}
                    className="input-field w-full"
                    disabled={isSubmitting}
                />
            </div>

            <div className="space-y-2">
                <div className="flex items-center justify-between">
                    <label className="text-sm font-medium text-muted-foreground uppercase tracking-widest ml-1">
                        Otomatik mod (120-180 sn)
                    </label>
                    <button
                        type="button"
                        role="switch"
                        aria-checked={autoMode}
                        aria-label="Otomatik mod"
                        onClick={() => setAutoMode((prev) => !prev)}
                        className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border-2 transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary ${autoMode ? 'bg-primary/20 border-primary/40' : 'bg-white/10 border-white/20'}`}
                    >
                        <span
                            className={`pointer-events-none inline-block h-4 w-4 rounded-full shadow-sm transition-transform ${autoMode ? 'translate-x-5 bg-primary' : 'translate-x-0.5 bg-white/60'}`}
                        />
                    </button>
                </div>
                {!autoMode && (
                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-1">
                            <label htmlFor={durationMinId} className="text-xs font-mono text-muted-foreground">
                                Min süre (sn)
                            </label>
                            <input
                                id={durationMinId}
                                type="number"
                                min={30}
                                max={300}
                                value={durationMin}
                                onChange={(e) => setDurationMin(Math.min(300, Math.max(30, Number(e.target.value) || 30)))}
                                className="input-field w-full"
                                disabled={isSubmitting}
                            />
                        </div>
                        <div className="space-y-1">
                            <label htmlFor={durationMaxId} className="text-xs font-mono text-muted-foreground">
                                Max süre (sn)
                            </label>
                            <input
                                id={durationMaxId}
                                type="number"
                                min={30}
                                max={300}
                                value={durationMax}
                                onChange={(e) => setDurationMax(Math.min(300, Math.max(30, Number(e.target.value) || 30)))}
                                className="input-field w-full"
                                disabled={isSubmitting}
                            />
                        </div>
                    </div>
                )}
            </div>

            {error && (
                <div role="alert" className="flex items-center gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-xs font-mono text-red-400">
                    <AlertCircle className="w-4 h-4 shrink-0" aria-hidden="true" />
                    {error}
                </div>
            )}

            <button
                type="submit"
                disabled={isSubmitting || !url}
                className={`btn-primary w-full flex items-center justify-center gap-3 ${isSubmitting ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
                {isSubmitting ? (
                    <>
                        <div className="w-5 h-5 border-2 border-background/30 border-t-background animate-spin rounded-full" />
                        INITIATING...
                    </>
                ) : (
                    <>
                        <Zap className="w-5 h-5" aria-hidden="true" />
                        VİDEOYU ÜRET
                    </>
                )}
            </button>
        </form>
    );
};
