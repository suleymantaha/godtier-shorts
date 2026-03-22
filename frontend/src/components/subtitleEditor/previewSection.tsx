import { RangeSlider } from '../RangeSlider';
import { TimeRangeHeader } from '../TimeRangeHeader';
import { useResolvedMediaSource } from '../ui/protectedMedia';
import { VideoControls } from '../ui/VideoControls';
import { useTranslation } from 'react-i18next';
import { RenderQualitySummaryCard } from './renderQuality';
import type { SubtitleEditorPreviewStackProps } from './sectionTypes';
import type { SubtitleEditorController } from './useSubtitleEditorController';

function VideoPreviewCard({
  handleLoadedMetadata,
  handleTimeUpdate,
  isPlaying,
  setIsPlaying,
  togglePlay,
  videoRef,
  videoSrc,
}: Pick<
  SubtitleEditorController,
  | 'handleLoadedMetadata'
  | 'handleTimeUpdate'
  | 'isPlaying'
  | 'setIsPlaying'
  | 'togglePlay'
  | 'videoRef'
  | 'videoSrc'
>) {
  const resolvedVideoSrc = useResolvedMediaSource(videoSrc);

  return (
    <div className="glass-card overflow-hidden border-primary/20">
      <div className="aspect-video bg-background/80 relative group">
        {videoSrc && (
          <>
            <video
              ref={videoRef}
              src={resolvedVideoSrc}
              className="w-full h-full object-contain"
              onLoadedMetadata={(event) => handleLoadedMetadata(event.currentTarget.duration)}
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
  );
}

function RangeCard({
  duration,
  endTime,
  handleRangeChange,
  startTime,
  visibleCount,
}: {
  duration: number;
  endTime: number;
  handleRangeChange: SubtitleEditorController['handleRangeChange'];
  startTime: number;
  visibleCount: number;
}) {
  const { t } = useTranslation();

  return (
    <div className="glass-card p-5 space-y-4 border-primary/20">
      <TimeRangeHeader
        endTime={endTime}
        extraLabel={t('subtitleEditor.preview.segmentCount', { count: visibleCount })}
        startTime={startTime}
        title={t('subtitleEditor.preview.editableRange')}
      />
      <RangeSlider
        min={0}
        max={duration || 100}
        start={startTime}
        end={endTime}
        onChange={handleRangeChange}
      />
    </div>
  );
}

function resolveProcessingKindLabel(jobId: string | null, t: (key: string) => string): string {
  if (!jobId) {
    return t('subtitleEditor.preview.tracking');
  }
  if (jobId.startsWith('reburn_')) {
    return t('subtitleEditor.preview.reburn');
  }
  if (jobId.startsWith('cliprecover_')) {
    return t('subtitleEditor.preview.clipTranscript');
  }
  if (jobId.startsWith('projecttranscript_') || jobId.startsWith('upload_') || jobId.startsWith('manualcut_')) {
    return t('subtitleEditor.preview.projectTranscript');
  }
  if (jobId.startsWith('manual_')) {
    return t('subtitleEditor.preview.rangeRender');
  }
  return t('subtitleEditor.preview.tracking');
}

function resolveProcessingStatusLabel(status: string, hasCurrentJob: boolean, t: (key: string) => string): string {
  if (!hasCurrentJob) {
    return t('common.status.syncing');
  }
  if (status === 'processing') {
    return t('common.status.processing');
  }
  if (status === 'completed') {
    return t('common.status.completed');
  }
  if (status === 'error') {
    return t('common.status.error');
  }
  if (status === 'cancelled') {
    return t('common.status.cancelled');
  }
  return t('common.status.queued');
}

function resolveProcessingToneClassName(status: string, hasCurrentJob: boolean): string {
  if (!hasCurrentJob) {
    return 'border-amber-500/20 bg-amber-500/5';
  }
  if (status === 'completed') {
    return 'border-emerald-500/20 bg-emerald-500/5';
  }
  if (status === 'error' || status === 'cancelled') {
    return 'border-red-500/20 bg-red-500/5';
  }
  return 'border-primary/20 bg-primary/5';
}

function resolveProcessingHeadline(
  jobId: string | null,
  currentJob: SubtitleEditorController['currentJob'],
  status: string,
  t: (key: string, options?: Record<string, unknown>) => string,
): string {
  if (!currentJob) {
    return t('subtitleEditor.preview.reconnecting');
  }

  const kindLabel = resolveProcessingKindLabel(jobId, t);
  if (status === 'queued') {
    return t('subtitleEditor.preview.queued', { kind: kindLabel });
  }
  if (status === 'processing') {
    return t('subtitleEditor.preview.processing', { kind: kindLabel });
  }
  if (status === 'completed') {
    return t('subtitleEditor.preview.completed', { kind: kindLabel });
  }
  if (status === 'cancelled') {
    return t('subtitleEditor.preview.cancelled', { kind: kindLabel });
  }
  return t('subtitleEditor.preview.failed', { kind: kindLabel });
}

function formatProcessingBytes(value?: number): string | null {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) {
    return null;
  }

  const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB'];
  let normalized = value;
  let unitIndex = 0;
  while (normalized >= 1024 && unitIndex < units.length - 1) {
    normalized /= 1024;
    unitIndex += 1;
  }

  return `${normalized.toFixed(unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

function resolveProcessingSummary(currentJob: SubtitleEditorController['currentJob']): string | null {
  if (currentJob?.download_progress?.phase !== 'download') {
    return null;
  }

  const downloaded = formatProcessingBytes(currentJob.download_progress.downloaded_bytes);
  const total = formatProcessingBytes(
    currentJob.download_progress.total_bytes ?? currentJob.download_progress.total_bytes_estimate,
  );
  const parts = [
    downloaded && total ? `${downloaded} / ${total}` : null,
    typeof currentJob.download_progress.percent === 'number'
      ? `${currentJob.download_progress.percent.toFixed(1)}%`
      : null,
    currentJob.download_progress.speed_text ?? null,
    currentJob.download_progress.eta_text ? `ETA ${currentJob.download_progress.eta_text}` : null,
  ].filter(Boolean);

  return parts.length > 0 ? parts.join(' • ') : null;
}

function ProcessingStatusCard({
  currentJob,
  currentJobId,
}: {
  currentJob: SubtitleEditorController['currentJob'];
  currentJobId: SubtitleEditorController['currentJobId'];
}) {
  const { t } = useTranslation();
  const status = currentJob?.status ?? 'queued';
  const toneClassName = resolveProcessingToneClassName(status, Boolean(currentJob));
  const kindLabel = resolveProcessingKindLabel(currentJob?.job_id ?? currentJobId ?? null, t);
  const summary = resolveProcessingSummary(currentJob);
  const headline = resolveProcessingHeadline(currentJob?.job_id ?? currentJobId ?? null, currentJob, status, t);
  const progress = currentJob ? Math.max(5, currentJob.progress) : 5;
  const timeline = currentJob?.timeline?.slice(-3) ?? [];

  return (
    <div className={`glass-card p-5 space-y-4 ${toneClassName}`} data-testid="subtitle-processing-status">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="space-y-1">
          <div className="text-[11px] font-mono uppercase tracking-[0.24em] opacity-80">{t('subtitleEditor.preview.processingStatus')}</div>
          <div className="text-sm font-bold uppercase tracking-[0.18em]">{kindLabel}</div>
          <p className="text-xs text-muted-foreground">{headline}</p>
        </div>
        <div className="rounded-full border border-current/20 px-3 py-1 text-[11px] font-mono uppercase tracking-widest">
          {resolveProcessingStatusLabel(status, Boolean(currentJob), t)}
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between gap-3 text-[11px] font-mono uppercase">
          <span>{currentJob?.last_message ?? t('subtitleEditor.preview.reconnectingStatus')}</span>
          <span>{progress}%</span>
        </div>
        <div className="h-1.5 rounded-full bg-foreground/10 overflow-hidden">
          <div
            className="h-full rounded-full bg-primary transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {summary && (
        <div className="rounded-xl border border-current/15 bg-black/15 px-3 py-2 text-[11px] font-mono uppercase tracking-widest">
          {summary}
        </div>
      )}

      {timeline.length > 0 && (
        <div className="space-y-2">
          {timeline.map((entry) => (
            <div key={entry.id} className="flex items-center justify-between gap-3 text-[11px]">
              <span className="text-muted-foreground truncate">{entry.message}</span>
              <span className="font-mono uppercase text-muted-foreground/80">{entry.progress}%</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function SubtitleEditorPreviewStack({
  clipRenderMetadata,
  currentJob,
  currentJobId,
  duration,
  endTime,
  handleLoadedMetadata,
  handleRangeChange,
  handleTimeUpdate,
  isPlaying,
  mode,
  rangeReady,
  selectedClip,
  setIsPlaying,
  startTime,
  togglePlay,
  transcriptCount,
  videoRef,
  videoSrc,
  visibleCount,
}: SubtitleEditorPreviewStackProps) {
  return (
    <>
      <VideoPreviewCard
        handleLoadedMetadata={handleLoadedMetadata}
        handleTimeUpdate={handleTimeUpdate}
        isPlaying={isPlaying}
        setIsPlaying={setIsPlaying}
        togglePlay={togglePlay}
        videoRef={videoRef}
        videoSrc={videoSrc}
      />
      {(currentJob || currentJobId) && (
        <ProcessingStatusCard currentJob={currentJob} currentJobId={currentJobId} />
      )}
      {rangeReady && mode === 'project' && transcriptCount > 0 && (
        <RangeCard
          duration={duration}
          endTime={endTime}
          handleRangeChange={handleRangeChange}
          startTime={startTime}
          visibleCount={visibleCount}
        />
      )}
      {mode === 'clip' && selectedClip && clipRenderMetadata && (
        <RenderQualitySummaryCard renderMetadata={clipRenderMetadata} />
      )}
    </>
  );
}
