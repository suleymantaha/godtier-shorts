import { AlertCircle, CheckCircle2, Film, RefreshCw, Save, Scissors, Subtitles } from 'lucide-react';

import type { RenderMetadata } from '../../types';
import { toTimeStr } from '../../utils/time';
import { RangeSlider } from '../RangeSlider';
import { TimeRangeHeader } from '../TimeRangeHeader';
import { Select } from '../ui/Select';
import { useResolvedMediaSource } from '../ui/protectedMedia';
import { VideoControls } from '../ui/VideoControls';
import { SUBTITLE_ANIMATION_OPTIONS, SUBTITLE_STYLE_OPTIONS } from './helpers';
import type { SubtitleEditorController } from './useSubtitleEditorController';

export function SubtitleEditorLayout({ controller }: { controller: SubtitleEditorController }) {
  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <SubtitleEditorPanels controller={controller} />
    </div>
  );
}

function resolveSubtitlePanelProps(controller: SubtitleEditorController) {
  const {
    animationType,
    clipTranscriptCapabilities,
    clipTranscriptStatus,
    clipRenderMetadata,
    clips,
    currentJob,
    currentTime,
    duration,
    endTime,
    error,
    handleClipSelect,
    handleLoadedMetadata,
    handleRecoverProjectTranscript,
    handleRecoverTranscript,
    handleRenderClip,
    handleSave,
    handleTimeUpdate,
    hasSelection,
    isPlaying,
    lockedToClip,
    loading,
    mode,
    projects,
    projectsError,
    projectTranscriptStatus,
    reburnWarningMessage,
    recommendedRecoveryStrategy,
    resolveClipSelectValue,
    saving,
    selectClipMode,
    selectProjectMode,
    selectedClip,
    selectedProjectId,
    setEndTime,
    setIsPlaying,
    setSelectedProjectId,
    setStartTime,
    setAnimationType,
    setStyle,
    startTime,
    style,
    successMessage,
    togglePlay,
    transcript,
    updateSubtitleText,
    videoRef,
    videoSrc,
    visibleTranscriptEntries,
  } = controller;

  return {
    animationType,
    clipTranscriptCapabilities,
    clipTranscriptStatus,
    clipRenderMetadata,
    clips,
    currentJob,
    currentTime,
    duration,
    endTime,
    error,
    handleClipSelect,
    handleLoadedMetadata,
    handleRecoverProjectTranscript,
    handleRecoverTranscript,
    handleRenderClip,
    handleSave,
    handleTimeUpdate,
    hasSelection,
    isPlaying,
    lockedToClip,
    loading,
    mode,
    projects,
    projectsError,
    projectTranscriptStatus,
    reburnWarningMessage,
    recommendedRecoveryStrategy,
    resolveClipSelectValue,
    saving,
    selectClipMode,
    selectProjectMode,
    selectedClip,
    selectedProjectId,
    setEndTime,
    setIsPlaying,
    setSelectedProjectId,
    setStartTime,
    setAnimationType,
    setStyle,
    startTime,
    style,
    successMessage,
    togglePlay,
    transcript,
    updateSubtitleText,
    videoRef,
    videoSrc,
    visibleTranscriptEntries,
  };
}

function SubtitleEditorPanels({ controller }: { controller: SubtitleEditorController }) {
  const props = resolveSubtitlePanelProps(controller);

  return (
    <>
      {!props.lockedToClip && (
        <SelectionCard
          clips={props.clips}
          handleClipSelect={props.handleClipSelect}
          mode={props.mode}
          projects={props.projects}
          projectsError={props.projectsError}
          resolveClipSelectValue={props.resolveClipSelectValue}
          selectClipMode={props.selectClipMode}
          selectProjectMode={props.selectProjectMode}
          selectedClip={props.selectedClip}
          selectedProjectId={props.selectedProjectId}
          setSelectedProjectId={props.setSelectedProjectId}
        />
      )}
      {props.hasSelection && (
        <SubtitleEditorContent
          clipTranscriptCapabilities={props.clipTranscriptCapabilities}
          clipTranscriptStatus={props.clipTranscriptStatus}
          clipRenderMetadata={props.clipRenderMetadata}
          currentJob={props.currentJob}
          currentTime={props.currentTime}
          duration={props.duration}
          endTime={props.endTime}
          error={props.error}
          handleLoadedMetadata={props.handleLoadedMetadata}
          handleRecoverProjectTranscript={props.handleRecoverProjectTranscript}
          handleRecoverTranscript={props.handleRecoverTranscript}
          handleRenderClip={props.handleRenderClip}
          handleSave={props.handleSave}
          handleTimeUpdate={props.handleTimeUpdate}
          isPlaying={props.isPlaying}
          lockedToClip={props.lockedToClip}
          loading={props.loading}
          mode={props.mode}
          projectTranscriptStatus={props.projectTranscriptStatus}
          reburnWarningMessage={props.reburnWarningMessage}
          recommendedRecoveryStrategy={props.recommendedRecoveryStrategy}
          saving={props.saving}
          selectedClip={props.selectedClip}
          selectedProjectId={props.selectedProjectId}
          setAnimationType={props.setAnimationType}
          setEndTime={props.setEndTime}
          setIsPlaying={props.setIsPlaying}
          setStartTime={props.setStartTime}
          setStyle={props.setStyle}
          animationType={props.animationType}
          startTime={props.startTime}
          style={props.style}
          successMessage={props.successMessage}
          togglePlay={props.togglePlay}
          transcript={props.transcript}
          updateSubtitleText={props.updateSubtitleText}
          videoRef={props.videoRef}
          videoSrc={props.videoSrc}
          visibleTranscriptEntries={props.visibleTranscriptEntries}
        />
      )}
    </>
  );
}

function SubtitleEditorContent(props: {
  clipTranscriptCapabilities: SubtitleEditorController['clipTranscriptCapabilities'];
  clipTranscriptStatus: SubtitleEditorController['clipTranscriptStatus'];
  clipRenderMetadata: SubtitleEditorController['clipRenderMetadata'];
  animationType: SubtitleEditorController['animationType'];
  currentJob: SubtitleEditorController['currentJob'];
  currentTime: number;
  duration: number;
  endTime: number;
  error: string | null;
  handleLoadedMetadata: SubtitleEditorController['handleLoadedMetadata'];
  handleRecoverProjectTranscript: SubtitleEditorController['handleRecoverProjectTranscript'];
  handleRecoverTranscript: SubtitleEditorController['handleRecoverTranscript'];
  handleRenderClip: SubtitleEditorController['handleRenderClip'];
  handleSave: SubtitleEditorController['handleSave'];
  handleTimeUpdate: SubtitleEditorController['handleTimeUpdate'];
  isPlaying: boolean;
  lockedToClip: boolean;
  loading: boolean;
  mode: SubtitleEditorController['mode'];
  projectTranscriptStatus: SubtitleEditorController['projectTranscriptStatus'];
  reburnWarningMessage: SubtitleEditorController['reburnWarningMessage'];
  recommendedRecoveryStrategy: SubtitleEditorController['recommendedRecoveryStrategy'];
  saving: boolean;
  selectedClip: SubtitleEditorController['selectedClip'];
  selectedProjectId: string | null;
  setAnimationType: SubtitleEditorController['setAnimationType'];
  setEndTime: SubtitleEditorController['setEndTime'];
  setIsPlaying: SubtitleEditorController['setIsPlaying'];
  setStartTime: SubtitleEditorController['setStartTime'];
  setStyle: SubtitleEditorController['setStyle'];
  startTime: number;
  style: SubtitleEditorController['style'];
  successMessage: string | null;
  togglePlay: SubtitleEditorController['togglePlay'];
  transcript: SubtitleEditorController['transcript'];
  updateSubtitleText: SubtitleEditorController['updateSubtitleText'];
  videoRef: SubtitleEditorController['videoRef'];
  videoSrc: SubtitleEditorController['videoSrc'];
  visibleTranscriptEntries: SubtitleEditorController['visibleTranscriptEntries'];
}) {
  return (
    <>
      <VideoPreviewCard
        handleLoadedMetadata={props.handleLoadedMetadata}
        handleTimeUpdate={props.handleTimeUpdate}
        isPlaying={props.isPlaying}
        setIsPlaying={props.setIsPlaying}
        togglePlay={props.togglePlay}
        videoRef={props.videoRef}
        videoSrc={props.videoSrc}
      />
      {!props.loading && props.mode === 'project' && props.transcript.length > 0 && (
        <RangeCard
          duration={props.duration}
          endTime={props.endTime}
          setEndTime={props.setEndTime}
          setStartTime={props.setStartTime}
          startTime={props.startTime}
          visibleCount={props.visibleTranscriptEntries.length}
        />
      )}
      {props.mode === 'clip' && props.selectedClip && props.clipRenderMetadata && (
        <RenderQualitySummaryCard renderMetadata={props.clipRenderMetadata} />
      )}
      <TranscriptCard
        clipTranscriptCapabilities={props.clipTranscriptCapabilities}
        clipTranscriptStatus={props.clipTranscriptStatus}
        currentJob={props.currentJob}
        currentTime={props.currentTime}
        endTime={props.endTime}
        error={props.error}
        handleRecoverProjectTranscript={props.handleRecoverProjectTranscript}
        handleRecoverTranscript={props.handleRecoverTranscript}
        handleRenderClip={props.handleRenderClip}
        handleSave={props.handleSave}
        lockedToClip={props.lockedToClip}
        loading={props.loading}
        mode={props.mode}
        projectTranscriptStatus={props.projectTranscriptStatus}
        reburnWarningMessage={props.reburnWarningMessage}
        recommendedRecoveryStrategy={props.recommendedRecoveryStrategy}
        saving={props.saving}
        selectedClip={props.selectedClip}
        selectedProjectId={props.selectedProjectId}
        setAnimationType={props.setAnimationType}
        setStyle={props.setStyle}
        animationType={props.animationType}
        startTime={props.startTime}
        style={props.style}
        successMessage={props.successMessage}
        transcript={props.transcript}
        updateSubtitleText={props.updateSubtitleText}
        videoRef={props.videoRef}
        visibleTranscriptEntries={props.visibleTranscriptEntries}
      />
    </>
  );
}

const QUALITY_TONE_CLASSNAMES = {
  degraded: 'border-red-500/25 bg-red-500/8 text-red-100',
  good: 'border-emerald-500/25 bg-emerald-500/8 text-emerald-100',
  watch: 'border-amber-500/25 bg-amber-500/8 text-amber-100',
} as const;

const QUALITY_DRIFT_WARNING_MS = 80;

function resolveQualityTone(score?: number | null): keyof typeof QUALITY_TONE_CLASSNAMES {
  if ((score ?? 0) >= 85) {
    return 'good';
  }
  if ((score ?? 0) >= 70) {
    return 'watch';
  }
  return 'degraded';
}

function buildRenderWarnings(renderMetadata: RenderMetadata): string[] {
  const warnings: string[] = [];
  if (renderMetadata.tracking_quality?.status === 'fallback') {
    warnings.push('Tracking fallback aktifti.');
  }
  if (renderMetadata.transcript_quality?.status === 'partial' || renderMetadata.transcript_quality?.status === 'degraded') {
    warnings.push('Transcript kalitesi tam değil.');
  }
  if (renderMetadata.subtitle_layout_quality?.subtitle_overflow_detected || renderMetadata.transcript_quality?.subtitle_overflow_detected) {
    warnings.push('Subtitle overflow tespit edildi.');
  }
  if ((renderMetadata.debug_timing?.merged_output_drift_ms ?? 0) >= QUALITY_DRIFT_WARNING_MS) {
    warnings.push('A/V drift yükseldi.');
  }
  const audioStatus = renderMetadata.audio_validation?.audio_validation_status;
  if (audioStatus === 'missing' || audioStatus === 'invalid' || renderMetadata.audio_validation?.has_audio === false) {
    warnings.push('Audio muted veya geçersiz.');
  }
  return warnings.slice(0, 3);
}

function RenderQualitySummaryCard({ renderMetadata }: { renderMetadata: RenderMetadata }) {
  const score = renderMetadata.render_quality_score ?? 0;
  const tone = resolveQualityTone(score);
  const warnings = buildRenderWarnings(renderMetadata);
  const transcriptStatus = renderMetadata.transcript_quality?.status ?? 'unknown';
  const trackingStatus = renderMetadata.tracking_quality?.status ?? 'unknown';
  const driftMs = renderMetadata.debug_timing?.merged_output_drift_ms ?? 0;
  const audioStatus = renderMetadata.audio_validation?.audio_validation_status ?? 'unknown';

  return (
    <div className={`glass-card p-5 space-y-4 ${QUALITY_TONE_CLASSNAMES[tone]}`} data-testid="render-quality-summary">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="space-y-1">
          <p className="text-[11px] font-mono uppercase tracking-[0.24em] opacity-80">Render Quality</p>
          <h3 className="text-sm font-bold uppercase tracking-[0.18em]">Kalite Özeti</h3>
        </div>
        <div className="rounded-full border border-current/25 px-3 py-1 text-[11px] font-mono uppercase tracking-widest">
          Score {score} / 100
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 text-xs sm:grid-cols-4">
        <MetricPill label="Tracking" value={trackingStatus} />
        <MetricPill label="Transcript" value={transcriptStatus} />
        <MetricPill label="Drift" value={`${driftMs.toFixed(1)} ms`} />
        <MetricPill label="Audio" value={audioStatus} />
      </div>

      {warnings.length > 0 ? (
        <div className="space-y-2">
          {warnings.map((warning) => (
            <div key={warning} className="flex items-start gap-2 text-xs leading-5">
              <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>{warning}</span>
            </div>
          ))}
        </div>
      ) : (
        <div className="flex items-start gap-2 text-xs leading-5">
          <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>Bu clip için takip, transcript ve zamanlama sinyalleri temiz görünüyor.</span>
        </div>
      )}
    </div>
  );
}

function MetricPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-current/15 bg-black/15 px-3 py-2">
      <p className="text-[10px] font-mono uppercase tracking-[0.2em] opacity-75">{label}</p>
      <p className="mt-1 font-medium uppercase tracking-[0.08em]">{value}</p>
    </div>
  );
}

function SelectionCard({
  clips,
  handleClipSelect,
  mode,
  projects,
  projectsError,
  resolveClipSelectValue,
  selectClipMode,
  selectProjectMode,
  selectedClip,
  selectedProjectId,
  setSelectedProjectId,
}: Pick<
  SubtitleEditorController,
  | 'clips'
  | 'handleClipSelect'
  | 'mode'
  | 'projects'
  | 'projectsError'
  | 'resolveClipSelectValue'
  | 'selectClipMode'
  | 'selectProjectMode'
  | 'selectedClip'
  | 'selectedProjectId'
  | 'setSelectedProjectId'
>) {
  return (
    <div className="glass-card p-5 border-accent/20">
      <h2 className="text-xs font-mono uppercase tracking-[0.2em] text-accent flex items-center gap-2 mb-4">
        <Subtitles className="w-4 h-4" />
        Altyazı Düzenleme
      </h2>
      <div className="flex flex-col sm:flex-row gap-4">
        <ModeButtons mode={mode} selectClipMode={selectClipMode} selectProjectMode={selectProjectMode} />
        <SourceSelector
          clips={clips}
          handleClipSelect={handleClipSelect}
          mode={mode}
          projects={projects}
          resolveClipSelectValue={resolveClipSelectValue}
          selectedClip={selectedClip}
          selectedProjectId={selectedProjectId}
          setSelectedProjectId={setSelectedProjectId}
        />
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
  );
}

function ModeButtons({
  mode,
  selectClipMode,
  selectProjectMode,
}: Pick<SubtitleEditorController, 'mode' | 'selectClipMode' | 'selectProjectMode'>) {
  return (
    <div className="flex-1 space-y-2">
      <label className="text-[11px] text-muted-foreground uppercase block">Mod</label>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={selectProjectMode}
          className={`px-4 py-2 rounded-lg text-[11px] font-mono uppercase border transition-all ${mode === 'project' ? 'bg-accent/20 border-accent/40 text-foreground' : 'bg-foreground/5 border-border text-muted-foreground'}`}
        >
          Proje
        </button>
        <button
          type="button"
          onClick={selectClipMode}
          className={`px-4 py-2 rounded-lg text-[11px] font-mono uppercase border transition-all ${mode === 'clip' ? 'bg-accent/20 border-accent/40 text-foreground' : 'bg-foreground/5 border-border text-muted-foreground'}`}
        >
          Klip
        </button>
      </div>
    </div>
  );
}

function SourceSelector({
  clips,
  handleClipSelect,
  mode,
  projects,
  resolveClipSelectValue,
  selectedClip,
  selectedProjectId,
  setSelectedProjectId,
}: Pick<
  SubtitleEditorController,
  | 'clips'
  | 'handleClipSelect'
  | 'mode'
  | 'projects'
  | 'resolveClipSelectValue'
  | 'selectedClip'
  | 'selectedProjectId'
  | 'setSelectedProjectId'
>) {
  return (
    <div className="flex-1 space-y-2">
      <label className="text-[11px] text-muted-foreground uppercase block">
        {mode === 'project' ? 'Proje' : 'Klip'}
      </label>
      {mode === 'project' ? (
        <Select
          value={selectedProjectId ?? ''}
          onChange={(value) => setSelectedProjectId(value || null)}
          options={[
            { label: 'Proje seçin', value: '' },
            ...projects.map((project) => ({ label: project.id, value: project.id })),
          ]}
          className="text-xs"
        />
      ) : (
        <Select
          value={resolveClipSelectValue(selectedClip)}
          onChange={handleClipSelect}
          options={[
            { label: 'Klip seçin', value: '' },
            ...clips.map((clip) => ({
              label: clip.name,
              value: `${clip.project ?? 'legacy'}:${clip.name}`,
            })),
          ]}
          className="text-xs"
        />
      )}
    </div>
  );
}

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
  setEndTime,
  setStartTime,
  startTime,
  visibleCount,
}: {
  duration: number;
  endTime: number;
  setEndTime: SubtitleEditorController['setEndTime'];
  setStartTime: SubtitleEditorController['setStartTime'];
  startTime: number;
  visibleCount: number;
}) {
  return (
    <div className="glass-card p-5 space-y-4 border-primary/20">
      <TimeRangeHeader
        endTime={endTime}
        extraLabel={`[${visibleCount} segment]`}
        startTime={startTime}
        title="Düzenlenecek aralık"
      />
      <RangeSlider
        min={0}
        max={duration || 100}
        start={startTime}
        end={endTime}
        onChange={(startTime, endTime) => {
          setStartTime(startTime);
          setEndTime(endTime);
        }}
      />
    </div>
  );
}

function TranscriptCard({
  animationType,
  clipTranscriptCapabilities,
  clipTranscriptStatus,
  currentJob,
  currentTime,
  endTime,
  error,
  handleRecoverProjectTranscript,
  handleRecoverTranscript,
  handleRenderClip,
  handleSave,
  lockedToClip,
  loading,
  mode,
  projectTranscriptStatus,
  reburnWarningMessage,
  recommendedRecoveryStrategy,
  saving,
  selectedClip,
  selectedProjectId,
  setAnimationType,
  setStyle,
  startTime,
  style,
  successMessage,
  transcript,
  updateSubtitleText,
  videoRef,
  visibleTranscriptEntries,
}: Pick<
  SubtitleEditorController,
  | 'animationType'
  | 'clipTranscriptCapabilities'
  | 'clipTranscriptStatus'
  | 'currentJob'
  | 'currentTime'
  | 'endTime'
  | 'error'
  | 'handleRecoverProjectTranscript'
  | 'handleRecoverTranscript'
  | 'handleRenderClip'
  | 'handleSave'
  | 'lockedToClip'
  | 'loading'
  | 'mode'
  | 'projectTranscriptStatus'
  | 'reburnWarningMessage'
  | 'recommendedRecoveryStrategy'
  | 'saving'
  | 'selectedClip'
  | 'selectedProjectId'
  | 'setAnimationType'
  | 'setStyle'
  | 'startTime'
  | 'style'
  | 'successMessage'
  | 'transcript'
  | 'updateSubtitleText'
  | 'videoRef'
  | 'visibleTranscriptEntries'
>) {
  const showProjectTranscriptCard = mode === 'project'
    && !loading
    && transcript.length === 0
    && (projectTranscriptStatus === 'pending' || projectTranscriptStatus === 'failed');
  const showClipPendingCard = mode === 'clip'
    && !loading
    && transcript.length === 0
    && (clipTranscriptStatus === 'project_pending' || clipTranscriptStatus === 'recovering');
  const showRecoveryCard = mode === 'clip'
    && !loading
    && transcript.length === 0
    && (clipTranscriptStatus === 'needs_recovery' || clipTranscriptStatus === 'failed');
  const showReburnWarning = mode === 'clip' && transcript.length > 0 && !clipTranscriptCapabilities.has_raw_backup;

  return (
    <div className="glass-card p-5 space-y-4">
      <TranscriptHeader
        animationType={animationType}
        endTime={endTime}
        handleRenderClip={handleRenderClip}
        handleSave={handleSave}
        lockedToClip={lockedToClip}
        loading={loading}
        mode={mode}
        saving={saving}
        selectedClip={selectedClip}
        selectedProjectId={selectedProjectId}
        setAnimationType={setAnimationType}
        setStyle={setStyle}
        startTime={startTime}
        style={style}
        transcript={transcript}
        visibleCount={visibleTranscriptEntries.length}
      />
      <TranscriptStatus error={error} successMessage={successMessage} />
      {showProjectTranscriptCard && (
        <ProjectTranscriptCard
          currentJob={currentJob}
          handleRecoverProjectTranscript={handleRecoverProjectTranscript}
          projectTranscriptStatus={projectTranscriptStatus}
          saving={saving}
        />
      )}
      {showClipPendingCard && (
        <ClipRecoveryStatusCard
          clipTranscriptCapabilities={clipTranscriptCapabilities}
          clipTranscriptStatus={clipTranscriptStatus}
          currentJob={currentJob}
        />
      )}
      {showRecoveryCard && (
        <RecoveryCard
          clipTranscriptCapabilities={clipTranscriptCapabilities}
          handleRecoverTranscript={handleRecoverTranscript}
          recommendedRecoveryStrategy={recommendedRecoveryStrategy}
          saving={saving}
        />
      )}
      {showReburnWarning && (
        <ReburnWarningCard message={reburnWarningMessage} />
      )}
      <TranscriptList
        currentTime={currentTime}
        updateSubtitleText={updateSubtitleText}
        videoRef={videoRef}
        visibleTranscriptEntries={visibleTranscriptEntries}
      />
    </div>
  );
}

function TranscriptHeader({
  animationType,
  endTime,
  handleRenderClip,
  handleSave,
  lockedToClip,
  loading,
  mode,
  saving,
  selectedClip,
  selectedProjectId,
  setAnimationType,
  setStyle,
  startTime,
  style,
  transcript,
  visibleCount,
}: {
  animationType: SubtitleEditorController['animationType'];
  endTime: number;
  handleRenderClip: SubtitleEditorController['handleRenderClip'];
  handleSave: SubtitleEditorController['handleSave'];
  lockedToClip: boolean;
  loading: boolean;
  mode: SubtitleEditorController['mode'];
  saving: boolean;
  selectedClip: SubtitleEditorController['selectedClip'];
  selectedProjectId: string | null;
  setAnimationType: SubtitleEditorController['setAnimationType'];
  setStyle: SubtitleEditorController['setStyle'];
  startTime: number;
  style: SubtitleEditorController['style'];
  transcript: SubtitleEditorController['transcript'];
  visibleCount: number;
}) {
  return (
    <div className="flex items-center justify-between gap-4 flex-wrap">
      <div className="space-y-1">
        <h3 className="text-sm font-bold uppercase tracking-[0.2em] flex items-center gap-2">
          <Film className="w-4 h-4 text-primary" />
          {loading ? 'Yükleniyor...' : `Altyazı (${visibleCount} / ${transcript.length} segment)`}
        </h3>
        {lockedToClip && selectedClip && (
          <p className="text-[11px] font-mono uppercase tracking-widest text-muted-foreground">
            ODAK KLIP: {selectedClip.name}
          </p>
        )}
      </div>
      <div className="flex items-center gap-3">
        <Select
          value={style}
          onChange={setStyle}
          options={SUBTITLE_STYLE_OPTIONS}
          className="w-40 text-xs"
        />
        <Select
          value={animationType}
          onChange={setAnimationType}
          options={SUBTITLE_ANIMATION_OPTIONS}
          className="w-40 text-xs"
        />
        {!loading && (
          <TranscriptActions
            endTime={endTime}
            handleRenderClip={handleRenderClip}
            handleSave={handleSave}
            mode={mode}
            saving={saving}
            selectedProjectId={selectedProjectId}
            startTime={startTime}
            transcript={transcript}
          />
        )}
      </div>
    </div>
  );
}

function RecoveryCard({
  clipTranscriptCapabilities,
  handleRecoverTranscript,
  recommendedRecoveryStrategy,
  saving,
}: Pick<SubtitleEditorController, 'clipTranscriptCapabilities' | 'handleRecoverTranscript' | 'recommendedRecoveryStrategy' | 'saving'>) {
  const loadingIcon = <div className="w-3 h-3 border-2 border-primary border-t-transparent animate-spin rounded-full" />;
  const hasRecoveryAction = clipTranscriptCapabilities.can_recover_from_project || clipTranscriptCapabilities.can_transcribe_source;
  const recommendedLabel = recommendedRecoveryStrategy === 'project_slice'
    ? 'Otomatik akış önce proje transcript dilimini dener.'
    : recommendedRecoveryStrategy === 'transcribe_source'
      ? 'Otomatik akış doğrudan kaynak videodan transkripsiyon çıkarır.'
      : null;

  return (
    <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4 space-y-3">
      <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-amber-300">
        <AlertCircle className="w-3.5 h-3.5" />
        Klip transkripti bulunamadi
      </div>
      <p className="text-xs text-muted-foreground">
        Sistem önce otomatik toparlamayı dener. Aşağıdaki butonlar gerektiğinde manuel override içindir.
      </p>
      {recommendedLabel && (
        <p className="text-[11px] text-amber-200/90">{recommendedLabel}</p>
      )}
      <div className="flex flex-wrap gap-2">
        {clipTranscriptCapabilities.can_recover_from_project && (
          <button
            onClick={() => handleRecoverTranscript('project_slice')}
            disabled={saving}
            className="px-4 py-2 rounded-lg bg-foreground/5 border border-border hover:bg-foreground/10 text-[11px] font-mono uppercase transition-all flex items-center gap-2 disabled:opacity-50"
          >
            {saving ? loadingIcon : <Save className="w-3 h-3" />}
            Proje transkriptinden yukle
          </button>
        )}
        {clipTranscriptCapabilities.can_transcribe_source && (
          <button
            onClick={() => handleRecoverTranscript('transcribe_source')}
            disabled={saving}
            className="px-4 py-2 rounded-lg bg-primary/20 border border-primary/40 hover:bg-primary/30 text-[11px] font-mono uppercase transition-all flex items-center gap-2 disabled:opacity-50"
          >
            {saving ? loadingIcon : <Subtitles className="w-3 h-3" />}
            {clipTranscriptCapabilities.has_raw_backup ? 'Ham videodan transkript cikar' : 'Videodan transkript cikar'}
          </button>
        )}
      </div>
      {!hasRecoveryAction && (
        <p className="text-[11px] text-muted-foreground">
          Bu klip icin otomatik kurtarma kaynagi bulunamadi. Gelismis duzenleme veya kaynagi yeniden uretme gerekebilir.
        </p>
      )}
    </div>
  );
}

function ProjectTranscriptCard({
  currentJob,
  handleRecoverProjectTranscript,
  projectTranscriptStatus,
  saving,
}: Pick<SubtitleEditorController, 'currentJob' | 'handleRecoverProjectTranscript' | 'projectTranscriptStatus' | 'saving'>) {
  const loadingIcon = <div className="w-3 h-3 border-2 border-primary border-t-transparent animate-spin rounded-full" />;
  const isPending = projectTranscriptStatus === 'pending';

  return (
    <div className={`rounded-xl border p-4 space-y-3 ${isPending ? 'border-primary/20 bg-primary/5' : 'border-amber-500/20 bg-amber-500/5'}`}>
      <div className={`flex items-center gap-2 text-xs font-mono uppercase tracking-widest ${isPending ? 'text-primary' : 'text-amber-300'}`}>
        {isPending ? <Subtitles className="w-3.5 h-3.5" /> : <AlertCircle className="w-3.5 h-3.5" />}
        {isPending ? 'Transkript hazirlaniyor' : 'Transkript eksik'}
      </div>
      <p className="text-xs text-muted-foreground">
        {isPending
          ? 'Bu proje için transcript hala hazırlanıyor. Hazır olur olmaz editor otomatik yüklenecek.'
          : 'Bu proje için transcript bulunamadı veya son deneme başarısız oldu. Yeniden deneyebilirsiniz.'}
      </p>
      {currentJob && (
        <JobProgressLine currentJob={currentJob} />
      )}
      {!isPending && (
        <button
          onClick={handleRecoverProjectTranscript}
          disabled={saving}
          className="px-4 py-2 rounded-lg bg-foreground/5 border border-border hover:bg-foreground/10 text-[11px] font-mono uppercase transition-all flex items-center gap-2 disabled:opacity-50"
        >
          {saving ? loadingIcon : <RefreshCw className="w-3 h-3" />}
          Transcripti yeniden cikar
        </button>
      )}
    </div>
  );
}

function ClipRecoveryStatusCard({
  clipTranscriptCapabilities,
  clipTranscriptStatus,
  currentJob,
}: Pick<SubtitleEditorController, 'clipTranscriptCapabilities' | 'clipTranscriptStatus' | 'currentJob'>) {
  const isProjectPending = clipTranscriptStatus === 'project_pending';

  return (
    <div className="rounded-xl border border-primary/20 bg-primary/5 p-4 space-y-3">
      <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-primary">
        <Subtitles className="w-3.5 h-3.5" />
        {isProjectPending ? 'Proje transcripti bekleniyor' : 'Klip transcripti toparlaniyor'}
      </div>
      <p className="text-xs text-muted-foreground">
        {isProjectPending
          ? 'Bu klip için önce proje transcriptinin hazır olması gerekiyor.'
          : clipTranscriptCapabilities.has_raw_backup
            ? 'Klip transcripti ham videodan veya metadata diliminden otomatik hazırlanıyor.'
            : 'Klip transcripti videodan otomatik hazırlanıyor.'}
      </p>
      {currentJob && (
        <JobProgressLine currentJob={currentJob} />
      )}
    </div>
  );
}

function JobProgressLine({
  currentJob,
}: Pick<SubtitleEditorController, 'currentJob'>) {
  if (!currentJob) {
    return null;
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-3 text-[11px] font-mono uppercase text-muted-foreground">
        <span>{currentJob.last_message}</span>
        <span>{currentJob.progress}%</span>
      </div>
      <div className="h-1.5 rounded-full bg-foreground/10 overflow-hidden">
        <div
          className="h-full rounded-full bg-primary transition-all duration-300"
          style={{ width: `${Math.max(5, currentJob.progress)}%` }}
        />
      </div>
    </div>
  );
}

function ReburnWarningCard({ message }: { message: string }) {
  return (
    <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4 space-y-2">
      <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-amber-300">
        <AlertCircle className="w-3.5 h-3.5" />
        Reburn uyarisi
      </div>
      <p className="text-xs text-muted-foreground">{message}</p>
    </div>
  );
}

function TranscriptStatus({
  error,
  successMessage,
}: {
  error: string | null;
  successMessage: string | null;
}) {
  return (
    <>
      {error && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-xs text-red-400" role="alert">
          <AlertCircle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}
      {successMessage && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-green-500/10 border border-green-500/20 text-xs text-green-400">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          {successMessage}
        </div>
      )}
    </>
  );
}

function TranscriptList({
  currentTime,
  updateSubtitleText,
  videoRef,
  visibleTranscriptEntries,
}: {
  currentTime: number;
  updateSubtitleText: SubtitleEditorController['updateSubtitleText'];
  videoRef: SubtitleEditorController['videoRef'];
  visibleTranscriptEntries: SubtitleEditorController['visibleTranscriptEntries'];
}) {
  return (
    <div className="max-h-[300px] overflow-y-auto space-y-2 pr-2 custom-scrollbar">
      {visibleTranscriptEntries.map(({ index, segment }) => {
        const isActive = currentTime >= segment.start && currentTime <= segment.end;

        return (
          <div
            key={index}
            role="button"
            tabIndex={0}
            onClick={() => {
              if (videoRef.current) {
                videoRef.current.currentTime = segment.start;
              }
            }}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && videoRef.current) {
                videoRef.current.currentTime = segment.start;
              }
            }}
            className={`flex gap-3 group transition-all duration-300 cursor-pointer ${isActive ? 'scale-[1.02] z-10' : 'opacity-40'}`}
          >
            <div className={`text-[11px] font-mono w-14 pt-3 shrink-0 ${isActive ? 'text-primary font-black' : 'text-muted-foreground'}`}>
              {toTimeStr(segment.start)}
            </div>
            <textarea
              value={segment.text}
              onChange={(event) => updateSubtitleText(index, event.target.value)}
              onClick={(event) => event.stopPropagation()}
              className={`flex-1 bg-foreground/5 border rounded-lg p-2.5 text-sm transition-all outline-none resize-none h-12 ${isActive ? 'border-primary/50 bg-foreground/10' : 'border-border group-hover:border-border'}`}
            />
          </div>
        );
      })}
    </div>
  );
}

function TranscriptActions({
  endTime,
  handleRenderClip,
  handleSave,
  mode,
  saving,
  selectedProjectId,
  startTime,
  transcript,
}: Pick<
  SubtitleEditorController,
  | 'endTime'
  | 'handleRenderClip'
  | 'handleSave'
  | 'mode'
  | 'saving'
  | 'selectedProjectId'
  | 'startTime'
  | 'transcript'
>) {
  const loadingIcon = <div className="w-3 h-3 border-2 border-primary border-t-transparent animate-spin rounded-full" />;

  return (
    <div className="flex gap-2">
      <button
        onClick={handleSave}
        disabled={saving || transcript.length === 0}
        className="px-4 py-2 rounded-lg bg-foreground/5 border border-border hover:bg-foreground/10 text-[11px] font-mono uppercase transition-all flex items-center gap-2 disabled:opacity-50"
      >
        {saving ? loadingIcon : <Save className="w-3 h-3" />}
        {mode === 'clip' ? 'Kaydet + Reburn' : 'Kaydet'}
      </button>
      {mode === 'project' && selectedProjectId && (
        <button
          onClick={handleRenderClip}
          disabled={saving || transcript.length === 0 || endTime <= startTime}
          className="px-4 py-2 rounded-lg bg-primary/20 border border-primary/40 hover:bg-primary/30 text-[11px] font-mono uppercase transition-all flex items-center gap-2 disabled:opacity-50"
        >
          {saving ? loadingIcon : <Scissors className="w-3 h-3" />}
          Aralığı klip olarak üret
        </button>
      )}
    </div>
  );
}
