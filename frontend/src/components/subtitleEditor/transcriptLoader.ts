import { useCallback, useEffect, useMemo } from 'react';

import { clipsApi, editorApi } from '../../api/client';
import { isAppError, type AppErrorCode } from '../../api/errors';
import { isStyleName, isSubtitleAnimationType } from '../../config/subtitleStyles';
import { tSafe } from '../../i18n';
import type {
  Clip,
  ClipTranscriptResponse,
  ProjectTranscriptResponse,
  RenderMetadata,
  Segment,
  TranscriptStatus,
  ClipTranscriptStatus,
} from '../../types';
import { normalizeTranscript } from '../../utils/transcript';
import { EMPTY_CLIP_TRANSCRIPT_CAPABILITIES, hasSubtitleSelection } from './helpers';
import {
  AUTH_BLOCKING_CODES,
  AUTH_BOOTSTRAP_RECOVERY_MS,
  TRUSTED_CLIP_TRANSCRIPT_RETRY_ATTEMPTS,
  TrustedReadyClipMismatchError,
  getTrustedClipTranscriptMismatchMessage,
  normalizeCapabilities,
} from './shared';
import type { TranscriptLoaderParams, TranscriptLoaderWorkspace } from './useSubtitleEditorController';

type TranscriptLoaderMutationWorkspace = Omit<TranscriptLoaderWorkspace, 'transcriptAccessState'>;

function resolveTranscriptAccessBlockedMessage(pauseReason: AppErrorCode | null): string {
  if (pauseReason === 'token_expired') {
    return tSafe('auth.notices.tokenExpired');
  }
  if (pauseReason === 'unauthorized') {
    return tSafe('auth.notices.backendSessionUnavailable');
  }
  if (pauseReason === 'forbidden') {
    return tSafe('auth.notices.accessPermissionRequired');
  }
  if (pauseReason === 'network_offline' || pauseReason === 'auth_revalidation_required') {
    return tSafe('auth.notices.protectedOffline');
  }
  return tSafe('subtitleEditor.transcript.accessPendingFallback');
}

function resolveProjectTranscriptStatus(
  response: ProjectTranscriptResponse,
  transcript: Segment[],
): TranscriptStatus {
  if (response.transcript_status) {
    return response.transcript_status;
  }
  return transcript.length > 0 ? 'ready' : 'failed';
}

function resolveClipTranscriptStatus(
  response: ClipTranscriptResponse,
  transcript: Segment[],
): ClipTranscriptStatus {
  if (response.transcript_status) {
    return response.transcript_status;
  }
  return transcript.length > 0 ? 'ready' : 'needs_recovery';
}

function resetClipTranscriptWorkspace(workspace: TranscriptLoaderMutationWorkspace) {
  workspace.setClipTranscriptCapabilities(EMPTY_CLIP_TRANSCRIPT_CAPABILITIES);
  workspace.setClipTranscriptStatus('needs_recovery');
  workspace.setClipRenderMetadata(null);
  workspace.setRecommendedRecoveryStrategy(null);
}

function clearTranscriptWorkspace(workspace: TranscriptLoaderMutationWorkspace) {
  resetClipTranscriptWorkspace(workspace);
  workspace.setCurrentJobId(null);
  workspace.setProjectTranscriptStatus('ready');
  workspace.setTranscriptAccessMessage(null);
  workspace.setTranscriptAccessState('idle');
  workspace.setTranscript([]);
}

function isTrustedReadyClip(selectedClip: Clip | null): boolean {
  return selectedClip?.transcript_status === 'ready';
}

function handleTrustedReadyClipMismatch(
  workspace: TranscriptLoaderMutationWorkspace,
  selectedClip: Clip | null,
  error: unknown,
) {
  workspace.setError(null);
  workspace.setClipTranscriptCapabilities(EMPTY_CLIP_TRANSCRIPT_CAPABILITIES);
  workspace.setClipTranscriptStatus(selectedClip?.transcript_status ?? 'ready');
  workspace.setClipRenderMetadata(null);
  workspace.setCurrentJobId(null);
  workspace.setProjectTranscriptStatus('ready');
  workspace.setRecommendedRecoveryStrategy(null);
  const mismatchMessage = getTrustedClipTranscriptMismatchMessage();
  workspace.setTranscriptAccessMessage(
    error instanceof Error && error.message !== mismatchMessage
      ? `${mismatchMessage} ${error.message}`
      : mismatchMessage,
  );
  workspace.setTranscriptAccessState('mismatch');
  workspace.setTranscript([]);
}

function handleTranscriptLoadFailure(
  workspace: TranscriptLoaderMutationWorkspace,
  error: unknown,
  options?: { selectedClip?: Clip | null },
) {
  if (isAppError(error) && AUTH_BLOCKING_CODES.has(error.code)) {
    workspace.setError(error.message);
    workspace.setTranscriptAccessMessage(resolveTranscriptAccessBlockedMessage(error.code));
    workspace.setTranscriptAccessState('auth_blocked');
    workspace.setTranscript([]);
    return;
  }

  if (
    isTrustedReadyClip(options?.selectedClip ?? null)
    || error instanceof TrustedReadyClipMismatchError
  ) {
    handleTrustedReadyClipMismatch(workspace, options?.selectedClip ?? null, error);
    return;
  }

  workspace.setError(error instanceof Error ? error.message : tSafe('subtitleEditor.transcript.loadFailed'));
  workspace.setClipTranscriptCapabilities(EMPTY_CLIP_TRANSCRIPT_CAPABILITIES);
  workspace.setClipTranscriptStatus('failed');
  workspace.setClipRenderMetadata(null);
  workspace.setCurrentJobId(null);
  workspace.setProjectTranscriptStatus('failed');
  workspace.setRecommendedRecoveryStrategy(null);
  workspace.setTranscriptAccessMessage(null);
  workspace.setTranscriptAccessState('ready');
  workspace.setTranscript([]);
}

export function resolveClipProjectId(selectedClip: Clip | null): string | null {
  if (!selectedClip) {
    return null;
  }

  if (selectedClip.resolved_project_id && selectedClip.resolved_project_id !== 'legacy') {
    return selectedClip.resolved_project_id;
  }

  if (!selectedClip.project || selectedClip.project === 'legacy') {
    return null;
  }

  return selectedClip.project;
}

function applyClipRenderMetadataPreferences(
  workspace: TranscriptLoaderMutationWorkspace,
  renderMetadata: RenderMetadata | null | undefined,
) {
  if (renderMetadata?.style_name && isStyleName(renderMetadata.style_name)) {
    workspace.setStyle(renderMetadata.style_name);
  }
  if (renderMetadata?.animation_type && isSubtitleAnimationType(renderMetadata.animation_type)) {
    workspace.setAnimationType(renderMetadata.animation_type);
  }
}

async function loadProjectTranscriptSelection(
  fetchJobs: () => Promise<void>,
  selectedProjectId: string,
  workspace: TranscriptLoaderMutationWorkspace,
) {
  resetClipTranscriptWorkspace(workspace);

  const response = await editorApi.getTranscript(selectedProjectId) as ProjectTranscriptResponse;
  const nextTranscript = normalizeTranscript(response);
  const nextStatus = resolveProjectTranscriptStatus(response, nextTranscript);

  workspace.setProjectTranscriptStatus(nextStatus);
  workspace.setCurrentJobId(response.active_job_id ?? null);
  workspace.setTranscript(nextTranscript);
  workspace.setError(nextStatus === 'failed' ? response.last_error ?? null : null);

  if (response.active_job_id) {
    await fetchJobs();
  }
}

async function loadClipTranscriptSelection(
  fetchJobs: () => Promise<void>,
  selectedClip: Clip,
  workspace: TranscriptLoaderMutationWorkspace,
) {
  const projectId = resolveClipProjectId(selectedClip);
  if (!projectId) {
    throw new Error(tSafe('subtitleEditor.errors.missingProjectContext', { defaultValue: 'Project context could not be found for this clip.' }));
  }

  const response = await clipsApi.getTranscript(selectedClip.name, projectId);
  const nextTranscript = normalizeTranscript(response);
  const nextStatus = resolveClipTranscriptStatus(response, nextTranscript);
  const renderMetadata = response.render_metadata;

  if (isTrustedReadyClip(selectedClip) && nextTranscript.length === 0 && nextStatus !== 'ready') {
    throw new TrustedReadyClipMismatchError();
  }

  workspace.setClipTranscriptCapabilities(normalizeCapabilities(response.capabilities));
  workspace.setClipTranscriptStatus(nextStatus);
  workspace.setClipRenderMetadata(renderMetadata ?? null);
  workspace.setProjectTranscriptStatus('ready');
  workspace.setRecommendedRecoveryStrategy(response.recommended_strategy ?? null);
  workspace.setCurrentJobId(response.active_job_id ?? null);
  workspace.setTranscript(nextTranscript);
  applyClipRenderMetadataPreferences(workspace, renderMetadata);
  workspace.setError(nextStatus === 'failed' ? response.last_error ?? null : null);

  if (response.active_job_id) {
    await fetchJobs();
  }
}

function useTranscriptLoaderWorkspace(workspace: TranscriptLoaderWorkspace) {
  const {
    setAnimationType,
    setClipTranscriptCapabilities,
    setClipTranscriptStatus,
    setClipRenderMetadata,
    setCurrentJobId,
    setDuration,
    setEndTime,
    setError,
    setLoading,
    setProjectTranscriptStatus,
    setRecommendedRecoveryStrategy,
    setStartTime,
    setStyle,
    setTranscriptAccessMessage,
    setTranscriptAccessState,
    setTranscript,
  } = workspace;

  return useMemo<TranscriptLoaderMutationWorkspace>(() => ({
    setAnimationType,
    setClipTranscriptCapabilities,
    setClipTranscriptStatus,
    setClipRenderMetadata,
    setCurrentJobId,
    setDuration,
    setEndTime,
    setError,
    setLoading,
    setProjectTranscriptStatus,
    setRecommendedRecoveryStrategy,
    setStartTime,
    setStyle,
    setTranscriptAccessMessage,
    setTranscriptAccessState,
    setTranscript,
  }), [
    setAnimationType,
    setClipTranscriptCapabilities,
    setClipTranscriptStatus,
    setClipRenderMetadata,
    setCurrentJobId,
    setDuration,
    setEndTime,
    setError,
    setLoading,
    setProjectTranscriptStatus,
    setRecommendedRecoveryStrategy,
    setStartTime,
    setStyle,
    setTranscriptAccessMessage,
    setTranscriptAccessState,
    setTranscript,
  ]);
}

function useTranscriptSelectionSyncEffect({
  canUseProtectedRequests,
  loadTranscript,
  loaderWorkspace,
  selectionKey,
  mode,
  pauseReason,
  selectedClip,
  selectedProjectId,
}: {
  canUseProtectedRequests: boolean;
  loadTranscript: (options?: { forceAuthRecovery?: boolean }) => Promise<void>;
  loaderWorkspace: TranscriptLoaderMutationWorkspace;
  selectionKey: string | null;
  mode: 'project' | 'clip';
  pauseReason: AppErrorCode | null;
  selectedClip: Clip | null;
  selectedProjectId: string | null;
}) {
  const { setTranscriptAccessMessage, setTranscriptAccessState } = loaderWorkspace;

  useEffect(() => {
    if (!canUseProtectedRequests) {
      if (hasSubtitleSelection(mode, selectedProjectId, selectedClip)) {
        setTranscriptAccessState(pauseReason ? 'auth_blocked' : 'loading');
        setTranscriptAccessMessage(pauseReason ? resolveTranscriptAccessBlockedMessage(pauseReason) : null);
      }
      return;
    }

    if (hasSubtitleSelection(mode, selectedProjectId, selectedClip)) {
      void loadTranscript();
      return;
    }

    clearTranscriptWorkspace(loaderWorkspace);
  }, [
    canUseProtectedRequests,
    loadTranscript,
    loaderWorkspace,
    mode,
    pauseReason,
    selectedClip,
    selectedProjectId,
    selectionKey,
    setTranscriptAccessMessage,
    setTranscriptAccessState,
  ]);
}

export function useTranscriptLoader({
  canUseProtectedRequests,
  fetchJobs,
  mode,
  pauseReason,
  selectionKey,
  selectedClip,
  selectedProjectId,
  workspace,
}: TranscriptLoaderParams) {
  const {
    setError,
    setLoading,
    setTranscriptAccessMessage,
    setTranscriptAccessState,
    transcriptAccessState,
  } = workspace;
  const loaderWorkspace = useTranscriptLoaderWorkspace(workspace);

  const loadTranscript = useCallback(async (options?: { forceAuthRecovery?: boolean }) => {
    if (!canUseProtectedRequests && !options?.forceAuthRecovery) {
      setTranscriptAccessState(pauseReason ? 'auth_blocked' : 'loading');
      setTranscriptAccessMessage(pauseReason ? resolveTranscriptAccessBlockedMessage(pauseReason) : null);
      return;
    }

    setError(null);
    setLoading(true);
    setTranscriptAccessMessage(null);
    setTranscriptAccessState('loading');
    try {
      if (mode === 'project' && selectedProjectId) {
        await loadProjectTranscriptSelection(fetchJobs, selectedProjectId, loaderWorkspace);
        setTranscriptAccessState('ready');
        return;
      }

      if (mode === 'clip' && selectedClip) {
        const maxAttempts = isTrustedReadyClip(selectedClip) ? TRUSTED_CLIP_TRANSCRIPT_RETRY_ATTEMPTS : 1;
        let lastError: unknown = null;

        for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
          try {
            await loadClipTranscriptSelection(fetchJobs, selectedClip, loaderWorkspace);
            setTranscriptAccessState('ready');
            return;
          } catch (error) {
            if (isAppError(error) && AUTH_BLOCKING_CODES.has(error.code)) {
              throw error;
            }
            lastError = error;
          }
        }

        handleTranscriptLoadFailure(loaderWorkspace, lastError, { selectedClip });
        return;
      }

      clearTranscriptWorkspace(loaderWorkspace);
    } catch (error) {
      handleTranscriptLoadFailure(loaderWorkspace, error, { selectedClip });
    } finally {
      setLoading(false);
    }
  }, [
    canUseProtectedRequests,
    fetchJobs,
    mode,
    pauseReason,
    selectedClip,
    selectedProjectId,
    loaderWorkspace,
    setError,
    setLoading,
    setTranscriptAccessMessage,
    setTranscriptAccessState,
  ]);

  useTranscriptSelectionSyncEffect({
    canUseProtectedRequests,
    loadTranscript,
    mode,
    pauseReason,
    selectionKey,
    selectedClip,
    selectedProjectId,
    loaderWorkspace,
  });

  useEffect(() => {
    if (
      canUseProtectedRequests
      || pauseReason
      || transcriptAccessState !== 'loading'
      || !hasSubtitleSelection(mode, selectedProjectId, selectedClip)
    ) {
      return;
    }

    const recoveryTimer = window.setTimeout(() => {
      void loadTranscript({ forceAuthRecovery: true });
    }, AUTH_BOOTSTRAP_RECOVERY_MS);

    return () => window.clearTimeout(recoveryTimer);
  }, [
    canUseProtectedRequests,
    loadTranscript,
    mode,
    pauseReason,
    selectedClip,
    selectedProjectId,
    transcriptAccessState,
  ]);

  return loadTranscript;
}
