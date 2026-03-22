import { AlertCircle, ChevronRight, Film, Save, Scissors, Sparkles, Waves } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { MAX_UPLOAD_BYTES } from '../../config';
import { getAnimationSelectOptions, STYLE_OPTIONS, isStyleName, isSubtitleAnimationType } from '../../config/subtitleStyles';
import { toTimeStr } from '../../utils/time';
import { RangeSlider } from '../RangeSlider';
import { TimeRangeHeader } from '../TimeRangeHeader';
import { VideoOverlay } from '../VideoOverlay';
import { Select } from '../ui/Select';
import { useResolvedMediaSource } from '../ui/protectedMedia';
import { VideoControls } from '../ui/VideoControls';
import { formatUploadLimit } from './helpers';
import type { EditorController } from './useEditorController';

export function EditorLayout({ controller }: { controller: EditorController }) {
  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <EditorUploadCard
        fileInputRef={controller.fileInputRef}
        handleFileUpload={controller.handleFileUpload}
        transcribing={controller.transcribing}
        uploading={controller.uploading}
      />
      <EditorPreviewCard
        animationType={controller.animationType}
        centerX={controller.centerX}
        currentTime={controller.currentTime}
        duration={controller.duration}
        endTime={controller.endTime}
        handleLoadedMetadata={controller.handleLoadedMetadata}
        handleTimeUpdate={controller.handleTimeUpdate}
        isPlaying={controller.isPlaying}
        jumpToEnd={controller.jumpToEnd}
        jumpToStart={controller.jumpToStart}
        onCropChange={controller.setCenterX}
        onPause={() => controller.setIsPlaying(false)}
        onPlay={() => controller.setIsPlaying(true)}
        onRangeChange={(start, end) => {
          controller.setStartTime(start);
          controller.setEndTime(end);
        }}
        startTime={controller.startTime}
        style={controller.style}
        togglePlay={controller.togglePlay}
        transcript={controller.transcript}
        videoRef={controller.videoRef}
        videoSrc={controller.videoSrc}
      />
      <EditorTranscriptCard
        currentTime={controller.currentTime}
        mode={controller.mode}
        onSave={controller.handleSaveTranscript}
        onUpdateSubtitle={controller.updateSubtitleText}
        saving={controller.saving}
        transcribing={controller.transcribing}
        visibleTranscript={controller.visibleTranscript}
      />
      <EditorRenderCard
        animationType={controller.animationType}
        duration={controller.duration}
        error={controller.error}
        numClips={controller.numClips}
        onAnimationTypeChange={controller.setAnimationType}
        onBatchRender={controller.handleProcessBatch}
        onManualRender={controller.handleProcessManual}
        onNumClipsChange={controller.setNumClips}
        onStyleChange={controller.setStyle}
        processing={controller.processing}
        style={controller.style}
        transcribing={controller.transcribing}
      />
    </div>
  );
}

function EditorUploadCard({
  fileInputRef,
  handleFileUpload,
  transcribing,
  uploading,
}: {
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  handleFileUpload: (event: React.ChangeEvent<HTMLInputElement>) => Promise<void>;
  transcribing: boolean;
  uploading: boolean;
}) {
  const { t } = useTranslation();

  return (
    <div className="glass-card p-5 border-accent/20">
      <div className="flex items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Film className="w-4 h-4 text-accent" />
            <h3 className="text-xs font-mono uppercase tracking-[0.2em] text-accent">
              {uploading
                ? t('editorWorkspace.upload.uploadingTitle')
                : transcribing
                  ? t('editorWorkspace.upload.transcribingTitle')
                  : t('editorWorkspace.upload.idleTitle')}
            </h3>
          </div>
          <p className="text-[11px] text-muted-foreground uppercase">
            {transcribing ? t('editorWorkspace.upload.transcribingSubtitle') : t('editorWorkspace.upload.idleSubtitle')}
          </p>
          <p className="text-[10px] text-muted-foreground">{t('editorWorkspace.upload.maxFileSize', { size: formatUploadLimit(MAX_UPLOAD_BYTES) })}</p>
        </div>
        <div className="flex items-center gap-2">
          {transcribing && <div className="w-3 h-3 border-2 border-accent border-t-transparent animate-spin rounded-full" />}
          <input ref={fileInputRef} type="file" onChange={handleFileUpload} className="hidden" accept="video/*" />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading || transcribing}
            className="btn-primary py-2 px-5 text-[11px] tracking-[0.2em] flex items-center gap-2 disabled:opacity-50"
          >
            {uploading ? t('editorWorkspace.upload.buttonUploading') : t('editorWorkspace.upload.buttonIdle')}
          </button>
        </div>
      </div>
    </div>
  );
}

function EditorPreviewCard({
  animationType,
  centerX,
  currentTime,
  duration,
  endTime,
  handleLoadedMetadata,
  handleTimeUpdate,
  isPlaying,
  jumpToEnd,
  jumpToStart,
  onCropChange,
  onPause,
  onPlay,
  onRangeChange,
  startTime,
  style,
  togglePlay,
  transcript,
  videoRef,
  videoSrc,
}: {
  animationType: EditorController['animationType'];
  centerX: number;
  currentTime: number;
  duration: number;
  endTime: number;
  handleLoadedMetadata: (event: React.SyntheticEvent<HTMLVideoElement>) => void;
  handleTimeUpdate: () => void;
  isPlaying: boolean;
  jumpToEnd: () => void;
  jumpToStart: () => void;
  onCropChange: (value: number) => void;
  onPause: () => void;
  onPlay: () => void;
  onRangeChange: (start: number, end: number) => void;
  startTime: number;
  style: EditorController['style'];
  togglePlay: () => void;
  transcript: EditorController['transcript'];
  videoRef: React.RefObject<HTMLVideoElement | null>;
  videoSrc?: string;
}) {
  const { t } = useTranslation();
  const resolvedVideoSrc = useResolvedMediaSource(videoSrc);

  return (
    <div className="glass-card overflow-hidden border-primary/20 shadow-lg shadow-primary/5 ring-1 ring-primary/10">
      <div className="aspect-video bg-black/60 relative group">
        <video
          ref={videoRef}
          src={resolvedVideoSrc}
          className="w-full h-full object-contain"
          onLoadedMetadata={handleLoadedMetadata}
          onTimeUpdate={handleTimeUpdate}
          onPlay={onPlay}
          onPause={onPause}
          controls={false}
        />
        <VideoOverlay
          animationType={animationType}
          currentTime={currentTime}
          transcript={transcript}
          style={style}
          centerX={centerX}
          onCropChange={onCropChange}
        />
        <VideoControls isPlaying={isPlaying} onTogglePlay={togglePlay} />
      </div>
      <div className="p-5 bg-black/30 space-y-6">
        <TimeRangeHeader endTime={endTime} startTime={startTime} title={t('editorWorkspace.preview.rangeTitle')} />
        <RangeSlider min={0} max={duration || 100} start={startTime} end={endTime} onChange={onRangeChange} />
        <div className="flex gap-2">
          <PreviewJumpButton label={`▶ ${t('editorWorkspace.preview.watchStart')}`} onClick={jumpToStart} tone="primary" />
          <PreviewJumpButton label={`▶ ${t('editorWorkspace.preview.watchEnd')}`} onClick={jumpToEnd} tone="accent" />
        </div>
      </div>
    </div>
  );
}

function PreviewJumpButton({
  label,
  onClick,
  tone,
}: {
  label: string;
  onClick: () => void;
  tone: 'accent' | 'primary';
}) {
  const toneClass = tone === 'accent'
    ? 'bg-accent/10 border-accent/20 hover:bg-accent/20 text-accent'
    : 'bg-primary/10 border-primary/20 hover:bg-primary/20 text-primary';

  return (
    <button onClick={onClick} className={`flex-1 py-1.5 text-[11px] font-mono uppercase tracking-widest border rounded transition-colors ${toneClass}`}>
      {label}
    </button>
  );
}

function EditorTranscriptCard({
  currentTime,
  mode,
  onSave,
  onUpdateSubtitle,
  saving,
  transcribing,
  visibleTranscript,
}: {
  currentTime: number;
  mode: 'master' | 'clip';
  onSave: () => void;
  onUpdateSubtitle: (index: number, text: string) => void;
  saving: boolean;
  transcribing: boolean;
  visibleTranscript: EditorController['visibleTranscript'];
}) {
  const { t } = useTranslation();

  if (visibleTranscript.length === 0 && !transcribing) {
    return null;
  }

  return (
    <div className="glass-card p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold uppercase tracking-[0.2em] flex items-center gap-2">
          <Scissors className="w-4 h-4 text-primary" />
          {transcribing ? t('editorWorkspace.transcript.loadingTitle') : t('editorWorkspace.transcript.title')}
        </h3>
        {!transcribing && (
          <button
            onClick={onSave}
            disabled={saving}
            className="px-4 py-2 rounded-lg bg-white/5 border border-white/10 hover:bg-white/10 text-[11px] font-mono uppercase transition-all flex items-center gap-2"
          >
            {saving ? <div className="w-3 h-3 border-2 border-primary border-t-transparent animate-spin rounded-full" /> : <Save className="w-3 h-3" />}
            {mode === 'clip' ? t('editorWorkspace.transcript.saveAndReburn') : t('editorWorkspace.transcript.save')}
          </button>
        )}
      </div>
      <div className="max-h-[300px] overflow-y-auto space-y-2 pr-2 custom-scrollbar">
        {visibleTranscript.map(({ index, segment }) => (
          <TranscriptEntry
            key={index}
            currentTime={currentTime}
            index={index}
            onChange={(text) => onUpdateSubtitle(index, text)}
            segment={segment}
          />
        ))}
      </div>
    </div>
  );
}

function TranscriptEntry({
  currentTime,
  index,
  onChange,
  segment,
}: {
  currentTime: number;
  index: number;
  onChange: (text: string) => void;
  segment: EditorController['transcript'][number];
}) {
  const isActive = currentTime >= segment.start && currentTime <= segment.end;

  return (
    <div id={`sub-${index}`} className={`flex gap-3 group transition-all duration-300 ${isActive ? 'scale-[1.02] z-10' : 'opacity-40'}`}>
      <div className={`text-[11px] font-mono w-14 pt-3 shrink-0 ${isActive ? 'text-primary font-black' : 'text-muted-foreground'}`}>
        {toTimeStr(segment.start)}
      </div>
      <textarea
        value={segment.text}
        onChange={(event) => onChange(event.target.value)}
        className={`flex-1 bg-white/5 border rounded-lg p-2.5 text-sm transition-all outline-none resize-none h-12 ${isActive ? 'border-primary/50 bg-white/10 shadow-lg shadow-primary/5' : 'border-white/5 group-hover:border-white/10'}`}
      />
    </div>
  );
}

function EditorRenderCard({
  animationType,
  duration,
  error,
  numClips,
  onAnimationTypeChange,
  onBatchRender,
  onManualRender,
  onNumClipsChange,
  onStyleChange,
  processing,
  style,
  transcribing,
}: {
  animationType: EditorController['animationType'];
  duration: number;
  error: string | null;
  numClips: number;
  onAnimationTypeChange: React.Dispatch<React.SetStateAction<EditorController['animationType']>>;
  onBatchRender: () => void;
  onManualRender: () => void;
  onNumClipsChange: React.Dispatch<React.SetStateAction<number>>;
  onStyleChange: React.Dispatch<React.SetStateAction<EditorController['style']>>;
  processing: boolean;
  style: EditorController['style'];
  transcribing: boolean;
}) {
  const { t } = useTranslation();

  return (
    <div className="glass-card p-5 space-y-4 border-secondary/20">
      <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-[0.2em] text-secondary">
        <Sparkles className="w-4 h-4" /> {t('editorWorkspace.render.title')}
      </div>
      <EditorStyleControls
        animationType={animationType}
        onAnimationTypeChange={onAnimationTypeChange}
        onStyleChange={onStyleChange}
        style={style}
      />
      {error && (
        <div role="alert" className="flex items-center gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-xs font-mono text-red-400">
          <AlertCircle className="w-4 h-4 shrink-0" aria-hidden="true" /> {error}
        </div>
      )}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <EditorBatchPanel
          duration={duration}
          numClips={numClips}
          onBatchRender={onBatchRender}
          onNumClipsChange={onNumClipsChange}
          processing={processing}
          transcribing={transcribing}
        />
        <EditorManualRenderButton
          duration={duration}
          onManualRender={onManualRender}
          processing={processing}
          transcribing={transcribing}
        />
      </div>
    </div>
  );
}

function EditorStyleControls({
  animationType,
  onAnimationTypeChange,
  onStyleChange,
  style,
}: {
  animationType: EditorController['animationType'];
  onAnimationTypeChange: React.Dispatch<React.SetStateAction<EditorController['animationType']>>;
  onStyleChange: React.Dispatch<React.SetStateAction<EditorController['style']>>;
  style: EditorController['style'];
}) {
  const { t } = useTranslation();

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      <div className="space-y-2">
        <label className="text-[11px] font-mono uppercase tracking-widest text-muted-foreground">{t('editorWorkspace.render.visualStyle')}</label>
        <Select
          value={style}
          onChange={(value) => onStyleChange(isStyleName(value) ? value : 'HORMOZI')}
          options={STYLE_OPTIONS.map((styleOption) => ({ label: styleOption, value: styleOption }))}
          icon={<Sparkles className="w-4 h-4 text-secondary/50" />}
        />
      </div>
      <div className="space-y-2">
        <label className="text-[11px] font-mono uppercase tracking-widest text-muted-foreground">{t('editorWorkspace.render.motionStyle')}</label>
        <Select
          value={animationType}
          onChange={(value) => onAnimationTypeChange(isSubtitleAnimationType(value) ? value : 'default')}
          options={ANIMATION_SELECT_OPTIONS}
          icon={<Waves className="w-4 h-4 text-secondary/50" />}
        />
      </div>
    </div>
  );
}

function EditorBatchPanel({
  duration,
  numClips,
  onBatchRender,
  onNumClipsChange,
  processing,
  transcribing,
}: {
  duration: number;
  numClips: number;
  onBatchRender: () => void;
  onNumClipsChange: React.Dispatch<React.SetStateAction<number>>;
  processing: boolean;
  transcribing: boolean;
}) {
  const { t } = useTranslation();

  return (
    <div className="p-3 rounded-xl bg-primary/5 border border-primary/10 space-y-3">
      <span className="text-[11px] font-mono text-primary uppercase tracking-widest block">{t('editorWorkspace.render.batchTitle')}</span>
      <div className="flex items-center gap-2">
        <input
          type="number"
          min={1}
          max={10}
          value={numClips}
          onChange={(event) => onNumClipsChange(Number(event.target.value))}
          className="w-full bg-black/40 border border-white/10 rounded px-2 py-2 text-xs font-mono text-center"
        />
      </div>
      <button
        onClick={onBatchRender}
        disabled={processing || transcribing || duration === 0}
        className="w-full py-2.5 rounded-lg bg-primary/10 border border-primary/30 hover:bg-primary/20 text-primary text-[11px] font-mono uppercase transition-all disabled:opacity-30"
      >
        {t('editorWorkspace.render.batchAction')}
      </button>
    </div>
  );
}

function EditorManualRenderButton({
  duration,
  onManualRender,
  processing,
  transcribing,
}: {
  duration: number;
  onManualRender: () => void;
  processing: boolean;
  transcribing: boolean;
}) {
  const { t } = useTranslation();

  return (
    <button
      onClick={onManualRender}
      disabled={processing || transcribing || duration === 0}
      className="btn-primary w-full tracking-[0.25em] font-black flex items-center justify-center gap-3 disabled:opacity-40 relative group overflow-hidden"
    >
      {processing ? (
        <>
          <div className="w-4 h-4 border-2 border-background border-t-transparent animate-spin rounded-full" /> {t('editorWorkspace.render.processing')}
        </>
      ) : (
        <>
          <ChevronRight className="w-5 h-5" /> {t('editorWorkspace.render.manualAction')}
        </>
      )}
    </button>
  );
}
const ANIMATION_SELECT_OPTIONS = getAnimationSelectOptions();
