import { useCallback, type Dispatch, type SetStateAction } from 'react';

import { editorApi } from '../../api/client';
import { isStyleName, isSubtitleAnimationType, type StyleName, type SubtitleAnimationType } from '../../config/subtitleStyles';
import { tSafe } from '../../i18n';
import type {
  Clip,
  ClipTranscriptCapabilities,
  ClipTranscriptStatus,
  Segment,
  TranscriptRecoveryStrategy,
} from '../../types';
import {
  replaceTranscriptText,
  selectClipByValue,
} from './helpers';
import { getReburnWarningMessage } from './shared';
import type {
  SubtitleEditorActionParams,
  SubtitleSaveActionParams,
  SubtitleSelectionState,
} from './useSubtitleEditorController';
import { resolveClipProjectId } from './transcriptLoader';

export function useSubtitleSelectionActions(
  lockedToClip: boolean,
  markRangeTouched: () => void,
  selection: SubtitleSelectionState,
) {
  const selectProjectMode = useCallback(() => {
    if (lockedToClip) {
      return;
    }

    selection.setMode('project');
    selection.setSelectedClip(null);
    selection.setSelectedProjectId(null);
  }, [lockedToClip, selection]);

  const selectClipMode = useCallback(() => {
    if (lockedToClip) {
      return;
    }

    selection.setMode('clip');
    selection.setSelectedProjectId(null);
    selection.setSelectedClip(null);
  }, [lockedToClip, selection]);

  const handleClipSelect = useCallback((value: string) => {
    if (lockedToClip) {
      return;
    }

    markRangeTouched();
    selection.setSelectedClip(selectClipByValue(selection.clips, value));
  }, [lockedToClip, markRangeTouched, selection]);

  return {
    handleClipSelect,
    selectClipMode,
    selectProjectMode,
    setSelectedProjectId: selection.setSelectedProjectId,
  };
}

function useSubtitleEditorOptionSetters(
  setAnimationTypeState: Dispatch<SetStateAction<SubtitleAnimationType>>,
  setStyleState: Dispatch<SetStateAction<StyleName>>,
) {
  const setStyle = useCallback((value: string) => {
    setStyleState(isStyleName(value) ? value : 'HORMOZI');
  }, [setStyleState]);
  const setAnimationType = useCallback((value: string) => {
    setAnimationTypeState(isSubtitleAnimationType(value) ? value : 'default');
  }, [setAnimationTypeState]);

  return { setAnimationType, setStyle };
}

function useSubtitleTextUpdater(
  setTranscript: Dispatch<SetStateAction<Segment[]>>,
) {
  return useCallback((index: number, text: string) => {
    setTranscript((currentTranscript) => replaceTranscriptText(currentTranscript, index, text));
  }, [setTranscript]);
}

function shouldConfirmClipReburn(capabilities: ClipTranscriptCapabilities) {
  return !capabilities.has_raw_backup && typeof window !== 'undefined';
}

function useSubtitleSaveAction({
  animationType,
  clipTranscriptCapabilities,
  fetchJobs,
  mode,
  selectedClip,
  selectedProjectId,
  setCurrentJobId,
  setError,
  setSaving,
  setSuccessMessage,
  style,
  transcript,
}: SubtitleSaveActionParams) {
  return useCallback(async () => {
    setError(null);
    setSuccessMessage(null);
    setSaving(true);
    try {
      if (mode === 'project' && selectedProjectId) {
        await editorApi.saveTranscript(transcript, selectedProjectId);
        setSuccessMessage(tSafe('subtitleEditor.transcript.transcriptSaved'));
        setSaving(false);
        return;
      }

      if (mode === 'clip' && selectedClip) {
        const projectId = resolveClipProjectId(selectedClip);
        if (!projectId) {
          setError(tSafe('subtitleEditor.errors.missingProjectContext', { defaultValue: 'Project context could not be found for this clip.' }));
          setSaving(false);
          return;
        }

        if (shouldConfirmClipReburn(clipTranscriptCapabilities)
          && !window.confirm(`${getReburnWarningMessage()}\n\n${tSafe('subtitleEditor.transcript.confirmContinue')}`)) {
          setSaving(false);
          return;
        }
        const response = await editorApi.reburn({
          animation_type: animationType,
          clip_name: selectedClip.name,
          project_id: projectId,
          style_name: style,
          transcript,
        });
        setCurrentJobId(response.job_id ?? null);
        await fetchJobs();
        return;
      }

      setSaving(false);
    } catch (error) {
      setError(error instanceof Error ? error.message : tSafe('subtitleEditor.transcript.saveFailed'));
      setSaving(false);
    }
  }, [
    animationType,
    clipTranscriptCapabilities,
    fetchJobs,
    mode,
    selectedClip,
    selectedProjectId,
    setCurrentJobId,
    setError,
    setSaving,
    setSuccessMessage,
    style,
    transcript,
  ]);
}

function useProjectTranscriptRecoveryAction({
  fetchJobs,
  selectedProjectId,
  setCurrentJobId,
  setError,
  setSaving,
  setSuccessMessage,
}: {
  fetchJobs: () => Promise<void>;
  selectedProjectId: string | null;
  setCurrentJobId: Dispatch<SetStateAction<string | null>>;
  setError: Dispatch<SetStateAction<string | null>>;
  setSaving: Dispatch<SetStateAction<boolean>>;
  setSuccessMessage: Dispatch<SetStateAction<string | null>>;
}) {
  return useCallback(async () => {
    if (!selectedProjectId) {
      return;
    }

    setError(null);
    setSuccessMessage(null);
    setSaving(true);

    try {
      const response = await editorApi.recoverProjectTranscript({ project_id: selectedProjectId });
      setCurrentJobId(response.job_id ?? null);
      if (response.job_id) {
        await fetchJobs();
        return;
      }
      setSaving(false);
    } catch (error) {
      setError(error instanceof Error ? error.message : tSafe('subtitleEditor.transcript.projectRecoverFailed'));
      setSaving(false);
    }
  }, [
    fetchJobs,
    selectedProjectId,
    setCurrentJobId,
    setError,
    setSaving,
    setSuccessMessage,
  ]);
}

function canRunSubtitleRecovery({
  capabilities,
  clipTranscriptStatus,
  strategy,
}: {
  capabilities: ClipTranscriptCapabilities;
  clipTranscriptStatus: ClipTranscriptStatus;
  strategy: TranscriptRecoveryStrategy;
}) {
  if (strategy === 'project_slice') {
    return capabilities.can_recover_from_project;
  }
  if (strategy === 'transcribe_source') {
    return capabilities.can_transcribe_source;
  }
  if (strategy === 'auto') {
    return clipTranscriptStatus === 'needs_recovery' || clipTranscriptStatus === 'failed';
  }
  return true;
}

function resolveRecoveryProjectId(
  capabilities: ClipTranscriptCapabilities,
  selectedClip: Clip,
) {
  return capabilities.resolved_project_id ?? resolveClipProjectId(selectedClip) ?? undefined;
}

function useSubtitleRecoveryAction({
  clipTranscriptCapabilities,
  clipTranscriptStatus,
  fetchJobs,
  selectedClip,
  setCurrentJobId,
  setError,
  setSaving,
  setSuccessMessage,
}: {
  clipTranscriptCapabilities: ClipTranscriptCapabilities;
  clipTranscriptStatus: ClipTranscriptStatus;
  fetchJobs: () => Promise<void>;
  selectedClip: Clip | null;
  setCurrentJobId: Dispatch<SetStateAction<string | null>>;
  setError: Dispatch<SetStateAction<string | null>>;
  setSaving: Dispatch<SetStateAction<boolean>>;
  setSuccessMessage: Dispatch<SetStateAction<string | null>>;
}) {
  return useCallback(async (strategy: TranscriptRecoveryStrategy) => {
    if (!selectedClip) {
      return;
    }

    if (!canRunSubtitleRecovery({
      capabilities: clipTranscriptCapabilities,
      clipTranscriptStatus,
      strategy,
    })) {
      return;
    }

    setError(null);
    setSuccessMessage(null);
    setSaving(true);

    try {
      const projectId = resolveRecoveryProjectId(clipTranscriptCapabilities, selectedClip);
      if (!projectId) {
        throw new Error(tSafe('subtitleEditor.errors.missingProjectContext', { defaultValue: 'Project context could not be found for this clip.' }));
      }

      const response = await editorApi.recoverClipTranscript({
        clip_name: selectedClip.name,
        project_id: projectId,
        strategy,
      });
      setCurrentJobId(response.job_id ?? null);
      if (response.job_id) {
        await fetchJobs();
        return;
      }
      setSaving(false);
    } catch (error) {
      setError(error instanceof Error ? error.message : tSafe('subtitleEditor.transcript.clipRecoverFailed'));
      setSaving(false);
    }
  }, [
    clipTranscriptCapabilities,
    clipTranscriptStatus,
    fetchJobs,
    selectedClip,
    setCurrentJobId,
    setError,
    setSaving,
    setSuccessMessage,
  ]);
}

function useSubtitleRenderAction({
  animationType,
  endTime,
  fetchJobs,
  markRangeTouched,
  selectedProjectId,
  setCurrentJobId,
  setError,
  setSaving,
  setSuccessMessage,
  startTime,
  style,
  transcript,
}: {
  animationType: SubtitleAnimationType;
  endTime: number;
  fetchJobs: () => Promise<void>;
  markRangeTouched: () => void;
  selectedProjectId: string | null;
  setCurrentJobId: Dispatch<SetStateAction<string | null>>;
  setError: Dispatch<SetStateAction<string | null>>;
  setSaving: Dispatch<SetStateAction<boolean>>;
  setSuccessMessage: Dispatch<SetStateAction<string | null>>;
  startTime: number;
  style: StyleName;
  transcript: Segment[];
}) {
  return useCallback(async () => {
    if (!selectedProjectId || endTime <= startTime) {
      return;
    }

    markRangeTouched();
    setError(null);
    setSuccessMessage(null);
    setSaving(true);
    try {
      const response = await editorApi.processManual({
        animation_type: animationType,
        end_time: endTime,
        project_id: selectedProjectId,
        start_time: startTime,
        style_name: style,
        transcript,
      });
      setCurrentJobId(response.job_id);
      await fetchJobs();
    } catch (error) {
      setError(error instanceof Error ? error.message : tSafe('subtitleEditor.transcript.rangeRenderFailed'));
      setSaving(false);
    }
  }, [
    animationType,
    endTime,
    fetchJobs,
    markRangeTouched,
    selectedProjectId,
    setCurrentJobId,
    setError,
    setSaving,
    setSuccessMessage,
    startTime,
    style,
    transcript,
  ]);
}

export function useSubtitleEditorActions({
  fetchJobs,
  markRangeTouched,
  mode,
  selectedClip,
  selectedProjectId,
  workspace,
}: SubtitleEditorActionParams) {
  const {
    animationType,
    clipTranscriptCapabilities,
    clipTranscriptStatus,
    endTime,
    setAnimationType: setAnimationTypeState,
    setCurrentJobId,
    setError,
    setSaving,
    setStyle: setStyleState,
    setSuccessMessage,
    setTranscript,
    startTime,
    style,
    transcript,
  } = workspace;
  const updateSubtitleText = useSubtitleTextUpdater(setTranscript);
  const handleSave = useSubtitleSaveAction({
    animationType,
    clipTranscriptCapabilities,
    fetchJobs,
    mode,
    selectedClip,
    selectedProjectId,
    setCurrentJobId,
    setError,
    setSaving,
    setSuccessMessage,
    style,
    transcript,
  });
  const handleRecoverProjectTranscript = useProjectTranscriptRecoveryAction({
    fetchJobs,
    selectedProjectId,
    setCurrentJobId,
    setError,
    setSaving,
    setSuccessMessage,
  });
  const handleRenderClip = useSubtitleRenderAction({
    animationType,
    endTime,
    fetchJobs,
    markRangeTouched,
    selectedProjectId,
    setCurrentJobId,
    setError,
    setSaving,
    setSuccessMessage,
    startTime,
    style,
    transcript,
  });
  const handleRecoverTranscript = useSubtitleRecoveryAction({
    clipTranscriptCapabilities,
    clipTranscriptStatus,
    fetchJobs,
    selectedClip,
    setCurrentJobId,
    setError,
    setSaving,
    setSuccessMessage,
  });
  const { setAnimationType, setStyle } = useSubtitleEditorOptionSetters(setAnimationTypeState, setStyleState);

  return {
    handleRecoverProjectTranscript,
    handleRecoverTranscript,
    handleRenderClip,
    handleSave,
    setAnimationType,
    setStyle,
    updateSubtitleText,
  };
}
