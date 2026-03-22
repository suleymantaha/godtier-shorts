import type { SubtitleEditorController } from './useSubtitleEditorController';

export type SubtitleEditorContentProps = Pick<
  SubtitleEditorController,
  | 'animationType'
  | 'clipRenderMetadata'
  | 'clipTranscriptCapabilities'
  | 'clipTranscriptStatus'
  | 'currentJob'
  | 'currentJobId'
  | 'duration'
  | 'endTime'
  | 'handleLoadedMetadata'
  | 'handleRangeChange'
  | 'handleRecoverProjectTranscript'
  | 'handleRecoverTranscript'
  | 'handleRenderClip'
  | 'reloadTranscript'
  | 'handleSave'
  | 'handleTimeUpdate'
  | 'isPlaying'
  | 'lockedToClip'
  | 'loading'
  | 'mode'
  | 'projectTranscriptStatus'
  | 'rangeReady'
  | 'reburnWarningMessage'
  | 'recommendedRecoveryStrategy'
  | 'saving'
  | 'selectedClip'
  | 'setAnimationType'
  | 'setEndTime'
  | 'setIsPlaying'
  | 'setStartTime'
  | 'setStyle'
  | 'style'
  | 'successMessage'
  | 'togglePlay'
  | 'transcript'
  | 'transcriptAccessMessage'
  | 'transcriptAccessState'
  | 'updateSubtitleText'
  | 'videoRef'
  | 'videoSrc'
  | 'visibleTranscriptEntries'
> & {
  currentTime: number;
  error: string | null;
  selectedProjectId: string | null;
  startTime: number;
};

export type SubtitleEditorPreviewStackProps = {
  clipRenderMetadata: SubtitleEditorController['clipRenderMetadata'];
  currentJob: SubtitleEditorController['currentJob'];
  currentJobId: SubtitleEditorController['currentJobId'];
  duration: number;
  endTime: number;
  handleLoadedMetadata: SubtitleEditorController['handleLoadedMetadata'];
  handleRangeChange: SubtitleEditorController['handleRangeChange'];
  handleTimeUpdate: SubtitleEditorController['handleTimeUpdate'];
  isPlaying: boolean;
  mode: SubtitleEditorController['mode'];
  rangeReady: boolean;
  selectedClip: SubtitleEditorController['selectedClip'];
  setIsPlaying: SubtitleEditorController['setIsPlaying'];
  startTime: number;
  togglePlay: SubtitleEditorController['togglePlay'];
  transcriptCount: number;
  videoRef: SubtitleEditorController['videoRef'];
  videoSrc: SubtitleEditorController['videoSrc'];
  visibleCount: number;
};

export type TranscriptCardProps = Pick<
  SubtitleEditorController,
  | 'animationType'
  | 'clipTranscriptCapabilities'
  | 'clipTranscriptStatus'
  | 'currentJob'
  | 'currentTime'
  | 'endTime'
  | 'handleRecoverProjectTranscript'
  | 'handleRecoverTranscript'
  | 'handleRenderClip'
  | 'reloadTranscript'
  | 'handleSave'
  | 'lockedToClip'
  | 'loading'
  | 'mode'
  | 'projectTranscriptStatus'
  | 'reburnWarningMessage'
  | 'recommendedRecoveryStrategy'
  | 'saving'
  | 'selectedClip'
  | 'setAnimationType'
  | 'setStyle'
  | 'style'
  | 'transcript'
  | 'transcriptAccessMessage'
  | 'transcriptAccessState'
  | 'updateSubtitleText'
  | 'videoRef'
  | 'visibleTranscriptEntries'
> & {
  error: string | null;
  selectedProjectId: string | null;
  startTime: number;
  successMessage: string | null;
};

export type SelectionCardProps = Pick<
  SubtitleEditorController,
  | 'clips'
  | 'handleClipSelect'
  | 'mode'
  | 'projects'
  | 'projectsError'
  | 'projectsStatus'
  | 'sourceMessage'
  | 'sourceState'
  | 'resolveClipSelectValue'
  | 'selectClipMode'
  | 'selectProjectMode'
  | 'selectedClip'
  | 'selectedProjectId'
  | 'setSelectedProjectId'
>;
