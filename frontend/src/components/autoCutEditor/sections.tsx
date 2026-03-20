import React from 'react';
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
  Waves,
  X,
} from 'lucide-react';

import {
  ANIMATION_SELECT_OPTIONS,
  resolvePreviewLayout,
  STYLE_OPTIONS,
  isStyleName,
  isSubtitleAnimationType,
  type RequestedSubtitleLayout,
  type StyleName,
  type SubtitleAnimationType,
} from '../../config/subtitleStyles';
import { toTimeStr } from '../../utils/time';
import { RangeSlider } from '../RangeSlider';
import { TimeRangeHeader } from '../TimeRangeHeader';
import { SubtitlePreview } from '../SubtitlePreview';
import { openMediaSource, useResolvedMediaSource } from '../ui/protectedMedia';
import { Select } from '../ui/Select';
import { VideoControls } from '../ui/VideoControls';
import type { AutoCutEditorController } from './useAutoCutEditorController';

interface AutoCutEditorLayoutProps {
  controller: AutoCutEditorController;
}

const LAYOUT_SELECT_OPTIONS = [
  { label: 'Auto', value: 'auto' },
  { label: 'Single', value: 'single' },
  { label: 'Split', value: 'split' },
];

export function AutoCutEditorLayout({ controller }: AutoCutEditorLayoutProps) {
  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <AutoCutFilePickerCard
        fileInputRef={controller.fileInputRef}
        onFileSelect={controller.handleFileSelect}
        onOpenFilePicker={controller.openFilePicker}
        processing={controller.processing}
        projectId={controller.projectId}
        selectedFile={controller.selectedFile}
      />
      <AutoCutPreviewCard controller={controller} />
      <AutoCutOptionsCard controller={controller} />
      <AutoCutJobStatusCard controller={controller} />
      <AutoCutResultCard
        currentJob={controller.currentJob}
        generatedClips={controller.generatedClips}
        handleOpenLibrary={controller.handleOpenLibrary}
        resultVideoSrc={controller.resultVideoSrc}
      />
      <AutoCutRenderCard controller={controller} />
    </div>
  );
}

function AutoCutFilePickerCard({
  fileInputRef,
  onFileSelect,
  onOpenFilePicker,
  processing,
  projectId,
  selectedFile,
}: {
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  onFileSelect: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onOpenFilePicker: () => void;
  processing: boolean;
  projectId?: string;
  selectedFile: File | null;
}) {
  return (
    <div className="glass-card p-5 border-accent/20">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Film className="w-4 h-4 text-accent" />
            <h3 className="text-xs font-mono uppercase tracking-[0.2em] text-accent">Otomatik Manual Cut</h3>
          </div>
          <p className="text-[11px] uppercase text-muted-foreground">
            Video sec, zaman araligini belirle, short pipeline geri kalanini otomatik tamamlasin.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <input ref={fileInputRef} type="file" accept="video/*" onChange={onFileSelect} className="hidden" />
          <button
            onClick={onOpenFilePicker}
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
          'Henuz video secilmedi.'
        )}
      </div>
    </div>
  );
}

function AutoCutPreviewCard({ controller }: AutoCutEditorLayoutProps) {
  return (
    <div className="glass-card overflow-hidden border-primary/20 shadow-lg shadow-primary/5 ring-1 ring-primary/10">
      <AutoCutVideoViewport
        handleVideoLoadedMetadata={controller.handleVideoLoadedMetadata}
        isPlaying={controller.isPlaying}
        onPause={() => controller.setIsPlaying(false)}
        onPlay={() => controller.setIsPlaying(true)}
        togglePlay={controller.togglePlay}
        videoRef={controller.videoRef}
        videoSrc={controller.videoSrc}
      />
      <div className="p-5 bg-foreground/5 space-y-6">
        <AutoCutRangeHeader endTime={controller.endTime} startTime={controller.startTime} />
        {controller.videoSrc ? (
          <>
            <RangeSlider
              min={0}
              max={controller.duration || 100}
              start={controller.startTime}
              end={controller.endTime}
              onChange={controller.updateRange}
            />
            <AutoCutPreviewActions
              addCurrentMarker={controller.addCurrentMarker}
              jumpToEnd={controller.jumpToEnd}
              jumpToStart={controller.jumpToStart}
            />
            <AutoCutMarkerFeedback
              feedback={controller.kesFeedback}
              markers={controller.markers}
              onRemoveMarker={controller.removeMarker}
            />
          </>
        ) : (
          <div className="rounded-xl border border-border bg-foreground/5 px-4 py-6 text-center text-xs text-muted-foreground">
            Zaman araligi secmek icin once video yukle.
          </div>
        )}
      </div>
    </div>
  );
}

function AutoCutVideoViewport({
  handleVideoLoadedMetadata,
  isPlaying,
  onPause,
  onPlay,
  togglePlay,
  videoRef,
  videoSrc,
}: {
  handleVideoLoadedMetadata: (event: React.SyntheticEvent<HTMLVideoElement>) => void;
  isPlaying: boolean;
  onPause: () => void;
  onPlay: () => void;
  togglePlay: () => void;
  videoRef: React.RefObject<HTMLVideoElement | null>;
  videoSrc?: string;
}) {
  const resolvedVideoSrc = useResolvedMediaSource(videoSrc);

  return (
    <div className="aspect-video bg-background/80 relative group">
      {videoSrc ? (
        <>
          <video
            ref={videoRef}
            src={resolvedVideoSrc}
            className="w-full h-full object-contain"
            onLoadedMetadata={handleVideoLoadedMetadata}
            onPlay={onPlay}
            onPause={onPause}
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
  );
}

function AutoCutRangeHeader({ endTime, startTime }: { endTime: number; startTime: number }) {
  return (
    <TimeRangeHeader endTime={endTime} startTime={startTime} title="Kesim Araligi" />
  );
}

function AutoCutPreviewActions({
  addCurrentMarker,
  jumpToEnd,
  jumpToStart,
}: {
  addCurrentMarker: () => void;
  jumpToEnd: () => void;
  jumpToStart: () => void;
}) {
  return (
    <div className="flex gap-2">
      <button
        onClick={jumpToStart}
        className="flex-1 py-1.5 text-[11px] font-mono uppercase tracking-widest bg-primary/10 border border-primary/20 rounded hover:bg-primary/20 transition-colors text-primary"
      >
        Basi izle
      </button>
      <button
        onClick={jumpToEnd}
        className="flex-1 py-1.5 text-[11px] font-mono uppercase tracking-widest bg-accent/10 border border-accent/20 rounded hover:bg-accent/20 transition-colors text-accent"
      >
        Sonu izle
      </button>
      <button
        onClick={addCurrentMarker}
        className="flex-1 py-1.5 text-[11px] font-mono uppercase tracking-widest bg-secondary/10 border border-secondary/20 rounded hover:bg-secondary/20 transition-colors text-secondary flex items-center justify-center gap-1.5"
        title="Mevcut zamana kesim noktasi ekle"
      >
        <Plus className="w-3 h-3" />
        Kes
      </button>
    </div>
  );
}

function AutoCutMarkerFeedback({
  feedback,
  markers,
  onRemoveMarker,
}: {
  feedback: string | null;
  markers: number[];
  onRemoveMarker: (index: number) => void;
}) {
  return (
    <>
      {feedback && <p className="text-[11px] font-mono text-secondary/90 animate-in fade-in">{feedback}</p>}
      {markers.length > 0 && (
        <div className="space-y-2">
          <span className="text-[11px] text-muted-foreground uppercase">Kesim noktalari ({markers.length + 1} klip)</span>
          <div className="flex flex-wrap gap-2">
            {markers.map((marker, index) => (
              <span
                key={`${marker}-${index}`}
                className="inline-flex items-center gap-1.5 rounded-lg bg-foreground/10 px-2 py-1 text-[11px] font-mono"
              >
                {toTimeStr(marker)}
                <button
                  type="button"
                  onClick={() => onRemoveMarker(index)}
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
  );
}

function AutoCutOptionsCard({ controller }: AutoCutEditorLayoutProps) {
  if (!controller.videoSrc) {
    return null;
  }

  return (
    <div className="glass-card p-5 space-y-4 border-secondary/20">
      <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-[0.2em] text-secondary">
        <Sparkles className="w-4 h-4" />
        Altyazi Stili & Uretim
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <AutoCutSubtitleOptions
          animationType={controller.animationType}
          cutAsShort={controller.cutAsShort}
          layout={controller.layout}
          setAnimationType={controller.setAnimationType}
          setCutAsShort={controller.setCutAsShort}
          setLayout={controller.setLayout}
          setSkipSubtitles={controller.setSkipSubtitles}
          setStyle={controller.setStyle}
          skipSubtitles={controller.skipSubtitles}
          style={controller.style}
        />
        <AutoCutClipCountCard
          markers={controller.markers}
          numClips={controller.numClips}
          onChangeClipCount={controller.updateSelectedClipCount}
        />
        <div className="rounded-xl border border-white/10 bg-foreground/5 p-3 h-full flex items-start justify-center">
          <SubtitlePreview
            animationType={controller.animationType}
            cutAsShort={controller.cutAsShort}
            disabled={controller.skipSubtitles}
            layout={resolvePreviewLayout(controller.layout)}
            styleName={controller.style}
            videoSrc={controller.videoSrc}
          />
        </div>
      </div>
    </div>
  );
}

function AutoCutSubtitleOptions({
  animationType,
  cutAsShort,
  layout,
  setAnimationType,
  setCutAsShort,
  setLayout,
  setSkipSubtitles,
  setStyle,
  skipSubtitles,
  style,
}: {
  animationType: SubtitleAnimationType;
  cutAsShort: boolean;
  layout: RequestedSubtitleLayout;
  setAnimationType: React.Dispatch<React.SetStateAction<SubtitleAnimationType>>;
  setCutAsShort: React.Dispatch<React.SetStateAction<boolean>>;
  setLayout: React.Dispatch<React.SetStateAction<RequestedSubtitleLayout>>;
  setSkipSubtitles: React.Dispatch<React.SetStateAction<boolean>>;
  setStyle: React.Dispatch<React.SetStateAction<StyleName>>;
  skipSubtitles: boolean;
  style: StyleName;
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-foreground/5 p-3 space-y-3 h-full">
      <div className="flex items-center justify-between gap-2">
        <label
          className="text-[11px] text-muted-foreground uppercase"
          title="Yatay videolari TikTok/Reels formatina donusturur. Kapaliyken sadece sure kesilir."
        >
          Short olarak kes (9:16)
        </label>
        <button
          type="button"
          role="switch"
          aria-checked={cutAsShort}
          aria-label="Short olarak kes"
          title="Yatay videolari dikey 9:16 formata donusturur. Kapaliyken orijinal boyut korunur."
          onClick={() => setCutAsShort((previous) => !previous)}
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
          onClick={() => setSkipSubtitles((previous) => !previous)}
          className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border-2 transition-colors ${skipSubtitles ? 'bg-red-500/30 border-red-500/50' : 'bg-primary/20 border-primary/40'}`}
        >
          <span
            className={`pointer-events-none inline-block h-4 w-4 rounded-full shadow-sm transition-transform ${skipSubtitles ? 'translate-x-5 bg-red-400' : 'translate-x-0.5 bg-primary'}`}
          />
        </button>
      </div>
      <Select
        value={style}
        onChange={(value) => setStyle(isStyleName(value) ? value : 'HORMOZI')}
        options={STYLE_OPTIONS.map((style) => ({ label: style, value: style }))}
        disabled={skipSubtitles}
        className={skipSubtitles ? 'opacity-40' : ''}
      />
      <div className="space-y-1">
        <label className="text-[11px] text-muted-foreground uppercase block">Layout</label>
        <Select
          value={layout}
          onChange={(value) => setLayout(value === 'split' ? 'split' : value === 'single' ? 'single' : 'auto')}
          options={LAYOUT_SELECT_OPTIONS}
          icon={<Sparkles className="w-4 h-4 text-secondary/50" />}
        />
      </div>
      <div className="space-y-1">
        <label className="text-[11px] text-muted-foreground uppercase block">Motion</label>
        <Select
          value={animationType}
          onChange={(value) => setAnimationType(isSubtitleAnimationType(value) ? value : 'default')}
          options={ANIMATION_SELECT_OPTIONS}
          disabled={skipSubtitles}
          className={skipSubtitles ? 'opacity-40' : ''}
          icon={<Waves className="w-4 h-4 text-secondary/50" />}
        />
      </div>
      {skipSubtitles && (
        <div className="flex items-center gap-1.5 text-[11px] font-mono text-red-400/80">
          <Subtitles className="w-3 h-3" />
          Altyazi devre disi
        </div>
      )}
    </div>
  );
}

function AutoCutClipCountCard({
  markers,
  numClips,
  onChangeClipCount,
}: {
  markers: number[];
  numClips: number;
  onChangeClipCount: (value: string) => void;
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-foreground/5 p-3 space-y-3 h-full">
      <label className="text-[11px] text-muted-foreground uppercase block">
        {markers.length > 0 ? 'Kesim noktalari' : 'Klip sayisi (AI)'}
      </label>
      {markers.length > 0 ? (
        <p className="text-xs font-mono text-primary">{markers.length + 1} klip (manuel kesim)</p>
      ) : (
        <>
          <input
            type="number"
            min={1}
            max={10}
            value={numClips}
            onChange={(event) => onChangeClipCount(event.target.value)}
            className="input-field w-full text-xs"
          />
          <p className="text-[10px] text-muted-foreground">
            {numClips === 1 ? 'Tek klip (secili aralik)' : `AI tum videodan ${numClips} viral klip uretir`}
          </p>
        </>
      )}
    </div>
  );
}

function AutoCutJobStatusCard({ controller }: AutoCutEditorLayoutProps) {
  if (!controller.currentJobId && !controller.currentJob && !controller.errorMessage) {
    return null;
  }

  return (
    <div className="glass-card p-5 space-y-4 border-secondary/20">
      <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-[0.2em] text-secondary">
        {controller.processing ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
        Is Durumu
      </div>
      <AutoCutJobProgress currentJob={controller.currentJob} currentJobId={controller.currentJobId} />
      {controller.queuePosition != null && controller.queuePosition > 1 && (
        <div className="rounded-md border border-border px-3 py-2 text-sm text-muted-foreground">
          GPU kuyrugunda sira: {controller.queuePosition}
        </div>
      )}
      {controller.generatedClips.length > 0 && (
        <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-3 py-3 text-xs text-emerald-100">
          Hazir klipler: {controller.generatedClips.length}
        </div>
      )}
      {controller.errorMessage && (
        <div className="flex items-center gap-2 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-3 text-xs text-red-300">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{controller.errorMessage}</span>
        </div>
      )}
    </div>
  );
}

function AutoCutJobProgress({
  currentJob,
  currentJobId,
}: Pick<AutoCutEditorController, 'currentJob' | 'currentJobId'>) {
  if (currentJob) {
    return (
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
    );
  }

  if (!currentJobId) {
    return null;
  }

  return <div className="text-xs font-mono text-muted-foreground">Job baglandi: {currentJobId}</div>;
}

function AutoCutResultCard({
  currentJob,
  generatedClips,
  handleOpenLibrary,
  resultVideoSrc,
}: Pick<AutoCutEditorController, 'currentJob' | 'generatedClips' | 'handleOpenLibrary' | 'resultVideoSrc'>) {
  const resolvedResultVideoSrc = useResolvedMediaSource(resultVideoSrc);
  const clipCount = Math.max(currentJob?.num_clips ?? 0, generatedClips.length, 1);

  if (!resultVideoSrc && generatedClips.length === 0) {
    return null;
  }

  return (
    <div className="glass-card p-5 space-y-4 border-green-500/20">
      <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-[0.2em] text-green-300">
        <CheckCircle2 className="w-4 h-4" />
        {clipCount > 1 ? `${clipCount} Klip Uretildi` : 'Uretilen Klip'}
      </div>
      {clipCount > 1 && (
        <p className="text-[11px] text-muted-foreground">Render tamamlandi. Tum klipler ClipGallery icinde indekslenir; ilk hazir klip asagida.</p>
      )}
      {generatedClips.length > 0 && (
        <div className="rounded-xl border border-border bg-foreground/5 px-4 py-3">
          <div className="mb-2 text-[11px] font-mono uppercase tracking-[0.2em] text-muted-foreground">Hazir Klipler</div>
          <div className="space-y-2">
            {generatedClips.map((clip) => (
              <div key={`${clip.job_id}:${clip.projectId ?? 'legacy'}:${clip.clipName}:${clip.at}`} className="flex items-center justify-between gap-3 text-xs">
                <div className="min-w-0">
                  <div className="truncate font-mono text-foreground/90">{clip.clipName}</div>
                  {clip.uiTitle && <div className="truncate text-muted-foreground">{clip.uiTitle}</div>}
                </div>
                {clip.projectId && (
                  <span className="shrink-0 rounded-full border border-primary/20 bg-primary/10 px-2 py-1 text-[10px] font-mono uppercase tracking-widest text-primary">
                    {clip.projectId}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
      {resultVideoSrc && <video src={resolvedResultVideoSrc} controls className="w-full rounded-xl bg-background/90" />}
      <div className="flex flex-wrap gap-3">
        {resultVideoSrc && (
          <button
            type="button"
            onClick={() => void openMediaSource(resolvedResultVideoSrc ?? resultVideoSrc)}
            className="inline-flex items-center gap-2 rounded-lg border border-border bg-foreground/5 px-4 py-2 text-[11px] font-mono uppercase tracking-[0.2em] text-foreground/80 hover:bg-foreground/10"
          >
            Ciktiyi ac
          </button>
        )}
        <button
          type="button"
          onClick={handleOpenLibrary}
          className="inline-flex items-center gap-2 rounded-lg border border-primary/20 bg-primary/10 px-4 py-2 text-[11px] font-mono uppercase tracking-[0.2em] text-primary hover:bg-primary/20"
        >
          Clip Library
        </button>
      </div>
    </div>
  );
}

function AutoCutRenderCard({ controller }: AutoCutEditorLayoutProps) {
  const title =
    controller.markers.length > 0
      ? 'Kesim Noktalari ile Render'
      : controller.numClips > 1
        ? 'AI ile Toplu Render'
        : 'Tek Adim Render';
  const description =
    controller.markers.length > 0
      ? `${controller.markers.length + 1} klip, belirlediginiz kesim noktalarina gore uretilir.`
      : controller.numClips > 1
        ? `AI tum videodan ${controller.numClips} viral klip secer ve uretir.`
        : 'faster-whisper transkripsiyon, smart crop, altyazi, format donusumu ve render short pipeline ile ayni akista calisir.';

  return (
    <div className="glass-card p-5 space-y-4 border-primary/20">
      <div className="space-y-1">
        <h3 className="text-xs font-mono uppercase tracking-[0.2em] text-primary">{title}</h3>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
      <button
        onClick={() => void controller.handleRender()}
        disabled={controller.busy || controller.processing || !controller.selectedFile || controller.duration === 0}
        className="btn-primary w-full tracking-[0.25em] font-black flex items-center justify-center gap-3 disabled:opacity-40"
      >
        {controller.busy ? (
          <>
            <Clock className="w-4 h-4" />
            Sirada / Isleniyor
          </>
        ) : controller.processing ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            RENDER...
          </>
        ) : (
          <>
            <ChevronRight className="w-5 h-5" />
            {controller.markers.length > 0
              ? `KESIM NOKTALARI ILE ${controller.markers.length + 1} KLIP URET`
              : controller.numClips > 1
                ? `AI ILE ${controller.numClips} KLIP URET`
                : 'OTOMATIK CUT URET'}
          </>
        )}
      </button>
    </div>
  );
}
