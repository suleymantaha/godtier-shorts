/**
 * SubtitleEditor.tsx
 * Altyazı düzenleme sayfası. Proje veya klip transcript'ini düzenler.
 */
import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { Film, Save, Subtitles, AlertCircle, CheckCircle2, Clock, Scissors } from 'lucide-react';
import { editorApi, clipsApi } from '../api/client';
import { API_BASE } from '../config';
import { getClipUrl } from '../utils/url';
import { useJobStore } from '../store/useJobStore';
import { STYLE_OPTIONS, isStyleName } from '../config/subtitleStyles';
import type { StyleName } from '../config/subtitleStyles';
import type { Clip, Segment } from '../types';
import { VideoControls } from './ui/VideoControls';
import { RangeSlider } from './RangeSlider';
import { toTimeStr } from '../utils/time';
import { normalizeTranscript } from '../utils/transcript';

export const SubtitleEditor: React.FC = () => {
    const { jobs, fetchJobs } = useJobStore();
    const [mode, setMode] = useState<'project' | 'clip'>('project');
    const [projects, setProjects] = useState<{ id: string; has_master: boolean; has_transcript: boolean }[]>([]);
    const [clips, setClips] = useState<Clip[]>([]);
    const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
    const [selectedClip, setSelectedClip] = useState<Clip | null>(null);
    const [transcript, setTranscript] = useState<Segment[]>([]);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [successMessage, setSuccessMessage] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [style, setStyle] = useState<StyleName>('HORMOZI');
    const [currentTime, setCurrentTime] = useState(0);
    const [isPlaying, setIsPlaying] = useState(false);
    const [currentJobId, setCurrentJobId] = useState<string | null>(null);
    const [cacheBust, setCacheBust] = useState(0);
    const [startTime, setStartTime] = useState(0);
    const [endTime, setEndTime] = useState(60);
    const [duration, setDuration] = useState(0);
    const videoRef = useRef<HTMLVideoElement>(null);

    const currentJob = currentJobId ? jobs.find((j) => j.job_id === currentJobId) ?? null : null;

    const [projectsError, setProjectsError] = useState<string | null>(null);

    useEffect(() => {
        editorApi.getProjects().then((d) => {
            setProjects(d.projects.filter((p) => p.has_master && p.has_transcript));
            setProjectsError(d.error ?? null);
        });
        clipsApi.list()
            .then((d) => setClips(d.clips))
            .catch(() => setClips([]));
    }, []);

    const videoSrc = mode === 'project' && selectedProjectId
        ? `${API_BASE}/api/projects/${selectedProjectId}/master`
        : mode === 'clip' && selectedClip
            ? `${getClipUrl(selectedClip)}${cacheBust ? `?t=${cacheBust}` : ''}`
            : undefined;

    const loadTranscript = useCallback(async () => {
        setError(null);
        setLoading(true);
        try {
            if (mode === 'project' && selectedProjectId) {
                const d = await editorApi.getTranscript(selectedProjectId);
                setTranscript(normalizeTranscript(d));
            } else if (mode === 'clip' && selectedClip) {
                const d = await clipsApi.getTranscript(selectedClip.name, selectedClip.project);
                setTranscript(normalizeTranscript(d));
            } else {
                setTranscript([]);
            }
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Transkript yüklenemedi.');
            setTranscript([]);
        } finally {
            setLoading(false);
        }
    }, [mode, selectedProjectId, selectedClip]);

    useEffect(() => {
        if ((mode === 'project' && selectedProjectId) || (mode === 'clip' && selectedClip)) {
            loadTranscript();
            setStartTime(0);
            setEndTime(60);
            setDuration(0);
        } else {
            setTranscript([]);
        }
    }, [mode, selectedProjectId, selectedClip, loadTranscript]);

    useEffect(() => {
        if (currentJob?.status === 'completed') {
            setSaving(false);
            setCurrentJobId(null);
            setSuccessMessage(mode === 'clip' ? 'Video render edildi. Altyazılar güncellendi.' : 'Klip üretildi.');
            setError(null);
            setCacheBust((b) => b + 1);
            if (mode === 'clip' && selectedClip) loadTranscript();
            if (mode === 'project') void fetchJobs();
        } else if (currentJob?.status === 'error' || currentJob?.status === 'cancelled') {
            setSaving(false);
            setError(currentJob.error ?? currentJob.last_message ?? 'İşlem başarısız.');
            setCurrentJobId(null);
        }
    }, [currentJob, fetchJobs, mode, selectedClip, loadTranscript]);

    useEffect(() => {
        if (!successMessage) return;
        const t = setTimeout(() => setSuccessMessage(null), 5000);
        return () => clearTimeout(t);
    }, [successMessage]);

    const updateSubtitleText = (idx: number, text: string) => {
        const t = [...transcript];
        t[idx] = { ...t[idx], text };
        setTranscript(t);
    };

    const handleSave = async () => {
        setError(null);
        setSuccessMessage(null);
        setSaving(true);
        try {
            if (mode === 'project' && selectedProjectId) {
                await editorApi.saveTranscript(transcript, selectedProjectId);
                setSuccessMessage('Transcript kaydedildi.');
                setTimeout(() => setSuccessMessage(null), 5000);
            } else if (mode === 'clip' && selectedClip) {
                const resp = await editorApi.reburn({
                    clip_name: selectedClip.name,
                    project_id: selectedClip.project ?? undefined,
                    transcript,
                    style_name: style,
                });
                setCurrentJobId(resp.job_id);
                return;
            }
            setSaving(false);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Kaydetme başarısız.');
            setSaving(false);
        }
    };

    const handleRenderClip = async () => {
        if (!selectedProjectId || endTime <= startTime) return;
        setError(null);
        setSuccessMessage(null);
        setSaving(true);
        try {
            const resp = await editorApi.processManual({
                project_id: selectedProjectId,
                start_time: startTime,
                end_time: endTime,
                transcript,
                style_name: style,
            });
            setCurrentJobId(resp.job_id);
            await fetchJobs();
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Klip üretilemedi.');
            setSaving(false);
        }
    };

    const handleTimeUpdate = useCallback(() => {
        if (videoRef.current) setCurrentTime(videoRef.current.currentTime);
    }, []);

    const togglePlay = useCallback(() => {
        if (!videoRef.current) return;
        if (videoRef.current.paused) videoRef.current.play();
        else videoRef.current.pause();
    }, []);

    const hasSelection = (mode === 'project' && selectedProjectId) || (mode === 'clip' && selectedClip);

    const visibleTranscript = useMemo(
        () => transcript.filter((s) => s.end > startTime && s.start < endTime),
        [transcript, startTime, endTime],
    );

    useEffect(() => {
        if (transcript.length > 0 && duration === 0) {
            const maxEnd = Math.max(...transcript.map((s) => s.end), 60);
            setDuration(maxEnd);
            setEndTime(Math.min(60, maxEnd));
        }
    }, [transcript, duration]);

    return (
        <div className="space-y-6 animate-in fade-in duration-500">
            <div className="glass-card p-5 border-accent/20">
                <h2 className="text-xs font-mono uppercase tracking-[0.2em] text-accent flex items-center gap-2 mb-4">
                    <Subtitles className="w-4 h-4" />
                    Altyazı Düzenleme
                </h2>
                <div className="flex flex-col sm:flex-row gap-4">
                    <div className="flex-1 space-y-2">
                        <label className="text-[11px] text-muted-foreground uppercase block">Mod</label>
                        <div className="flex gap-2">
                            <button
                                type="button"
                                onClick={() => { setMode('project'); setSelectedClip(null); setSelectedProjectId(null); }}
                                className={`px-4 py-2 rounded-lg text-[11px] font-mono uppercase border transition-all ${mode === 'project' ? 'bg-accent/20 border-accent/40 text-white' : 'bg-white/5 border-white/10 text-muted-foreground'}`}
                            >
                                Proje
                            </button>
                            <button
                                type="button"
                                onClick={() => { setMode('clip'); setSelectedProjectId(null); setSelectedClip(null); }}
                                className={`px-4 py-2 rounded-lg text-[11px] font-mono uppercase border transition-all ${mode === 'clip' ? 'bg-accent/20 border-accent/40 text-white' : 'bg-white/5 border-white/10 text-muted-foreground'}`}
                            >
                                Klip
                            </button>
                        </div>
                    </div>
                    <div className="flex-1 space-y-2">
                        <label className="text-[11px] text-muted-foreground uppercase block">
                            {mode === 'project' ? 'Proje' : 'Klip'}
                        </label>
                        {mode === 'project' ? (
                            <select
                                value={selectedProjectId ?? ''}
                                onChange={(e) => setSelectedProjectId(e.target.value || null)}
                                className="input-field w-full text-xs"
                            >
                                <option value="">Proje seçin</option>
                                {projects.map((p) => (
                                    <option key={p.id} value={p.id}>{p.id}</option>
                                ))}
                            </select>
                        ) : (
                            <select
                                value={selectedClip ? `${selectedClip.project ?? 'legacy'}:${selectedClip.name}` : ''}
                                onChange={(e) => {
                                    const v = e.target.value;
                                    if (!v) { setSelectedClip(null); return; }
                                    const [proj, name] = v.split(':');
                                    const c = clips.find((cl) => (cl.project ?? 'legacy') === proj && cl.name === name);
                                    setSelectedClip(c ?? null);
                                }}
                                className="input-field w-full text-xs"
                            >
                                <option value="">Klip seçin</option>
                                {clips.map((c) => (
                                    <option key={`${c.project ?? 'legacy'}:${c.name}`} value={`${c.project ?? 'legacy'}:${c.name}`}>
                                        {c.name}
                                    </option>
                                ))}
                            </select>
                        )}
                    </div>
                </div>
                {projectsError && mode === 'project' && (
                    <p className="text-[11px] text-red-400/90 mt-2 flex items-center gap-1.5">
                        <AlertCircle className="w-3 h-3 shrink-0" />
                        {projectsError}
                    </p>
                )}
                {projects.length === 0 && mode === 'project' && !projectsError && (
                    <p className="text-[11px] text-muted-foreground mt-2">Henüz proje yok. Video yükleyerek başlayın.</p>
                )}
                {clips.length === 0 && mode === 'clip' && (
                    <p className="text-[11px] text-muted-foreground mt-2">Henüz klip yok.</p>
                )}
            </div>

            {hasSelection && (
                <>
                    <div className="glass-card overflow-hidden border-primary/20">
                        <div className="aspect-video bg-black/60 relative group">
                            {videoSrc && (
                                <>
                                    <video
                                        ref={videoRef}
                                        src={videoSrc}
                                        className="w-full h-full object-contain"
                                        onLoadedMetadata={(e) => {
                                            const d = e.currentTarget.duration;
                                            setDuration(d);
                                            setEndTime((prev) => (prev > d || prev === 60 ? Math.min(60, d) : prev));
                                        }}
                                        onTimeUpdate={handleTimeUpdate}
                                        onPlay={() => setIsPlaying(true)}
                                        onPause={() => setIsPlaying(false)}
                                        controls={false}
                                    />
                                    <VideoControls isPlaying={isPlaying} onTogglePlay={togglePlay} />
                                </>
                            )}
                        </div>
                    </div>

                    {!loading && transcript.length > 0 && (
                        <div className="glass-card p-5 space-y-4 border-primary/20">
                            <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-muted-foreground">
                                <Clock className="w-3 h-3" />
                                <span>Düzenlenecek aralık</span>
                                <span className="ml-auto text-primary font-semibold">
                                    {toTimeStr(startTime)} — {toTimeStr(endTime)}
                                    <span className="text-muted-foreground ml-1">
                                        ({visibleTranscript.length} segment)
                                    </span>
                                </span>
                            </div>
                            <RangeSlider
                                min={0}
                                max={duration || 100}
                                start={startTime}
                                end={endTime}
                                onChange={(s, e) => {
                                    setStartTime(s);
                                    setEndTime(e);
                                }}
                            />
                        </div>
                    )}

                    <div className="glass-card p-5 space-y-4">
                        <div className="flex items-center justify-between">
                            <h3 className="text-sm font-bold uppercase tracking-[0.2em] flex items-center gap-2">
                                <Film className="w-4 h-4 text-primary" />
                                {loading ? 'Yükleniyor...' : `Altyazı (${visibleTranscript.length} / ${transcript.length} segment)`}
                            </h3>
                            <select
                                value={style}
                                onChange={(e) => setStyle(isStyleName(e.target.value) ? e.target.value : 'HORMOZI')}
                                className="input-field w-32 text-xs"
                            >
                                {STYLE_OPTIONS.filter((s) => s !== 'CUSTOM').map((s) => (
                                    <option key={s} value={s}>{s}</option>
                                ))}
                            </select>
                            {!loading && (
                                <div className="flex gap-2">
                                    <button
                                        onClick={handleSave}
                                        disabled={saving || transcript.length === 0}
                                        className="px-4 py-2 rounded-lg bg-white/5 border border-white/10 hover:bg-white/10 text-[11px] font-mono uppercase transition-all flex items-center gap-2 disabled:opacity-50"
                                    >
                                        {saving ? <div className="w-3 h-3 border-2 border-primary border-t-transparent animate-spin rounded-full" /> : <Save className="w-3 h-3" />}
                                        {mode === 'clip' ? 'Kaydet + Reburn' : 'Kaydet'}
                                    </button>
                                    {mode === 'project' && selectedProjectId && (
                                        <button
                                            onClick={handleRenderClip}
                                            disabled={saving || transcript.length === 0 || endTime <= startTime}
                                            className="px-4 py-2 rounded-lg bg-primary/20 border border-primary/40 hover:bg-primary/30 text-[11px] font-mono uppercase transition-all flex items-center gap-2 disabled:opacity-50"
                                        >
                                            {saving ? <div className="w-3 h-3 border-2 border-primary border-t-transparent animate-spin rounded-full" /> : <Scissors className="w-3 h-3" />}
                                            Aralığı klip olarak üret
                                        </button>
                                    )}
                                </div>
                            )}
                        </div>
                        {error && (
                            <div className="flex items-center gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-xs text-red-400">
                                <AlertCircle className="w-4 h-4 shrink-0" /> {error}
                            </div>
                        )}
                        {successMessage && (
                            <div className="flex items-center gap-2 p-3 rounded-lg bg-green-500/10 border border-green-500/20 text-xs text-green-400">
                                <CheckCircle2 className="w-4 h-4 shrink-0" /> {successMessage}
                            </div>
                        )}
                        <div className="max-h-[300px] overflow-y-auto space-y-2 pr-2 custom-scrollbar">
                            {visibleTranscript.map((sub) => {
                                const realIdx = transcript.indexOf(sub);
                                const isActive = currentTime >= sub.start && currentTime <= sub.end;
                                return (
                                    <div
                                        key={realIdx}
                                        role="button"
                                        tabIndex={0}
                                        onClick={() => { if (videoRef.current) videoRef.current.currentTime = sub.start; }}
                                        onKeyDown={(e) => { if (e.key === 'Enter' && videoRef.current) videoRef.current.currentTime = sub.start; }}
                                        className={`flex gap-3 group transition-all duration-300 cursor-pointer ${isActive ? 'scale-[1.02] z-10' : 'opacity-40'}`}
                                    >
                                        <div className={`text-[11px] font-mono w-14 pt-3 shrink-0 ${isActive ? 'text-primary font-black' : 'text-muted-foreground'}`}>
                                            {toTimeStr(sub.start)}
                                        </div>
                                        <textarea
                                            value={sub.text}
                                            onChange={(e) => updateSubtitleText(realIdx, e.target.value)}
                                            onClick={(e) => e.stopPropagation()}
                                            className={`flex-1 bg-white/5 border rounded-lg p-2.5 text-sm transition-all outline-none resize-none h-12 ${isActive ? 'border-primary/50 bg-white/10' : 'border-white/5 group-hover:border-white/10'}`}
                                        />
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                </>
            )}
        </div>
    );
};
