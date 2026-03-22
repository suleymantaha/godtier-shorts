import { useCallback, useMemo, useRef, useState, type Dispatch, type SetStateAction } from 'react';

import { useAuthRuntimeStore } from '../../auth/runtime';
import { type StyleName, type SubtitleAnimationType } from '../../config/subtitleStyles';
import { useJobStore } from '../../store/useJobStore';
import type {
  Clip,
  ClipTranscriptCapabilities,
  ClipTranscriptStatus,
  Job,
  RenderMetadata,
  Segment,
  TranscriptRecoveryStrategy,
  TranscriptStatus,
} from '../../types';
import {
  EMPTY_CLIP_TRANSCRIPT_CAPABILITIES,
  filterVisibleTranscriptEntries,
  hasSubtitleSelection,
  resolveClipSelectValue,
  resolveSubtitleSelectionKey,
  resolveSubtitleVideoSrc,
  type SubtitleEditorMode,
  type SubtitleProject,
} from './helpers';
import { useSubtitleEditorActions, useSubtitleSelectionActions } from './actions';
import {
  useActiveJobSyncEffect,
  useClipAutoRecoveryEffect,
  usePersistedSubtitleSessionEffect,
  usePersistedSubtitleSessionResumeEffect,
  useSubtitleJobTrackingEffect,
} from './jobs';
import {
  useRangeSelectionResetEffect,
  useStableRangeReady,
  useSubtitlePlayback,
  useSubtitleRangeChangeAction,
  useSuccessMessageTimeout,
  useTranscriptDurationEffect,
} from './playback';
import {
  type ProjectsFetchStatus,
  getReburnWarningMessage,
  type SubtitleSourceState,
  type TranscriptAccessState,
} from './shared';
import { useLockedClipSelectionEffect, useSubtitleSourcesEffect } from './sources';
import { useTranscriptLoader } from './transcriptLoader';

export interface UseSubtitleEditorControllerProps {
  lockedToClip?: boolean;
  targetClip?: Clip | null;
}

export type SubtitleSelectionState = ReturnType<typeof useSubtitleSelectionState>;
export type SubtitleWorkspace = ReturnType<typeof useSubtitleWorkspaceState>;
export type TranscriptLoaderWorkspace = Pick<
  SubtitleWorkspace,
  | 'setAnimationType'
  | 'setClipTranscriptCapabilities'
  | 'setClipTranscriptStatus'
  | 'setClipRenderMetadata'
  | 'setCurrentJobId'
  | 'setDuration'
  | 'setEndTime'
  | 'setError'
  | 'setLoading'
  | 'setProjectTranscriptStatus'
  | 'setRecommendedRecoveryStrategy'
  | 'setStartTime'
  | 'setStyle'
  | 'setTranscriptAccessMessage'
  | 'setTranscriptAccessState'
  | 'transcriptAccessState'
  | 'setTranscript'
>;
export type TranscriptLoadOptions = {
  forceAuthRecovery?: boolean;
};
export type TranscriptLoaderParams = {
  canUseProtectedRequests: boolean;
  fetchJobs: () => Promise<void>;
  mode: SubtitleEditorMode;
  pauseReason: import('../../api/errors').AppErrorCode | null;
  selectionKey: string | null;
  selectedClip: Clip | null;
  selectedProjectId: string | null;
  workspace: TranscriptLoaderWorkspace;
};
export type SubtitleEditorActionWorkspace = Pick<
  SubtitleWorkspace,
  | 'animationType'
  | 'clipTranscriptCapabilities'
  | 'clipTranscriptStatus'
  | 'endTime'
  | 'setAnimationType'
  | 'setCurrentJobId'
  | 'setError'
  | 'setSaving'
  | 'setStyle'
  | 'setSuccessMessage'
  | 'setTranscript'
  | 'startTime'
  | 'style'
  | 'transcript'
>;
export type SubtitleEditorActionParams = {
  fetchJobs: () => Promise<void>;
  markRangeTouched: () => void;
  mode: SubtitleEditorMode;
  selectedClip: Clip | null;
  selectedProjectId: string | null;
  workspace: SubtitleEditorActionWorkspace;
};
export type SubtitleSaveActionParams = {
  animationType: SubtitleAnimationType;
  clipTranscriptCapabilities: ClipTranscriptCapabilities;
  fetchJobs: () => Promise<void>;
  mode: SubtitleEditorMode;
  selectedClip: Clip | null;
  selectedProjectId: string | null;
  setCurrentJobId: Dispatch<SetStateAction<string | null>>;
  setError: Dispatch<SetStateAction<string | null>>;
  setSaving: Dispatch<SetStateAction<boolean>>;
  setSuccessMessage: Dispatch<SetStateAction<string | null>>;
  style: StyleName;
  transcript: Segment[];
};

function useSubtitleSelectionState() {
  const [clips, setClips] = useState<Clip[]>([]);
  const [mode, setMode] = useState<SubtitleEditorMode>('project');
  const [projects, setProjects] = useState<SubtitleProject[]>([]);
  const [projectsError, setProjectsError] = useState<string | null>(null);
  const [projectsStatus, setProjectsStatus] = useState<ProjectsFetchStatus>('good');
  const [sourceMessage, setSourceMessage] = useState<string | null>(null);
  const [sourceState, setSourceState] = useState<SubtitleSourceState>('loading');
  const [selectedClip, setSelectedClip] = useState<Clip | null>(null);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);

  return {
    clips,
    mode,
    projects,
    projectsError,
    projectsStatus,
    sourceMessage,
    sourceState,
    selectedClip,
    selectedProjectId,
    setClips,
    setMode,
    setProjects,
    setProjectsError,
    setProjectsStatus,
    setSourceMessage,
    setSourceState,
    setSelectedClip,
    setSelectedProjectId,
  };
}

function useSubtitleWorkspaceState() {
  const [cacheBust, setCacheBust] = useState(0);
  const [clipTranscriptCapabilities, setClipTranscriptCapabilities] = useState<ClipTranscriptCapabilities>(
    EMPTY_CLIP_TRANSCRIPT_CAPABILITIES,
  );
  const [clipTranscriptStatus, setClipTranscriptStatus] = useState<ClipTranscriptStatus>('needs_recovery');
  const [clipRenderMetadata, setClipRenderMetadata] = useState<RenderMetadata | null>(null);
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [endTime, setEndTime] = useState(60);
  const [error, setError] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [loading, setLoading] = useState(false);
  const [projectTranscriptStatus, setProjectTranscriptStatus] = useState<TranscriptStatus>('ready');
  const [recommendedRecoveryStrategy, setRecommendedRecoveryStrategy] = useState<Exclude<TranscriptRecoveryStrategy, 'auto'> | null>(null);
  const [saving, setSaving] = useState(false);
  const [startTime, setStartTime] = useState(0);
  const [style, setStyle] = useState<StyleName>('HORMOZI');
  const [animationType, setAnimationType] = useState<SubtitleAnimationType>('default');
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [transcriptAccessMessage, setTranscriptAccessMessage] = useState<string | null>(null);
  const [transcriptAccessState, setTranscriptAccessState] = useState<TranscriptAccessState>('idle');
  const [transcript, setTranscript] = useState<Segment[]>([]);
  const videoRef = useRef<HTMLVideoElement>(null);

  return {
    animationType,
    cacheBust,
    clipRenderMetadata,
    clipTranscriptCapabilities,
    clipTranscriptStatus,
    currentJobId,
    currentTime,
    duration,
    endTime,
    error,
    isPlaying,
    loading,
    projectTranscriptStatus,
    recommendedRecoveryStrategy,
    saving,
    setAnimationType,
    setCacheBust,
    setClipRenderMetadata,
    setClipTranscriptCapabilities,
    setClipTranscriptStatus,
    setCurrentJobId,
    setCurrentTime,
    setDuration,
    setEndTime,
    setError,
    setIsPlaying,
    setLoading,
    setProjectTranscriptStatus,
    setRecommendedRecoveryStrategy,
    setSaving,
    setStartTime,
    setStyle,
    setSuccessMessage,
    setTranscript,
    setTranscriptAccessMessage,
    setTranscriptAccessState,
    startTime,
    style,
    successMessage,
    transcript,
    transcriptAccessMessage,
    transcriptAccessState,
    videoRef,
  };
}

function buildSubtitleEditorState({
  currentJob,
  currentJobId,
  currentTime,
  currentVideoState,
  hasSelection,
  lockedToClip,
  rangeReady,
  selectionKey,
  selection,
  visibleTranscriptEntries,
  workspace,
}: {
  currentJob: Job | null;
  currentJobId: string | null;
  currentTime: number;
  currentVideoState: {
    isPlaying: boolean;
    videoRef: SubtitleWorkspace['videoRef'];
    videoSrc: string | undefined;
  };
  hasSelection: boolean;
  lockedToClip: boolean;
  rangeReady: boolean;
  selectionKey: string | null;
  selection: SubtitleSelectionState;
  visibleTranscriptEntries: ReturnType<typeof filterVisibleTranscriptEntries>;
  workspace: SubtitleWorkspace;
}) {
  return {
    animationType: workspace.animationType,
    clipTranscriptCapabilities: workspace.clipTranscriptCapabilities,
    clipTranscriptStatus: workspace.clipTranscriptStatus,
    clipRenderMetadata: workspace.clipRenderMetadata,
    clips: selection.clips,
    currentJob,
    currentJobId,
    currentTime,
    duration: workspace.duration,
    endTime: workspace.endTime,
    error: workspace.error,
    hasSelection,
    isPlaying: currentVideoState.isPlaying,
    loading: workspace.loading,
    lockedToClip,
    mode: selection.mode,
    projects: selection.projects,
    projectsError: selection.projectsError,
    projectsStatus: selection.projectsStatus,
    projectTranscriptStatus: workspace.projectTranscriptStatus,
    rangeReady,
    reburnWarningMessage: getReburnWarningMessage(),
    recommendedRecoveryStrategy: workspace.recommendedRecoveryStrategy,
    resolveClipSelectValue,
    saving: workspace.saving,
    selectedClip: selection.selectedClip,
    selectedProjectId: selection.selectedProjectId,
    selectionKey,
    setCurrentTime: workspace.setCurrentTime,
    setEndTime: workspace.setEndTime,
    setIsPlaying: workspace.setIsPlaying,
    setStartTime: workspace.setStartTime,
    sourceMessage: selection.sourceMessage,
    sourceState: selection.sourceState,
    startTime: workspace.startTime,
    style: workspace.style,
    successMessage: workspace.successMessage,
    transcript: workspace.transcript,
    transcriptAccessMessage: workspace.transcriptAccessMessage,
    transcriptAccessState: workspace.transcriptAccessState,
    videoRef: currentVideoState.videoRef,
    videoSrc: currentVideoState.videoSrc,
    visibleTranscriptEntries,
  };
}

function buildSubtitleEditorHandlers({
  editorActions,
  handleRangeChange,
  loadTranscript,
  playback,
  selectionActions,
}: {
  editorActions: ReturnType<typeof useSubtitleEditorActions>;
  handleRangeChange: (startTime: number, endTime: number) => void;
  loadTranscript: (options?: TranscriptLoadOptions) => Promise<void>;
  playback: ReturnType<typeof useSubtitlePlayback>;
  selectionActions: ReturnType<typeof useSubtitleSelectionActions>;
}) {
  return {
    handleClipSelect: selectionActions.handleClipSelect,
    handleLoadedMetadata: playback.handleLoadedMetadata,
    handleRangeChange,
    handleRecoverProjectTranscript: editorActions.handleRecoverProjectTranscript,
    handleRecoverTranscript: editorActions.handleRecoverTranscript,
    handleRenderClip: editorActions.handleRenderClip,
    handleSave: editorActions.handleSave,
    handleTimeUpdate: playback.handleTimeUpdate,
    reloadTranscript: loadTranscript,
    selectClipMode: selectionActions.selectClipMode,
    selectProjectMode: selectionActions.selectProjectMode,
    setAnimationType: editorActions.setAnimationType,
    setSelectedProjectId: selectionActions.setSelectedProjectId,
    setStyle: editorActions.setStyle,
    togglePlay: playback.togglePlay,
    updateSubtitleText: editorActions.updateSubtitleText,
  };
}

function buildSubtitleEditorController({
  currentTime,
  currentJob,
  currentJobId,
  currentVideoState,
  editorActions,
  handleRangeChange,
  hasSelection,
  loadTranscript,
  lockedToClip,
  playback,
  rangeReady,
  selection,
  selectionActions,
  selectionKey,
  visibleTranscriptEntries,
  workspace,
}: {
  currentTime: number;
  currentJob: Job | null;
  currentJobId: string | null;
  currentVideoState: {
    isPlaying: boolean;
    videoRef: SubtitleWorkspace['videoRef'];
    videoSrc: string | undefined;
  };
  editorActions: ReturnType<typeof useSubtitleEditorActions>;
  handleRangeChange: (startTime: number, endTime: number) => void;
  hasSelection: boolean;
  loadTranscript: (options?: TranscriptLoadOptions) => Promise<void>;
  lockedToClip: boolean;
  playback: ReturnType<typeof useSubtitlePlayback>;
  rangeReady: boolean;
  selection: SubtitleSelectionState;
  selectionActions: ReturnType<typeof useSubtitleSelectionActions>;
  selectionKey: string | null;
  visibleTranscriptEntries: ReturnType<typeof filterVisibleTranscriptEntries>;
  workspace: SubtitleWorkspace;
}) {
  return {
    ...buildSubtitleEditorState({
      currentJob,
      currentJobId,
      currentTime,
      currentVideoState,
      hasSelection,
      lockedToClip,
      rangeReady,
      selection,
      selectionKey,
      visibleTranscriptEntries,
      workspace,
    }),
    ...buildSubtitleEditorHandlers({
      editorActions,
      handleRangeChange,
      loadTranscript,
      playback,
      selectionActions,
    }),
  };
}

function useSubtitleControllerServices({
  canUseProtectedRequests,
  fetchJobs,
  jobs,
  lockedToClip,
  markRangeTouched,
  pauseReason,
  selection,
  workspace,
}: {
  canUseProtectedRequests: boolean;
  fetchJobs: () => Promise<void>;
  jobs: Job[];
  lockedToClip: boolean;
  markRangeTouched: () => void;
  pauseReason: import('../../api/errors').AppErrorCode | null;
  selection: SubtitleSelectionState;
  workspace: SubtitleWorkspace;
}) {
  const selectionKey = useMemo(
    () => resolveSubtitleSelectionKey(selection.mode, selection.selectedProjectId, selection.selectedClip),
    [selection.mode, selection.selectedProjectId, selection.selectedClip],
  );
  const currentJob = useMemo(
    () => workspace.currentJobId ? jobs.find((job) => job.job_id === workspace.currentJobId) ?? null : null,
    [jobs, workspace.currentJobId],
  );
  const hasSelection = hasSubtitleSelection(selection.mode, selection.selectedProjectId, selection.selectedClip);
  const loadTranscript = useTranscriptLoader({
    canUseProtectedRequests,
    fetchJobs,
    mode: selection.mode,
    pauseReason,
    selectionKey,
    selectedClip: selection.selectedClip,
    selectedProjectId: selection.selectedProjectId,
    workspace,
  });
  const playback = useSubtitlePlayback({
    setCurrentTime: workspace.setCurrentTime,
    setDuration: workspace.setDuration,
    setEndTime: workspace.setEndTime,
    videoRef: workspace.videoRef,
  });
  const handleRangeChange = useSubtitleRangeChangeAction({
    endTime: workspace.endTime,
    markRangeTouched,
    setCurrentTime: workspace.setCurrentTime,
    setEndTime: workspace.setEndTime,
    setStartTime: workspace.setStartTime,
    startTime: workspace.startTime,
    videoRef: workspace.videoRef,
  });
  const selectionActions = useSubtitleSelectionActions(lockedToClip, markRangeTouched, selection);
  const editorActions = useSubtitleEditorActions({
    fetchJobs,
    markRangeTouched,
    mode: selection.mode,
    selectedClip: selection.selectedClip,
    selectedProjectId: selection.selectedProjectId,
    workspace,
  });
  const videoState = {
    isPlaying: workspace.isPlaying,
    videoRef: workspace.videoRef,
    videoSrc: resolveSubtitleVideoSrc({
      cacheBust: workspace.cacheBust,
      mode: selection.mode,
      selectedClip: selection.selectedClip,
      selectedProjectId: selection.selectedProjectId,
    }),
  };
  const visibleTranscriptEntries = selection.mode === 'clip'
    ? workspace.transcript.map((segment, index) => ({ index, segment }))
    : filterVisibleTranscriptEntries(workspace.transcript, workspace.startTime, workspace.endTime);
  const rangeReadyCandidate = selection.mode === 'project'
    && workspace.transcriptAccessState === 'ready'
    && workspace.transcript.length > 0
    && workspace.duration > 0;

  return {
    currentJob,
    editorActions,
    handleRangeChange,
    hasSelection,
    loadTranscript,
    playback,
    rangeReadyCandidate,
    selectionActions,
    selectionKey,
    videoState,
    visibleTranscriptEntries,
  };
}

export function useSubtitleEditorController({
  lockedToClip = false,
  targetClip = null,
}: UseSubtitleEditorControllerProps = {}) {
  const canUseProtectedRequests = useAuthRuntimeStore((state) => state.canUseProtectedRequests);
  const pauseReason = useAuthRuntimeStore((state) => state.pauseReason);
  const { fetchJobs, jobs } = useJobStore();
  const selection = useSubtitleSelectionState();
  const workspace = useSubtitleWorkspaceState();
  const rangeTouchedSelectionRef = useRef<string | null>(null);
  const selectionKey = useMemo(
    () => resolveSubtitleSelectionKey(selection.mode, selection.selectedProjectId, selection.selectedClip),
    [selection.mode, selection.selectedProjectId, selection.selectedClip],
  );
  const markRangeTouched = useCallback(() => {
    rangeTouchedSelectionRef.current = selectionKey;
  }, [selectionKey]);
  const services = useSubtitleControllerServices({
    canUseProtectedRequests,
    fetchJobs,
    jobs,
    lockedToClip,
    markRangeTouched,
    pauseReason,
    selection,
    workspace,
  });
  const stableRangeReady = useStableRangeReady({
    rangeReadyCandidate: services.rangeReadyCandidate,
    selectionKey,
  });

  useSubtitleSourcesEffect({
    canUseProtectedRequests,
    fetchJobs,
    pauseReason,
    sourceState: selection.sourceState,
    setClips: selection.setClips,
    setProjects: selection.setProjects,
    setProjectsError: selection.setProjectsError,
    setProjectsStatus: selection.setProjectsStatus,
    setSourceMessage: selection.setSourceMessage,
    setSourceState: selection.setSourceState,
  });
  useLockedClipSelectionEffect({ clips: selection.clips, lockedToClip, selection, targetClip });
  useRangeSelectionResetEffect({
    clearRangeReadySelection: stableRangeReady.clearRangeReadySelection,
    selectionKey,
    setCurrentJobId: workspace.setCurrentJobId,
    setCurrentTime: workspace.setCurrentTime,
    setDuration: workspace.setDuration,
    setEndTime: workspace.setEndTime,
    setError: workspace.setError,
    setStartTime: workspace.setStartTime,
    setSuccessMessage: workspace.setSuccessMessage,
  });
  useSubtitleJobTrackingEffect({
    currentJob: services.currentJob,
    fetchJobs,
    loadTranscript: services.loadTranscript,
    mode: selection.mode,
    selectedClip: selection.selectedClip,
    selectionKey,
    setCacheBust: workspace.setCacheBust,
    setError: workspace.setError,
    setSaving: workspace.setSaving,
    setSuccessMessage: workspace.setSuccessMessage,
  });
  useActiveJobSyncEffect({
    currentJob: services.currentJob,
    currentJobId: workspace.currentJobId,
    fetchJobs,
  });
  usePersistedSubtitleSessionResumeEffect({
    currentJobId: workspace.currentJobId,
    fetchJobs,
    jobs,
    mode: selection.mode,
    selectedClip: selection.selectedClip,
    selectedProjectId: selection.selectedProjectId,
    selectionKey,
    setCurrentJobId: workspace.setCurrentJobId,
  });
  usePersistedSubtitleSessionEffect({
    currentJob: services.currentJob,
    currentJobId: workspace.currentJobId,
    mode: selection.mode,
    selectedClip: selection.selectedClip,
    selectedProjectId: selection.selectedProjectId,
    selectionKey,
  });
  useClipAutoRecoveryEffect({
    clipTranscriptStatus: workspace.clipTranscriptStatus,
    currentJobId: workspace.currentJobId,
    handleRecoverTranscript: services.editorActions.handleRecoverTranscript,
    loading: workspace.loading,
    mode: selection.mode,
    recommendedRecoveryStrategy: workspace.recommendedRecoveryStrategy,
    selectedClip: selection.selectedClip,
    transcriptAccessState: workspace.transcriptAccessState,
    transcript: workspace.transcript,
  });
  useSuccessMessageTimeout(workspace.successMessage, workspace.setSuccessMessage);
  useTranscriptDurationEffect({
    duration: workspace.duration,
    rangeTouchedSelectionRef,
    selectionKey,
    setDuration: workspace.setDuration,
    setEndTime: workspace.setEndTime,
    transcript: workspace.transcript,
  });

  return buildSubtitleEditorController({
    currentTime: workspace.currentTime,
    currentJob: services.currentJob,
    currentJobId: workspace.currentJobId,
    currentVideoState: services.videoState,
    editorActions: services.editorActions,
    handleRangeChange: services.handleRangeChange,
    hasSelection: services.hasSelection,
    loadTranscript: services.loadTranscript,
    lockedToClip,
    playback: services.playback,
    rangeReady: stableRangeReady.rangeReady,
    selection,
    selectionActions: services.selectionActions,
    selectionKey: services.selectionKey,
    visibleTranscriptEntries: services.visibleTranscriptEntries,
    workspace,
  });
}

export type SubtitleEditorController = ReturnType<typeof useSubtitleEditorController>;
