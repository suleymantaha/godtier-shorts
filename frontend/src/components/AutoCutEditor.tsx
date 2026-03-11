import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
    AlertCircle,
    CheckCircle2,
    ChevronRight,
    Clock,
    Film,
    Loader2,
    Plus,
    Scissors,
    Sparkles,
    Subtitles,
    X,
} from 'lucide-react';

import { editorApi } from '../api/client';
import { API_BASE } from '../config';
import { getClipUrl } from '../utils/url';
import { getQueuePosition, isProjectBusy } from '../utils/jobQueue';
import { useJobStore } from '../store/useJobStore';
import { STYLE_OPTIONS, isStyleName } from '../config/subtitleStyles';
import type { StyleName } from '../config/subtitleStyles';
import { RangeSlider } from './RangeSlider';
import { SubtitlePreview } from './SubtitlePreview';
import { VideoControls } from './ui/VideoControls';
import { Select } from './ui/Select';
import { toTimeStr } from '../utils/time';
import { readStored } from '../utils/storage';

const AUTO_CUT_SESSION_KEY = 'godtier-auto-cut-session';

interface StoredAutoCutSession {
    currentJobId?: string | null;
    projectId?: string;
    startTime?: number;
    endTime?: number;
}

function readStoredAutoCutSession(): StoredAutoCutSession | null {
    return readStored<StoredAutoCutSession | null>(AUTO_CUT_SESSION_KEY, null);
}

export const AutoCutEditor: React.FC = () => {
    const initialSession = useMemo(() => readStoredAutoCutSession(), []);
    const { jobs, fetchJobs } = useJobStore();

    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [localSrc, setLocalSrc] = useState<string | null>(null);
    const [projectId, setProjectId] = useState<string | undefined>(initialSession?.projectId);
    const [currentJobId, setCurrentJobId] = useState<string | null>(initialSession?.currentJobId ?? null);
    const [pendingOutputUrl, setPendingOutputUrl] = useState<string | null>(null);
    const [requestError, setRequestError] = useState<string | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);

    const [startTime, setStartTime] = useState(initialSession?.startTime ?? 0);
    const [endTime, setEndTime] = useState(initialSession?.endTime ?? 60);
    const [duration, setDuration] = useState(0);
    const [isPlaying, setIsPlaying] = useState(false);
    const [style, setStyle] = useState<StyleName>('TIKTOK');
    const [skipSubtitles, setSkipSubtitles] = useState(false);
    const [cutAsShort, setCutAsShort] = useState(true);
    const [numClips, setNumClips] = useState(3);
    const [markers, setMarkers] = useState<number[]>([]);
    const [kesFeedback, setKesFeedback] = useState<string | null>(null);

    const fileInputRef = useRef<HTMLInputElement>(null);
    const videoRef = useRef<HTMLVideoElement>(null);

    const currentJob = useMemo(
        () => (currentJobId ? jobs.find((job) => job.job_id === currentJobId) ?? null : null),
        [currentJobId, jobs],
    );

    useEffect(() => {
        const syncJobs = async () => {
            await fetchJobs();
            if (currentJobId) {
                const found = useJobStore.getState().jobs.some(j => j.job_id === currentJobId);
                if (!found) {
                    setCurrentJobId(null);
                    setProjectId(undefined);
                    setPendingOutputUrl(null);
                    window.localStorage.removeItem(AUTO_CUT_SESSION_KEY);
                }
            }
        };
        void syncJobs();
    }, []);

    const busy = isProjectBusy(projectId, jobs);
    const queuePosition = currentJobId ? getQueuePosition(currentJobId, jobs) : null;
    const hasTerminalJob = currentJob?.status === 'completed'
        || currentJob?.status === 'cancelled'
        || currentJob?.status === 'error';
    const processing = isSubmitting || (Boolean(currentJobId) && !hasTerminalJob);
    const errorMessage = requestError
        ?? (
            currentJob?.status === 'cancelled' || currentJob?.status === 'error'
                ? currentJob.error ?? currentJob.last_message ?? 'Islem tamamlanamadi.'
                : null
        );
    const resultUrl = currentJob?.status === 'completed'
        ? (
            currentJob.output_url
            ?? (
                currentJob.project_id && currentJob.clip_name
                    ? `/api/projects/${currentJob.project_id}/shorts/${currentJob.clip_name}`
                    : pendingOutputUrl
            )
        )
        : null;

    useEffect(() => {
        if (typeof window === 'undefined') {
            return;
        }

        if (processing && currentJobId) {
            window.localStorage.setItem(
                AUTO_CUT_SESSION_KEY,
                JSON.stringify({
                    currentJobId,
                    projectId,
                    startTime,
                    endTime,
                } satisfies StoredAutoCutSession),
            );
            return;
        }

        window.localStorage.removeItem(AUTO_CUT_SESSION_KEY);
    }, [currentJobId, endTime, processing, projectId, startTime]);

    useEffect(() => {
        return () => {
            if (localSrc) {
                URL.revokeObjectURL(localSrc);
            }
        };
    }, [localSrc]);

    const videoSrc = localSrc ?? (projectId ? `${API_BASE}/api/projects/${projectId}/master` : undefined);
    const resultVideoSrc = resultUrl ? getClipUrl({ url: resultUrl }) : undefined;

    const togglePlay = useCallback(() => {
        if (!videoRef.current) {
            return;
        }

        if (videoRef.current.paused) {
            void videoRef.current.play();
            return;
        }

        videoRef.current.pause();
    }, []);

    const handleFileSelect = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) {
            return;
        }

        setSelectedFile(file);
        setProjectId(undefined);
        setCurrentJobId(null);
        setPendingOutputUrl(null);
        setRequestError(null);
        setMarkers([]);

        setLocalSrc((prev) => {
            if (prev) {
                URL.revokeObjectURL(prev);
            }
            return URL.createObjectURL(file);
        });
    }, []);

    const handleRender = useCallback(async () => {
        if (!selectedFile) {
            setRequestError('Once bir video sec.');
            return;
        }

        if (endTime <= startTime) {
            setRequestError('Bitis zamani baslangictan buyuk olmali.');
            return;
        }

        setIsSubmitting(true);
        setRequestError(null);
        setPendingOutputUrl(null);

        const inRange = markers.filter((m) => m > startTime && m < endTime);
        const cutPoints =
            inRange.length > 0
                ? [startTime, ...inRange.sort((a, b) => a - b), endTime]
                : undefined;

        const useFullVideoForAI = numClips > 1 && !cutPoints && duration > 0;
        const effectiveStart = useFullVideoForAI ? 0 : startTime;
        const effectiveEnd = useFullVideoForAI ? duration : endTime;

        try {
            const response = await editorApi.manualCutUpload(selectedFile, {
                start_time: effectiveStart,
                end_time: effectiveEnd,
                style_name: style,
                skip_subtitles: skipSubtitles,
                num_clips: cutPoints ? cutPoints.length - 1 : numClips,
                cut_points: cutPoints,
                cut_as_short: cutAsShort,
            });

            setProjectId(response.project_id);
            setCurrentJobId(response.job_id);
            setPendingOutputUrl(response.output_url ?? null);
            setIsSubmitting(false);
            await fetchJobs();
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Otomatik manual cut baslatilamadi.';
            setRequestError(message);
            setIsSubmitting(false);
        }
    }, [cutAsShort, duration, endTime, fetchJobs, markers, numClips, selectedFile, skipSubtitles, startTime, style]);

    return (
        <div className="space-y-6 animate-in fade-in duration-500">
            <div className="glass-card p-5 border-accent/20">
                <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                    <div className="space-y-1">
                        <div className="flex items-center gap-2">
                            <Film className="w-4 h-4 text-accent" />
                            <h3 className="text-xs font-mono uppercase tracking-[0.2em] text-accent">
                                Otomatik Manual Cut
                            </h3>
                        </div>
                        <p className="text-[11px] uppercase text-muted-foreground">
                            Video sec, zaman araligini belirle, short pipeline geri kalanini otomatik tamamlasin.
                        </p>
                    </div>

                    <div className="flex items-center gap-2">
                        <input
                            ref={fileInputRef}
                            type="file"
                            accept="video/*"
                            onChange={handleFileSelect}
                            className="hidden"
                        />
                        <button
                            onClick={() => fileInputRef.current?.click()}
                            disabled={processing}
                            className="btn-primary py-2 px-5 text-[11px] tracking-[0.2em] disabled:opacity-50"
                        >
                            {selectedFile ? 'VIDEOYU DEGISTIR' : 'VIDEO SEC'}
                        </button>
                    </div>
                </div>

                <div className="mt-4 rounded-xl border border-border bg-foreground/5 px-4 py-3 text-xs text-muted-foreground">
                    {selectedFile ? (
                        <span className="font-mono text-foreground/80">{selectedFile.name}</span>
                    ) : projectId ? (
                        <span className="font-mono text-foreground/80">Proje: {projectId}</span>
                    ) : (
                        'Henüz video seçilmedi.'
                    )}
                </div>
            </div>

            <div className="glass-card overflow-hidden border-primary/20 shadow-lg shadow-primary/5 ring-1 ring-primary/10">
                <div className="aspect-video bg-background/80 relative group">
                    {videoSrc ? (
                        <>
                            <video
                                ref={videoRef}
                                src={videoSrc}
                                className="w-full h-full object-contain"
                                onLoadedMetadata={(event) => {
                                    const mediaDuration = event.currentTarget.duration;
                                    setDuration(mediaDuration);
                                    setStartTime((prev) => Math.max(0, Math.min(prev, Math.max(0, mediaDuration - 0.5))));
                                    setEndTime((prev) => {
                                        if (prev > 0 && prev <= mediaDuration) {
                                            return prev;
                                        }
                                        return Math.min(60, mediaDuration);
                                    });
                                }}
                                onPlay={() => setIsPlaying(true)}
                                onPause={() => setIsPlaying(false)}
                                controls={false}
                            />

                            <VideoControls isPlaying={isPlaying} onTogglePlay={togglePlay} />
                        </>
                    ) : (
                        <div className="absolute inset-0 flex items-center justify-center p-8">
                            <div className="w-full max-w-xl rounded-2xl border border-dashed border-border bg-foreground/5 px-6 py-10 text-center">
                                <Scissors className="w-8 h-8 text-primary mx-auto mb-3" />
                                <p className="text-sm font-semibold text-foreground">Bos baslangic hazir</p>
                                <p className="mt-2 text-xs text-muted-foreground">
                                    Manual cut ekrani sadece video yuklendikten sonra aktif olur.
                                </p>
                            </div>
                        </div>
                    )}
                </div>

                <div className="p-5 bg-foreground/5 space-y-6">
                    <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-muted-foreground">
                        <Clock className="w-3 h-3" />
                        <span>Kesim Araligi</span>
                        <span className="ml-auto text-primary font-semibold">
                            {toTimeStr(startTime)} - {toTimeStr(endTime)}
                            <span className="text-muted-foreground ml-1">({Math.max(0, endTime - startTime).toFixed(1)}s)</span>
                        </span>
                    </div>

                    {videoSrc ? (
                        <>
                            <RangeSlider
                                min={0}
                                max={duration || 100}
                                start={startTime}
                                end={endTime}
                                onChange={(nextStart, nextEnd) => {
                                    setStartTime(nextStart);
                                    setEndTime(nextEnd);
                                }}
                            />

                            <div className="flex gap-2">
                                <button
                                    onClick={() => {
                                        if (videoRef.current) {
                                            videoRef.current.currentTime = startTime;
                                        }
                                    }}
                                    className="flex-1 py-1.5 text-[11px] font-mono uppercase tracking-widest bg-primary/10 border border-primary/20 rounded hover:bg-primary/20 transition-colors text-primary"
                                >
                                    Basi izle
                                </button>
                                <button
                                    onClick={() => {
                                        if (videoRef.current) {
                                            videoRef.current.currentTime = Math.max(startTime, endTime - 3);
                                        }
                                    }}
                                    className="flex-1 py-1.5 text-[11px] font-mono uppercase tracking-widest bg-accent/10 border border-accent/20 rounded hover:bg-accent/20 transition-colors text-accent"
                                >
                                    Sonu izle
                                </button>
                                <button
                                    onClick={() => {
                                        setKesFeedback(null);
                                        if (!videoRef.current) {
                                            setKesFeedback('Video yukleniyor...');
                                            return;
                                        }
                                        const t = videoRef.current.currentTime;
                                        const inRange = t > startTime + 0.1 && t < endTime - 0.1;
                                        if (!inRange) {
                                            setKesFeedback('Once videoyu oynatip kesmek istediginiz zamana gidin.');
                                            return;
                                        }
                                        const near = markers.some((m) => Math.abs(m - t) < 0.5);
                                        if (near) {
                                            setKesFeedback('Bu noktada zaten kesim var.');
                                            return;
                                        }
                                        setMarkers((prev) => [...prev, t].sort((a, b) => a - b));
                                        setKesFeedback('Kesim noktasi eklendi.');
                                        setTimeout(() => setKesFeedback(null), 2000);
                                    }}
                                    className="py-1.5 px-3 text-[11px] font-mono uppercase tracking-widest bg-secondary/10 border border-secondary/20 rounded hover:bg-secondary/20 transition-colors text-secondary flex items-center gap-1.5"
                                    title="Mevcut zamana kesim noktasi ekle"
                                >
                                    <Plus className="w-3 h-3" />
                                    Kes
                                </button>
                            </div>
                            {kesFeedback && (
                                <p className="text-[11px] font-mono text-secondary/90 animate-in fade-in">
                                    {kesFeedback}
                                </p>
                            )}
                            {markers.length > 0 && (
                                <div className="space-y-2">
                                    <span className="text-[11px] text-muted-foreground uppercase">
                                        Kesim noktalari ({markers.length + 1} klip)
                                    </span>
                                    <div className="flex flex-wrap gap-2">
                                        {markers.map((m, i) => (
                                            <span
                                                key={`${m}-${i}`}
                                                className="inline-flex items-center gap-1.5 rounded-lg bg-foreground/10 px-2 py-1 text-[11px] font-mono"
                                            >
                                                {toTimeStr(m)}
                                                <button
                                                    type="button"
                                                    onClick={() => setMarkers((prev) => prev.filter((_, j) => j !== i))}
                                                    className="hover:bg-foreground/20 rounded p-0.5"
                                                    aria-label="Sil"
                                                >
                                                    <X className="w-3 h-3" />
                                                </button>
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </>
                    ) : (
                        <div className="rounded-xl border border-border bg-foreground/5 px-4 py-6 text-center text-xs text-muted-foreground">
                            Zaman araligi secmek icin once video yukle.
                        </div>
                    )}
                </div>
            </div>

            {videoSrc && (
                <div className="glass-card p-5 space-y-4 border-secondary/20">
                    <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-[0.2em] text-secondary">
                        <Sparkles className="w-4 h-4" />
                        Altyazi Stili & Uretim
                    </div>
                    <div className="flex flex-col sm:flex-row gap-4">
                        <div className="flex-1 space-y-2">
                            <div className="flex items-center justify-between gap-2">
                                <label className="text-[11px] text-muted-foreground uppercase" title="Yatay videolari TikTok/Reels formatina donusturur. Kapaliyken sadece sure kesilir.">
                                    Short olarak kes (9:16)
                                </label>
                                <button
                                    type="button"
                                    role="switch"
                                    aria-checked={cutAsShort}
                                    aria-label="Short olarak kes"
                                    title="Yatay videolari dikey 9:16 formata donusturur. Kapaliyken orijinal boyut korunur."
                                    onClick={() => setCutAsShort((prev) => !prev)}
                                    className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border-2 transition-colors ${cutAsShort ? 'bg-primary/20 border-primary/40' : 'bg-foreground/10 border-border'}`}
                                >
                                    <span
                                        className={`pointer-events-none inline-block h-4 w-4 rounded-full shadow-sm transition-transform ${cutAsShort ? 'translate-x-5 bg-primary' : 'translate-x-0.5 bg-foreground/60'}`}
                                    />
                                </button>
                            </div>
                            <div className="flex items-center justify-between">
                                <label className="text-[11px] text-muted-foreground uppercase">Stil</label>
                                <button
                                    type="button"
                                    role="switch"
                                    aria-checked={skipSubtitles}
                                    aria-label="Altyazi atla"
                                    onClick={() => setSkipSubtitles((prev) => !prev)}
                                    className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border-2 transition-colors ${skipSubtitles ? 'bg-red-500/30 border-red-500/50' : 'bg-primary/20 border-primary/40'}`}
                                >
                                    <span
                                        className={`pointer-events-none inline-block h-4 w-4 rounded-full shadow-sm transition-transform ${skipSubtitles ? 'translate-x-5 bg-red-400' : 'translate-x-0.5 bg-primary'}`}
                                    />
                                </button>
                            </div>
                            <Select
                                value={style}
                                onChange={(val) => setStyle(isStyleName(val) ? val : 'HORMOZI')}
                                options={STYLE_OPTIONS.filter((s) => s !== 'CUSTOM').map((s) => ({
                                    value: s,
                                    label: s
                                }))}
                                disabled={skipSubtitles}
                                className={skipSubtitles ? 'opacity-40' : ''}
                            />
                            {skipSubtitles && (
                                <div className="flex items-center gap-1.5 text-[11px] font-mono text-red-400/80">
                                    <Subtitles className="w-3 h-3" />
                                    Altyazi devre disi
                                </div>
                            )}
                        </div>
                        <div className="flex-1 space-y-2">
                            <label className="text-[11px] text-muted-foreground uppercase block">
                                {markers.length > 0 ? 'Kesim noktalari' : 'Klip sayisi (AI)'}
                            </label>
                            {markers.length > 0 ? (
                                <p className="text-xs font-mono text-primary">
                                    {markers.length + 1} klip (manuel kesim)
                                </p>
                            ) : (
                                <>
                                    <input
                                        type="number"
                                        min={1}
                                        max={10}
                                        value={numClips}
                                        onChange={(e) => setNumClips(Math.min(10, Math.max(1, Number(e.target.value) || 1)))}
                                        className="input-field w-full text-xs"
                                    />
                                    <p className="text-[10px] text-muted-foreground">
                                        {numClips === 1 ? 'Tek klip (secili aralik)' : `AI tum videodan ${numClips} viral klip uretir`}
                                    </p>
                                </>
                            )}
                        </div>
                        {!skipSubtitles && (
                            <div className="sm:w-48 shrink-0">
                                <SubtitlePreview styleName={style} disabled={false} />
                            </div>
                        )}
                    </div>
                </div>
            )}

            {(currentJobId || currentJob || errorMessage) && (
                <div className="glass-card p-5 space-y-4 border-secondary/20">
                    <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-[0.2em] text-secondary">
                        {processing ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
                        Is Durumu
                    </div>

                    {currentJob ? (
                        <div className="space-y-2">
                            <div className="flex items-center justify-between text-xs font-mono text-muted-foreground">
                                <span>{currentJob.last_message}</span>
                                <span>{Math.round(currentJob.progress)}%</span>
                            </div>
                            <div className="h-2 rounded-full bg-foreground/5 overflow-hidden">
                                <div
                                    className="h-full bg-gradient-to-r from-primary to-accent transition-all duration-500"
                                    style={{ width: `${currentJob.progress}%` }}
                                />
                            </div>
                        </div>
                    ) : currentJobId ? (
                        <div className="text-xs font-mono text-muted-foreground">
                            Job baglandi: {currentJobId}
                        </div>
                    ) : null}

                    {queuePosition != null && queuePosition > 1 && (
                        <div className="rounded-md border border-border px-3 py-2 text-sm text-muted-foreground">
                            GPU kuyruğunda sıra: {queuePosition}
                        </div>
                    )}

                    {errorMessage && (
                        <div className="flex items-center gap-2 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-3 text-xs text-red-300">
                            <AlertCircle className="w-4 h-4 shrink-0" />
                            <span>{errorMessage}</span>
                        </div>
                    )}
                </div>
            )}

            {resultVideoSrc && (
                <div className="glass-card p-5 space-y-4 border-green-500/20">
                    <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-[0.2em] text-green-300">
                        <CheckCircle2 className="w-4 h-4" />
                        {(currentJob?.num_clips ?? 1) > 1
                            ? `${currentJob?.num_clips ?? 0} Klip Uretildi`
                            : 'Uretilen Klip'}
                    </div>
                    {(currentJob?.num_clips ?? 1) > 1 && (
                        <p className="text-[11px] text-muted-foreground">
                            Tum klipler ClipGallery&apos;de goruntulenir. Ilk klip asagida.
                        </p>
                    )}
                    <video src={resultVideoSrc} controls className="w-full rounded-xl bg-background/90" />
                    <a
                        href={resultVideoSrc}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-2 rounded-lg border border-border bg-foreground/5 px-4 py-2 text-[11px] font-mono uppercase tracking-[0.2em] text-foreground/80 hover:bg-foreground/10"
                    >
                        Ciktiyi ac
                    </a>
                </div>
            )}

            <div className="glass-card p-5 space-y-4 border-primary/20">
                <div className="space-y-1">
                    <h3 className="text-xs font-mono uppercase tracking-[0.2em] text-primary">
                        {markers.length > 0
                            ? 'Kesim Noktalari ile Render'
                            : numClips > 1
                              ? 'AI ile Toplu Render'
                              : 'Tek Adim Render'}
                    </h3>
                    <p className="text-xs text-muted-foreground">
                        {markers.length > 0
                            ? `${markers.length + 1} klip, belirlediginiz kesim noktalarina gore uretilir.`
                            : numClips > 1
                              ? `AI tum videodan ${numClips} viral klip secer ve uretir.`
                              : 'WhisperX transkripsiyon, smart crop, altyazi, format donusumu ve render short pipeline ile ayni akista calisir.'}
                    </p>
                </div>

                <button
                    onClick={() => void handleRender()}
                    disabled={busy || processing || !selectedFile || duration === 0}
                    className="btn-primary w-full tracking-[0.25em] font-black flex items-center justify-center gap-3 disabled:opacity-40"
                >
                    {busy ? (
                        <>
                            <Clock className="w-4 h-4" />
                            Sırada / İşleniyor
                        </>
                    ) : processing ? (
                        <>
                            <Loader2 className="w-4 h-4 animate-spin" />
                            RENDER...
                        </>
                    ) : (
                        <>
                            <ChevronRight className="w-5 h-5" />
                            {markers.length > 0
                                ? `KESIM NOKTALARI ILE ${markers.length + 1} KLIP URET`
                                : numClips > 1
                                  ? `AI ILE ${numClips} KLIP URET`
                                  : 'OTOMATIK CUT URET'}
                        </>
                    )}
                </button>
            </div>
        </div>
    );
};
