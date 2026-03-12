/**
 * Editor.tsx
 * ===========
 * Manuel klip editörü. (v2.1 - Visual Feedback & Manual Crop)
 *
 * Doğru akış:
 *  1. Video yükle → önizleme hemen görünür
 *  2. Transkripsiyon arka planda başlar (WebSocket ile takip)
 *  3. Kırpma zamanını ayarla (RangeSlider + Önizleme)
 *  4. Altyazı stilini seç & Kadrajı belirle (Sürükle-Bırak)
 *  5. Render Manual Clip → klibi oluştur
 */
import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import {
    Scissors, Save, AlertCircle,
    Clock, Sparkles, Film, ChevronRight,
} from 'lucide-react';
import { editorApi, clipsApi } from '../api/client';
import { API_BASE, MAX_UPLOAD_BYTES } from '../config';
import { getClipUrl } from '../utils/url';
import type { Clip, Segment } from '../types';
import { useJobStore } from '../store/useJobStore';
import { useThrottledCallback } from '../hooks/useThrottle';
import { useDebouncedEffect } from '../hooks/useDebouncedEffect';
import { STYLE_OPTIONS, isStyleName } from '../config/subtitleStyles';
import type { StyleName } from '../config/subtitleStyles';
import { RangeSlider } from './RangeSlider';
import { VideoOverlay } from './VideoOverlay';
import { VideoControls } from './ui/VideoControls';
import { toTimeStr } from '../utils/time';
import { normalizeTranscript } from '../utils/transcript';
import { readStored } from '../utils/storage';

const MASTER_EDITOR_SESSION_KEY = 'godtier-editor-master-session';

const formatUploadLimit = (bytes: number): string => {
    const gb = bytes / (1024 * 1024 * 1024);
    if (Number.isInteger(gb)) return `${gb}GB`;
    return `${gb.toFixed(1)}GB`;
};

const getErrorMessage = (error: unknown, fallback: string): string => {
    return error instanceof Error ? error.message : fallback;
};

interface StoredEditorSession {
    projectId?: string;
    transcript?: Segment[];
    startTime?: number;
    endTime?: number;
    style?: StyleName;
    numClips?: number;
    centerX?: number;
    currentJobId?: string | null;
}

function buildEditorSessionKey(mode: 'master' | 'clip', targetClip?: Clip): string {
    if (mode === 'clip' && targetClip) {
        return `godtier-editor-clip-session:${targetClip.project ?? 'legacy'}:${targetClip.name}`;
    }
    return MASTER_EDITOR_SESSION_KEY;
}

function readStoredEditorSession(sessionKey: string): StoredEditorSession | null {
    return readStored<StoredEditorSession | null>(sessionKey, null);
}

interface EditorProps {
    mode?: 'master' | 'clip';
    targetClip?: Clip;
    onClose?: () => void;
}

export const Editor: React.FC<EditorProps> = ({ mode = 'master', targetClip }) => {
    const { jobs } = useJobStore();
    const clipProjectId = targetClip?.project && targetClip.project !== 'legacy'
        ? targetClip.project
        : undefined;
    const sessionKey = buildEditorSessionKey(mode, targetClip);

    // ── Durum ─────────────────────────────────────────────────────────────
    const [localSrc, setLocalSrc] = useState<string | null>(null);   
    const [uploading, setUploading] = useState(false);
    const [transcribing, setTranscribing] = useState(false);
    const [transcript, setTranscript] = useState<Segment[]>([]);
    const [saving, setSaving] = useState(false);
    const [processing, setProcessing] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const [startTime, setStartTime] = useState(0);
    const [endTime, setEndTime] = useState(60);
    const [duration, setDuration] = useState(0);
    const [currentTime, setCurrentTime] = useState(0);
    const [isPlaying, setIsPlaying] = useState(false);
    const [style, setStyle] = useState<StyleName>('HORMOZI');
    const [numClips, setNumClips] = useState(3);
    const [centerX, setCenterX] = useState(0.5); // 0-1 range

    const videoRef = useRef<HTMLVideoElement>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [projectId, setProjectId] = useState<string | undefined>(clipProjectId);
    const [currentJobId, setCurrentJobId] = useState<string | null>(null);
    const [sessionReady, setSessionReady] = useState(false);
    const localBlobUrlRef = useRef<string | null>(null);

    const setLocalSrcWithCleanup = useCallback((nextSrc: string | null) => {
        setLocalSrc(prevSrc => {
            if (prevSrc && prevSrc !== nextSrc && prevSrc.startsWith('blob:')) {
                URL.revokeObjectURL(prevSrc);
            }
            return nextSrc;
        });

        localBlobUrlRef.current = nextSrc && nextSrc.startsWith('blob:') ? nextSrc : null;
    }, []);

    useEffect(() => () => {
        if (localBlobUrlRef.current) {
            URL.revokeObjectURL(localBlobUrlRef.current);
            localBlobUrlRef.current = null;
        }
    }, []);

    useEffect(() => {
        setSessionReady(false);
        setError(null);
        setLocalSrcWithCleanup(null);

        const stored = readStoredEditorSession(sessionKey);

        if (mode === 'clip' && targetClip) {
            setProjectId(stored?.projectId ?? clipProjectId);
            setTranscript(Array.isArray(stored?.transcript) ? stored.transcript : []);
            setStartTime(typeof stored?.startTime === 'number' ? stored.startTime : 0);
            setEndTime(typeof stored?.endTime === 'number' ? stored.endTime : 60);
            setStyle(isStyleName(stored?.style) ? stored.style : 'HORMOZI');
            setNumClips(typeof stored?.numClips === 'number' ? stored.numClips : 3);
            setCenterX(typeof stored?.centerX === 'number' ? stored.centerX : 0.5);
            setCurrentJobId(typeof stored?.currentJobId === 'string' ? stored.currentJobId : null);
        } else {
            setProjectId(undefined);
            setTranscript([]);
            setStartTime(0);
            setEndTime(60);
            setStyle('HORMOZI');
            setNumClips(3);
            setCenterX(0.5);
            setCurrentJobId(null);

            if (typeof window !== 'undefined') {
                window.localStorage.removeItem(sessionKey);
            }
        }

        setSessionReady(true);
    }, [clipProjectId, mode, sessionKey, setLocalSrcWithCleanup, targetClip]);

    useDebouncedEffect(() => {
        if (!sessionReady || typeof window === 'undefined') {
            return;
        }

        const payload: StoredEditorSession = {
            projectId,
            transcript,
            startTime,
            endTime,
            style,
            numClips,
            centerX,
            currentJobId,
        };

        window.localStorage.setItem(sessionKey, JSON.stringify(payload));
    }, [
        centerX,
        currentJobId,
        endTime,
        numClips,
        projectId,
        sessionKey,
        sessionReady,
        startTime,
        style,
        transcript,
    ], 500);

    // ── Transkript Fetch (useEffect içinde tanımlanır - closure sorununu önlemek için) ──
    useEffect(() => {
        if (!sessionReady || !projectId || transcript.length > 0) return;
        
        const loadTranscript = async () => {
            try {
                const d = await editorApi.getTranscript(projectId);
                setTranscript(normalizeTranscript(d));
            } catch (err) {
                console.error('Transkript yüklenirken hata:', err);
            }
        };
        
        loadTranscript();
    }, [projectId, sessionReady, transcript.length]);

    // ── WebSocket İlerleme Takibi ──────────────────────────────────────────
    useEffect(() => {
        if (!sessionReady) return;
        if (!currentJobId) return;
        const job = jobs.find(j => j.job_id === currentJobId);
        if (job) {
            if (job.status === 'completed') {
                setProcessing(false);
                setTranscribing(false);
                if (currentJobId.startsWith('upload') && projectId) {
                    // ProjectId ile transcript'i yeniden yükle
                    editorApi.getTranscript(projectId)
                        .then(d => setTranscript(normalizeTranscript(d)))
                        .catch(err => console.error('Transkript yüklenirken hata:', err));
                }
                setCurrentJobId(null);
            } else if (job.status === 'error' || job.status === 'cancelled') {
                setProcessing(false);
                setTranscribing(false);
                setError(job.last_message || 'İşlem başarısız.');
                setCurrentJobId(null);
            }
        }
    }, [jobs, currentJobId, projectId, sessionReady]);

    // ── İlk Yükleme ────────────────────────────────────────────────────────────
    useEffect(() => {
        if (!sessionReady) return;

        if (mode === 'clip' && targetClip && transcript.length === 0) {
            clipsApi.getTranscript(targetClip.name, clipProjectId)
                .then(d => setTranscript(normalizeTranscript(d)))
                .catch(err => setError(err.message));
        }
    }, [mode, targetClip, clipProjectId, sessionReady, transcript.length]);

    const videoSrc = localSrc
        ? localSrc
        : mode === 'clip' && targetClip
            ? getClipUrl(targetClip)
            : projectId
                ? `${API_BASE}/api/projects/${projectId}/master`
                : undefined;

    const togglePlay = useCallback(() => {
        if (!videoRef.current) return;
        if (videoRef.current.paused) { videoRef.current.play(); }
        else { videoRef.current.pause(); }
    }, []);

    const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;
        if (file.size > MAX_UPLOAD_BYTES) {
            setError(`Dosya boyutu çok büyük. Maksimum: ${formatUploadLimit(MAX_UPLOAD_BYTES)}`);
            return;
        }

        const blobUrl = URL.createObjectURL(file);
        setLocalSrcWithCleanup(blobUrl);
        setError(null);
        setUploading(true);

        try {
            const resp = await clipsApi.upload(file);
            if (resp.project_id) setProjectId(resp.project_id);
            
            if (resp.status === 'cached') {
                const data = await editorApi.getTranscript(resp.project_id);
                const t = Array.isArray(data.transcript) ? data.transcript : (data.transcript as { transcript?: Segment[] })?.transcript;
                setTranscript(t ?? []);
            } else {
                setTranscribing(true);
                setCurrentJobId(resp.job_id);
            }
        } catch (err: unknown) {
            setError(`Yükleme başarısız: ${getErrorMessage(err, 'Bilinmeyen hata')}`);
        } finally {
            setUploading(false);
            e.target.value = '';
        }
    };

    const handleSaveTranscript = async () => {
        setSaving(true);
        setError(null);
        try {
            if (mode === 'clip' && targetClip) {
                const resp = await editorApi.reburn({
                    clip_name: targetClip.name,
                    project_id: clipProjectId,
                    transcript,
                    style_name: style,
                });
                setProcessing(true);
                setCurrentJobId(resp.job_id);
            } else {
                await editorApi.saveTranscript(transcript, projectId);
            }
        }
        catch (err: unknown) { setError(getErrorMessage(err, 'Kaydetme başarısız.')); }
        finally { setSaving(false); }
    };

    const handleProcessBatch = async () => {
        if (endTime <= startTime) { setError('Bitiş zamanı başlangıçtan büyük olmalı.'); return; }
        setProcessing(true);
        setError(null);
        try {
            const resp = await editorApi.processBatch({
                project_id: projectId,
                start_time: startTime,
                end_time: endTime,
                num_clips: numClips,
                style_name: style,
            });
            setCurrentJobId(resp.job_id);
        } catch (err: unknown) {
            setError(getErrorMessage(err, 'Toplu iş başarısız.'));
            setProcessing(false);
        }
    };

    const handleProcessManual = async () => {
        if (endTime <= startTime) { setError('Bitiş zamanı başlangıçtan büyük olmalı.'); return; }
        setProcessing(true);
        setError(null);
        try {
            const resp = await editorApi.processManual({
                project_id: projectId,
                start_time: startTime,
                end_time: endTime,
                transcript: transcript.filter(s => s.start >= startTime && s.end <= endTime),
                style_name: style,
                center_x: centerX,
            });
            setCurrentJobId(resp.job_id);
        } catch (err: unknown) {
            setError(getErrorMessage(err, 'Manuel iş başarısız.'));
            setProcessing(false);
        }
    };

    const updateSubtitleText = (idx: number, text: string) => {
        const t = [...transcript];
        t[idx] = { ...t[idx], text };
        setTranscript(t);
    };

    const visibleTranscript = useMemo(
        () => transcript.filter(s => s.start >= startTime && s.end <= endTime),
        [transcript, startTime, endTime],
    );

    const handleTimeUpdateCore = useCallback((time: number) => {
        setCurrentTime(time);

        const subIdx = transcript.findIndex(s => time >= s.start && time <= s.end);
        if (subIdx !== -1) {
            const el = document.getElementById(`sub-${subIdx}`);
            if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }, [transcript]);

    const throttledTimeUpdate = useThrottledCallback(handleTimeUpdateCore, 100);

    const handleTimeUpdate = useCallback(() => {
        if (!videoRef.current) return;
        throttledTimeUpdate(videoRef.current.currentTime);
    }, [throttledTimeUpdate]);

    return (
        <div className="space-y-6 animate-in fade-in duration-500">
            {/* 1. Adım: Video Yükle */}
            <div className="glass-card p-5 border-accent/20">
                <div className="flex items-center justify-between gap-4">
                    <div className="space-y-1">
                        <div className="flex items-center gap-2">
                            <Film className="w-4 h-4 text-accent" />
                            <h3 className="text-xs font-mono uppercase tracking-[0.2em] text-accent">
                                {uploading ? 'Yükleniyor...' : transcribing ? 'Transkripsiyon çalışıyor...' : 'Video Yükle'}
                            </h3>
                        </div>
                        <p className="text-[11px] text-muted-foreground uppercase">
                            {transcribing ? 'WhisperX analiz ediyor, lütfen bekle...' : 'Kırmak istediğin videoyu seç'}
                        </p>
                        <p className="text-[10px] text-muted-foreground">
                            Maksimum dosya boyutu: {formatUploadLimit(MAX_UPLOAD_BYTES)}
                        </p>
                    </div>
                    <div className="flex items-center gap-2">
                        {transcribing && (
                            <div className="w-3 h-3 border-2 border-accent border-t-transparent animate-spin rounded-full" />
                        )}
                        <input type="file" ref={fileInputRef} onChange={handleFileUpload}
                            className="hidden" accept="video/*" />
                        <button
                            onClick={() => fileInputRef.current?.click()}
                            disabled={uploading || transcribing}
                            className="btn-primary py-2 px-5 text-[11px] tracking-[0.2em] flex items-center gap-2 disabled:opacity-50"
                        >
                            {uploading ? 'UPLOADING...' : 'VIDEO SEÇ'}
                        </button>
                    </div>
                </div>
            </div>

            {/* 2. Adım: Video Önizleme & Kadraj */}
            <div className="glass-card overflow-hidden border-primary/20 shadow-lg shadow-primary/5 ring-1 ring-primary/10">
                <div className="aspect-video bg-black/60 relative group">
                    <video
                        ref={videoRef}
                        src={videoSrc}
                        className="w-full h-full object-contain"
                        onLoadedMetadata={e => {
                            const dur = e.currentTarget.duration;
                            setDuration(dur);
                            setEndTime(Math.min(60, dur));
                        }}
                        onTimeUpdate={handleTimeUpdate}
                        onPlay={() => setIsPlaying(true)}
                        onPause={() => setIsPlaying(false)}
                        controls={false}
                    />
                    
                    {/* Visual Overlay Hub */}
                    <VideoOverlay 
                        currentTime={currentTime}
                        transcript={transcript}
                        style={style}
                        centerX={centerX}
                        onCropChange={setCenterX}
                    />

                    <VideoControls isPlaying={isPlaying} onTogglePlay={togglePlay} />
                </div>

                {/* 3. Adım: Kırpma Zamanı (Modern RangeSlider) */}
                <div className="p-5 bg-black/30 space-y-6">
                    <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-muted-foreground">
                        <Clock className="w-3 h-3" />
                        <span>Kırpma Aralığı</span>
                        <span className="ml-auto text-primary font-semibold">
                            {toTimeStr(startTime)} — {toTimeStr(endTime)} 
                            <span className="text-muted-foreground ml-1">({(endTime - startTime).toFixed(1)}s)</span>
                        </span>
                    </div>

                    <RangeSlider 
                        min={0} max={duration || 100}
                        start={startTime} end={endTime}
                        onChange={(s, e) => { setStartTime(s); setEndTime(e); }}
                    />

                    <div className="flex gap-2">
                        <button
                            onClick={() => { if (videoRef.current) { videoRef.current.currentTime = startTime; } }}
                            className="flex-1 py-1.5 text-[11px] font-mono uppercase tracking-widest bg-primary/10 border border-primary/20 rounded hover:bg-primary/20 transition-colors text-primary"
                        >
                            ▶ Baştan izle
                        </button>
                        <button
                            onClick={() => { if (videoRef.current) { videoRef.current.currentTime = endTime - 3; } }}
                            className="flex-1 py-1.5 text-[11px] font-mono uppercase tracking-widest bg-accent/10 border border-accent/20 rounded hover:bg-accent/20 transition-colors text-accent"
                        >
                            ▶ Sonu izle
                        </button>
                    </div>
                </div>
            </div>

            {/* 4. Adım: Transkript Editörü */}
            {(transcript.length > 0 || transcribing) && (
                <div className="glass-card p-5 space-y-4">
                    <div className="flex items-center justify-between">
                        <h3 className="text-sm font-bold uppercase tracking-[0.2em] flex items-center gap-2">
                            <Scissors className="w-4 h-4 text-primary" />
                            {transcribing ? 'Transkripsiyon bekleniyor...' : 'Altyazı Düzenleme'}
                        </h3>
                        {!transcribing && (
                            <button
                                onClick={handleSaveTranscript}
                                disabled={saving}
                                className="px-4 py-2 rounded-lg bg-white/5 border border-white/10 hover:bg-white/10 text-[11px] font-mono uppercase transition-all flex items-center gap-2"
                            >
                                {saving ? <div className="w-3 h-3 border-2 border-primary border-t-transparent animate-spin rounded-full" /> : <Save className="w-3 h-3" />}
                                {mode === 'clip' ? 'Kaydet + Reburn' : 'Kaydet'}
                            </button>
                        )}
                    </div>

                    <div className="max-h-[300px] overflow-y-auto space-y-2 pr-2 custom-scrollbar">
                        {visibleTranscript.map((sub, idx) => {
                                const realIdx = transcript.indexOf(sub);
                                const isActive = currentTime >= sub.start && currentTime <= sub.end;
                                return (
                                    <div key={idx} id={`sub-${realIdx}`} className={`flex gap-3 group transition-all duration-300 ${isActive ? 'scale-[1.02] z-10' : 'opacity-40'}`}>
                                        <div className={`text-[11px] font-mono w-14 pt-3 shrink-0 ${isActive ? 'text-primary font-black' : 'text-muted-foreground'}`}>
                                            {toTimeStr(sub.start)}
                                        </div>
                                        <textarea
                                            value={sub.text}
                                            onChange={e => updateSubtitleText(realIdx, e.target.value)}
                                            className={`flex-1 bg-white/5 border rounded-lg p-2.5 text-sm transition-all outline-none resize-none h-12 ${isActive ? 'border-primary/50 bg-white/10 shadow-lg shadow-primary/5' : 'border-white/5 group-hover:border-white/10'}`}
                                        />
                                    </div>
                                );
                            })}
                    </div>
                </div>
            )}

            {/* 5. Adım: Stil Seç + Render */}
            <div className="glass-card p-5 space-y-4 border-secondary/20">
                <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-[0.2em] text-secondary">
                    <Sparkles className="w-4 h-4" /> Altyazı Stili & Render
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-2" role="radiogroup" aria-label="Altyazi stili">
                    {STYLE_OPTIONS.map(s => (
                        <button key={s} onClick={() => setStyle(s)}
                            role="radio"
                            aria-checked={style === s}
                            className={`py-2.5 rounded-lg text-[11px] font-mono uppercase border transition-all ${style === s ? 'bg-secondary/20 border-secondary/60 text-secondary' : 'bg-white/5 border-white/10 text-muted-foreground hover:border-white/20'}`}>
                            {s}
                        </button>
                    ))}
                </div>

                {error && (
                    <div role="alert" className="flex items-center gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-xs font-mono text-red-400">
                        <AlertCircle className="w-4 h-4 shrink-0" aria-hidden="true" /> {error}
                    </div>
                )}

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="p-3 rounded-xl bg-primary/5 border border-primary/10 space-y-3">
                        <span className="text-[11px] font-mono text-primary uppercase tracking-widest block">AI Batch Üretimi</span>
                        <div className="flex items-center gap-2">
                            <input type="number" min={1} max={10} value={numClips} onChange={e => setNumClips(Number(e.target.value))}
                                className="w-full bg-black/40 border border-white/10 rounded px-2 py-2 text-xs font-mono text-center" />
                        </div>
                        <button onClick={handleProcessBatch} disabled={processing || transcribing || duration === 0}
                            className="w-full py-2.5 rounded-lg bg-primary/10 border border-primary/30 hover:bg-primary/20 text-primary text-[11px] font-mono uppercase transition-all disabled:opacity-30">
                            AI ILE TOPLU ÜRET
                        </button>
                    </div>

                    <button
                        onClick={handleProcessManual}
                        disabled={processing || transcribing || duration === 0}
                        className="btn-primary w-full tracking-[0.25em] font-black flex items-center justify-center gap-3 disabled:opacity-40 relative group overflow-hidden"
                    >
                        {processing ? (
                            <><div className="w-4 h-4 border-2 border-background border-t-transparent animate-spin rounded-full" /> RENDER...</>
                        ) : (
                            <><ChevronRight className="w-5 h-5" /> SEÇİMİ RENDER ET</>
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
};
