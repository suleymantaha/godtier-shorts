import { AlertCircle, CheckCircle2, Film, RefreshCw, Save, Scissors, Subtitles } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { toTimeStr } from '../../utils/time';
import { Select } from '../ui/Select';
import { getSubtitleAnimationOptions, getSubtitleStyleOptions } from './helpers';
import type { TranscriptCardProps } from './sectionTypes';
import type { SubtitleEditorController } from './useSubtitleEditorController';

const CLIP_PENDING_STATUSES = new Set(['project_pending', 'recovering']);
const CLIP_RECOVERY_REQUIRED_STATUSES = new Set(['needs_recovery', 'failed']);

function resolveTranscriptCardState({
  clipTranscriptCapabilities,
  clipTranscriptStatus,
  loading,
  mode,
  projectTranscriptStatus,
  transcriptAccessState,
  transcript,
}: Pick<
  TranscriptCardProps,
  'clipTranscriptCapabilities' | 'clipTranscriptStatus' | 'loading' | 'mode' | 'projectTranscriptStatus' | 'transcript' | 'transcriptAccessState'
>) {
  const hasTranscript = transcript.length > 0;
  const isAccessBlocked = !loading && !hasTranscript && transcriptAccessState === 'auth_blocked';
  const isMismatch = !loading && !hasTranscript && transcriptAccessState === 'mismatch';
  const isEmptyAndReady = !loading && !hasTranscript && transcriptAccessState === 'ready';
  const isClipMode = mode === 'clip';
  const isProjectMode = mode === 'project';
  const isClipPending = CLIP_PENDING_STATUSES.has(clipTranscriptStatus);
  const needsClipRecovery = CLIP_RECOVERY_REQUIRED_STATUSES.has(clipTranscriptStatus);
  const isProjectTranscriptBlocked = projectTranscriptStatus === 'pending' || projectTranscriptStatus === 'failed';

  return {
    showAccessBlockedCard: isAccessBlocked,
    showClipPendingCard: isClipMode && isEmptyAndReady && isClipPending,
    showMismatchCard: isClipMode && isMismatch,
    showProjectTranscriptCard: isProjectMode && isEmptyAndReady && isProjectTranscriptBlocked,
    showReburnWarning: isClipMode && hasTranscript && !clipTranscriptCapabilities.has_raw_backup,
    showRecoveryCard: isClipMode && isEmptyAndReady && needsClipRecovery,
  };
}

function TranscriptAccessBlockedCard({ message }: { message: string | null }) {
  const { t } = useTranslation();

  return (
    <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4 space-y-2">
      <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-amber-300">
        <AlertCircle className="w-3.5 h-3.5" />
        {t('subtitleEditor.transcript.accessPending')}
      </div>
      <p className="text-xs text-muted-foreground">
        {message ?? t('subtitleEditor.transcript.accessPendingFallback')}
      </p>
    </div>
  );
}

function TranscriptMismatchCard({
  message,
  reloadTranscript,
  saving,
}: {
  message: string | null;
  reloadTranscript: SubtitleEditorController['reloadTranscript'];
  saving: boolean;
}) {
  const { t } = useTranslation();

  return (
    <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4 space-y-3">
      <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-amber-300">
        <AlertCircle className="w-3.5 h-3.5" />
        {t('subtitleEditor.transcript.mismatchTitle')}
      </div>
      <p className="text-xs text-muted-foreground">
        {message ?? t('subtitleEditor.transcript.mismatchFallback')}
      </p>
      <button
        onClick={() => void reloadTranscript()}
        disabled={saving}
        className="px-4 py-2 rounded-lg bg-foreground/5 border border-border hover:bg-foreground/10 text-[11px] font-mono uppercase transition-all flex items-center gap-2 disabled:opacity-50"
      >
        <RefreshCw className="w-3 h-3" />
        {t('subtitleEditor.transcript.reload')}
      </button>
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
  const { t } = useTranslation();
  const loadingIcon = <div className="w-3 h-3 border-2 border-primary border-t-transparent animate-spin rounded-full" />;

  return (
    <div className="flex gap-2">
      <button
        onClick={handleSave}
        disabled={saving || transcript.length === 0}
        className="px-4 py-2 rounded-lg bg-foreground/5 border border-border hover:bg-foreground/10 text-[11px] font-mono uppercase transition-all flex items-center gap-2 disabled:opacity-50"
      >
        {saving ? loadingIcon : <Save className="w-3 h-3" />}
        {mode === 'clip' ? t('subtitleEditor.transcript.saveAndReburn') : t('subtitleEditor.transcript.save')}
      </button>
      {mode === 'project' && selectedProjectId && (
        <button
          onClick={handleRenderClip}
          disabled={saving || transcript.length === 0 || endTime <= startTime}
          className="px-4 py-2 rounded-lg bg-primary/20 border border-primary/40 hover:bg-primary/30 text-[11px] font-mono uppercase transition-all flex items-center gap-2 disabled:opacity-50"
        >
          {saving ? loadingIcon : <Scissors className="w-3 h-3" />}
          {t('subtitleEditor.transcript.renderRange')}
        </button>
      )}
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
  const { t } = useTranslation();
  const showBlockingLoadingState = loading && transcript.length === 0;

  return (
    <div className="flex items-center justify-between gap-4 flex-wrap">
      <div className="space-y-1">
        <h3 className="text-sm font-bold uppercase tracking-[0.2em] flex items-center gap-2">
          <Film className="w-4 h-4 text-primary" />
          {showBlockingLoadingState
            ? t('common.labels.loading')
            : t('subtitleEditor.transcript.title', { total: transcript.length, visible: visibleCount })}
        </h3>
        {lockedToClip && selectedClip && (
          <p className="text-[11px] font-mono uppercase tracking-widest text-muted-foreground">
            {t('subtitleEditor.transcript.focusedClip', { name: selectedClip.name })}
          </p>
        )}
      </div>
      <div className="flex items-center gap-3">
        <Select
          value={style}
          onChange={setStyle}
          options={getSubtitleStyleOptions()}
          className="w-40 text-xs"
        />
        <Select
          value={animationType}
          onChange={setAnimationType}
          options={getSubtitleAnimationOptions()}
          className="w-40 text-xs"
        />
        {!showBlockingLoadingState && (
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

function RecoveryCard({
  clipTranscriptCapabilities,
  handleRecoverTranscript,
  recommendedRecoveryStrategy,
  saving,
}: Pick<SubtitleEditorController, 'clipTranscriptCapabilities' | 'handleRecoverTranscript' | 'recommendedRecoveryStrategy' | 'saving'>) {
  const { t } = useTranslation();
  const loadingIcon = <div className="w-3 h-3 border-2 border-primary border-t-transparent animate-spin rounded-full" />;
  const hasRecoveryAction = clipTranscriptCapabilities.can_recover_from_project || clipTranscriptCapabilities.can_transcribe_source;
  const recommendedLabel = recommendedRecoveryStrategy === 'project_slice'
    ? t('subtitleEditor.transcript.recommendedProjectSlice')
    : recommendedRecoveryStrategy === 'transcribe_source'
      ? t('subtitleEditor.transcript.recommendedSource')
      : null;

  return (
    <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4 space-y-3">
      <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-amber-300">
        <AlertCircle className="w-3.5 h-3.5" />
        {t('subtitleEditor.transcript.recoveryTitle')}
      </div>
      <p className="text-xs text-muted-foreground">
        {t('subtitleEditor.transcript.recoveryDescription')}
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
            {t('subtitleEditor.transcript.recoveryProjectSlice')}
          </button>
        )}
        {clipTranscriptCapabilities.can_transcribe_source && (
          <button
            onClick={() => handleRecoverTranscript('transcribe_source')}
            disabled={saving}
            className="px-4 py-2 rounded-lg bg-primary/20 border border-primary/40 hover:bg-primary/30 text-[11px] font-mono uppercase transition-all flex items-center gap-2 disabled:opacity-50"
          >
            {saving ? loadingIcon : <Subtitles className="w-3 h-3" />}
            {clipTranscriptCapabilities.has_raw_backup
              ? t('subtitleEditor.transcript.recoverySourceRaw')
              : t('subtitleEditor.transcript.recoverySourceVideo')}
          </button>
        )}
      </div>
      {!hasRecoveryAction && (
        <p className="text-[11px] text-muted-foreground">
          {t('subtitleEditor.transcript.recoveryUnavailable')}
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
  const { t } = useTranslation();
  const loadingIcon = <div className="w-3 h-3 border-2 border-primary border-t-transparent animate-spin rounded-full" />;
  const isPending = projectTranscriptStatus === 'pending';

  return (
    <div className={`rounded-xl border p-4 space-y-3 ${isPending ? 'border-primary/20 bg-primary/5' : 'border-amber-500/20 bg-amber-500/5'}`}>
      <div className={`flex items-center gap-2 text-xs font-mono uppercase tracking-widest ${isPending ? 'text-primary' : 'text-amber-300'}`}>
        {isPending ? <Subtitles className="w-3.5 h-3.5" /> : <AlertCircle className="w-3.5 h-3.5" />}
        {isPending ? t('subtitleEditor.transcript.projectPendingTitle') : t('subtitleEditor.transcript.projectMissingTitle')}
      </div>
      <p className="text-xs text-muted-foreground">
        {isPending
          ? t('subtitleEditor.transcript.projectPendingDescription')
          : t('subtitleEditor.transcript.projectMissingDescription')}
      </p>
      {currentJob && <JobProgressLine currentJob={currentJob} />}
      {!isPending && (
        <button
          onClick={handleRecoverProjectTranscript}
          disabled={saving}
          className="px-4 py-2 rounded-lg bg-foreground/5 border border-border hover:bg-foreground/10 text-[11px] font-mono uppercase transition-all flex items-center gap-2 disabled:opacity-50"
        >
          {saving ? loadingIcon : <RefreshCw className="w-3 h-3" />}
          {t('subtitleEditor.transcript.projectRetry')}
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
  const { t } = useTranslation();
  const isProjectPending = clipTranscriptStatus === 'project_pending';

  return (
    <div className="rounded-xl border border-primary/20 bg-primary/5 p-4 space-y-3">
      <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-primary">
        <Subtitles className="w-3.5 h-3.5" />
        {isProjectPending ? t('subtitleEditor.transcript.clipPendingProject') : t('subtitleEditor.transcript.clipPendingRecovery')}
      </div>
      <p className="text-xs text-muted-foreground">
        {isProjectPending
          ? t('subtitleEditor.transcript.clipPendingProjectDescription')
          : clipTranscriptCapabilities.has_raw_backup
            ? t('subtitleEditor.transcript.clipPendingRecoveryDescriptionRaw')
            : t('subtitleEditor.transcript.clipPendingRecoveryDescriptionVideo')}
      </p>
      {currentJob && <JobProgressLine currentJob={currentJob} />}
    </div>
  );
}

function ReburnWarningCard({ message }: { message: string }) {
  const { t } = useTranslation();

  return (
    <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4 space-y-2">
      <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-amber-300">
        <AlertCircle className="w-3.5 h-3.5" />
        {t('subtitleEditor.transcript.reburnWarningTitle')}
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

export function TranscriptCard(props: TranscriptCardProps) {
  const cardState = resolveTranscriptCardState(props);

  return (
    <div className="glass-card p-5 space-y-4">
      <TranscriptHeader
        animationType={props.animationType}
        endTime={props.endTime}
        handleRenderClip={props.handleRenderClip}
        handleSave={props.handleSave}
        lockedToClip={props.lockedToClip}
        loading={props.loading}
        mode={props.mode}
        saving={props.saving}
        selectedClip={props.selectedClip}
        selectedProjectId={props.selectedProjectId}
        setAnimationType={props.setAnimationType}
        setStyle={props.setStyle}
        startTime={props.startTime}
        style={props.style}
        transcript={props.transcript}
        visibleCount={props.visibleTranscriptEntries.length}
      />
      <TranscriptStatus error={props.error} successMessage={props.successMessage} />
      {cardState.showAccessBlockedCard && (
        <TranscriptAccessBlockedCard message={props.transcriptAccessMessage} />
      )}
      {cardState.showProjectTranscriptCard && (
        <ProjectTranscriptCard
          currentJob={props.currentJob}
          handleRecoverProjectTranscript={props.handleRecoverProjectTranscript}
          projectTranscriptStatus={props.projectTranscriptStatus}
          saving={props.saving}
        />
      )}
      {cardState.showMismatchCard && (
        <TranscriptMismatchCard
          message={props.transcriptAccessMessage}
          reloadTranscript={props.reloadTranscript}
          saving={props.saving}
        />
      )}
      {cardState.showClipPendingCard && (
        <ClipRecoveryStatusCard
          clipTranscriptCapabilities={props.clipTranscriptCapabilities}
          clipTranscriptStatus={props.clipTranscriptStatus}
          currentJob={props.currentJob}
        />
      )}
      {cardState.showRecoveryCard && (
        <RecoveryCard
          clipTranscriptCapabilities={props.clipTranscriptCapabilities}
          handleRecoverTranscript={props.handleRecoverTranscript}
          recommendedRecoveryStrategy={props.recommendedRecoveryStrategy}
          saving={props.saving}
        />
      )}
      {cardState.showReburnWarning && (
        <ReburnWarningCard message={props.reburnWarningMessage} />
      )}
      <TranscriptList
        currentTime={props.currentTime}
        updateSubtitleText={props.updateSubtitleText}
        videoRef={props.videoRef}
        visibleTranscriptEntries={props.visibleTranscriptEntries}
      />
    </div>
  );
}
