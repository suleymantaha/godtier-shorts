import { useCallback, useEffect, useMemo, useState, type Dispatch, type SetStateAction } from 'react';

import { tSafe } from '../../i18n';
import { socialApi } from '../../api/client';
import type { Clip, PublishJob, ShareDraftContent, SocialAccount, SocialConnectionMode, SocialPlatform } from '../../types';
import {
  clearManagedConnectPending,
  clearSocialOAuthStatusQuery,
  DEFAULT_PLATFORM,
  buildDraftState,
  buildHashtagsFromInput,
  buildPublishTargets,
  getErrorMessage,
  getPublishSuccessMessage,
  hasManagedConnectPending,
  localDraftKey,
  markManagedConnectPending,
  mergeDraftContent,
  nowPlusHourLocal,
  parseLocalDraftBuffer,
  readSocialOAuthStatusFromQuery,
  resolveProjectId,
  summarizePublishErrors,
  toggleSelection,
  type DraftState,
  type ShareComposerContentMap,
} from './helpers';

interface ShareComposerState {
  accounts: SocialAccount[];
  apiKey: string;
  connected: boolean;
  connectionMode: SocialConnectionMode;
  connectUrl: string | null;
  contentByPlatform: ShareComposerContentMap | null;
  draftState: DraftState;
  error: string | null;
  hasDirtyEdits: boolean;
  jobs: PublishJob[];
  loading: boolean;
  managedConnectionPending: boolean;
  publishing: boolean;
  scheduleAt: string;
  selectedAccountIds: string[];
  selectedPlatform: SocialPlatform;
  success: string | null;
}

interface LoadedShareComposerData {
  accounts: SocialAccount[];
  connected: boolean;
  connectionMode: SocialConnectionMode;
  connectUrl: string | null;
  contentByPlatform: ShareComposerContentMap;
  draftState: DraftState;
  jobs: PublishJob[];
}

interface UseShareComposerControllerParams {
  clip: Clip | null;
  open: boolean;
}

function useShareComposerState(): [ShareComposerState, Dispatch<SetStateAction<ShareComposerState>>] {
  return useState<ShareComposerState>({
    accounts: [],
    apiKey: '',
    connected: false,
    connectionMode: 'manual_api_key',
    connectUrl: null,
    contentByPlatform: null,
    draftState: { hasLocalBuffer: false, hasServerDrafts: false },
    error: null,
    hasDirtyEdits: false,
    jobs: [],
    loading: false,
    managedConnectionPending: hasManagedConnectPending(),
    publishing: false,
    scheduleAt: nowPlusHourLocal(),
    selectedAccountIds: [],
    selectedPlatform: DEFAULT_PLATFORM,
    success: null,
  });
}

async function fetchShareComposerData(projectId: string, clipName: string): Promise<LoadedShareComposerData> {
  const [accountResp, prefillResp, jobsResp] = await Promise.all([
    socialApi.getAccounts(),
    socialApi.getPrefill(projectId, clipName),
    socialApi.getPublishJobs(projectId, clipName),
  ]);
  const storageKey = localDraftKey(projectId, clipName);
  const parsedBuffer = parseLocalDraftBuffer(window.localStorage.getItem(storageKey));

  if (parsedBuffer.invalid) {
    window.localStorage.removeItem(storageKey);
  }

  return {
    accounts: accountResp.accounts ?? [],
    connected: accountResp.connected,
    connectionMode: accountResp.connection_mode ?? 'managed',
    connectUrl: accountResp.connect_url ?? null,
    contentByPlatform: mergeDraftContent(prefillResp.platforms, parsedBuffer.buffer),
    draftState: buildDraftState(prefillResp, parsedBuffer.buffer),
    jobs: jobsResp.jobs ?? [],
  };
}

function useShareComposerData({
  clip,
  open,
  projectId,
  setState,
}: UseShareComposerControllerParams & {
  projectId: string | null;
  setState: Dispatch<SetStateAction<ShareComposerState>>;
}) {
  const loadData = useCallback(async () => {
    if (!open || !clip || !projectId) {
      return null;
    }

    setState((current) => ({ ...current, error: null, loading: true }));
    try {
      const loaded = await fetchShareComposerData(projectId, clip.name);
      setState((current) => ({
        ...current,
        ...loaded,
        error: null,
        hasDirtyEdits: false,
      }));
      return loaded;
    } catch (error) {
      setState((current) => ({
        ...current,
        error: getErrorMessage(error, tSafe('shareComposer.errors.loadDataFailed')),
      }));
      return null;
    } finally {
      setState((current) => ({ ...current, loading: false }));
    }
  }, [clip, open, projectId, setState]);

  useEffect(() => {
    if (!open) {
      return;
    }

    void loadData();
  }, [loadData, open]);

  return loadData;
}

function useManagedConnectionSync({
  connectionMode,
  loadData,
  managedConnectionPending,
  open,
  setState,
}: {
  connectionMode: SocialConnectionMode;
  loadData: () => Promise<LoadedShareComposerData | null>;
  managedConnectionPending: boolean;
  open: boolean;
  setState: Dispatch<SetStateAction<ShareComposerState>>;
}) {
  const refreshManagedConnection = useCallback(async () => {
    if (!open || connectionMode !== 'managed' || !managedConnectionPending) {
      return;
    }

    const loaded = await loadData();
    if (!loaded?.connected) {
      return;
    }

    clearManagedConnectPending();
    setState((current) => ({
      ...current,
      managedConnectionPending: false,
      success: tSafe('shareComposer.connection.oauthConnectedSuccess'),
    }));
  }, [connectionMode, loadData, managedConnectionPending, open, setState]);

  useEffect(() => {
    if (!open || connectionMode !== 'managed' || !managedConnectionPending) {
      return;
    }

    const handleFocus = () => {
      void refreshManagedConnection();
    };
    const handleVisibility = () => {
      if (document.visibilityState === 'visible') {
        void refreshManagedConnection();
      }
    };

    window.addEventListener('focus', handleFocus);
    document.addEventListener('visibilitychange', handleVisibility);

    return () => {
      window.removeEventListener('focus', handleFocus);
      document.removeEventListener('visibilitychange', handleVisibility);
    };
  }, [connectionMode, managedConnectionPending, open, refreshManagedConnection]);
}

function useManagedOAuthCallbackSignal({
  connectionMode,
  loadData,
  open,
  setState,
}: {
  connectionMode: SocialConnectionMode;
  loadData: () => Promise<LoadedShareComposerData | null>;
  open: boolean;
  setState: Dispatch<SetStateAction<ShareComposerState>>;
}) {
  useEffect(() => {
    if (!open || connectionMode !== 'managed') {
      return;
    }

    const oauthStatus = readSocialOAuthStatusFromQuery(window.location.search);
    if (!oauthStatus) {
      return;
    }

    clearSocialOAuthStatusQuery();
    clearManagedConnectPending();
    setState((current) => ({
      ...current,
      managedConnectionPending: false,
    }));

    if (oauthStatus === 'error') {
      setState((current) => ({
        ...current,
        error: tSafe('shareComposer.connection.oauthError'),
        success: null,
      }));
      return;
    }

    let cancelled = false;
    void (async () => {
      const loaded = await loadData();
      if (cancelled) {
        return;
      }
      if (loaded?.connected) {
        setState((current) => ({
          ...current,
          error: null,
          managedConnectionPending: false,
          success: tSafe('shareComposer.connection.oauthConnectedSuccess'),
        }));
        return;
      }
      setState((current) => ({
        ...current,
        managedConnectionPending: false,
        error: tSafe('shareComposer.connection.oauthVerifyFailed'),
        success: null,
      }));
    })();

    return () => {
      cancelled = true;
    };
  }, [connectionMode, loadData, open, setState]);
}

function useShareComposerAutosave({
  clip,
  contentByPlatform,
  hasDirtyEdits,
  open,
  projectId,
}: UseShareComposerControllerParams & {
  contentByPlatform: ShareComposerContentMap | null;
  hasDirtyEdits: boolean;
  projectId: string | null;
}) {
  useEffect(() => {
    if (!open || !projectId || !clip || !contentByPlatform || !hasDirtyEdits) {
      return;
    }

    const storageKey = localDraftKey(projectId, clip.name);
    const timer = window.setTimeout(() => {
      window.localStorage.setItem(storageKey, JSON.stringify(contentByPlatform));
      void socialApi.saveDrafts(projectId, clip.name, contentByPlatform).catch(() => {
        // Draft autosave best-effort.
      });
    }, 700);

    return () => window.clearTimeout(timer);
  }, [clip, contentByPlatform, hasDirtyEdits, open, projectId]);
}

function useShareComposerConnectionActions(setState: Dispatch<SetStateAction<ShareComposerState>>) {
  const handleConnect = useCallback(async (apiKey: string) => {
    if (!apiKey.trim()) {
      setState((current) => ({ ...current, error: tSafe('shareComposer.connection.missingApiKey') }));
      return;
    }

    setState((current) => ({ ...current, error: null, loading: true, success: null }));
    try {
      const response = await socialApi.saveCredentials({
        provider: 'postiz',
        api_key: apiKey.trim(),
      });
      setState((current) => ({
        ...current,
        accounts: response.accounts ?? [],
        apiKey: '',
        connected: true,
        success: tSafe('shareComposer.connection.connectedSuccess'),
      }));
    } catch (error) {
      setState((current) => ({
        ...current,
        error: getErrorMessage(error, tSafe('shareComposer.connection.connectFailed')),
      }));
    } finally {
      setState((current) => ({ ...current, loading: false }));
    }
  }, [setState]);

  const handleDisconnect = useCallback(async () => {
    setState((current) => ({ ...current, error: null, loading: true, success: null }));
    try {
      await socialApi.deleteCredentials();
      setState((current) => ({
        ...current,
        accounts: [],
        connected: false,
        selectedAccountIds: [],
        success: tSafe('shareComposer.connection.disconnectedSuccess'),
      }));
    } catch (error) {
      setState((current) => ({
        ...current,
        error: getErrorMessage(error, tSafe('shareComposer.connection.disconnectFailed')),
      }));
    } finally {
      setState((current) => ({ ...current, loading: false }));
    }
  }, [setState]);

  return { handleConnect, handleDisconnect };
}

function useShareComposerJobActions({
  clip,
  projectId,
  setState,
}: UseShareComposerControllerParams & {
  projectId: string | null;
  setState: Dispatch<SetStateAction<ShareComposerState>>;
}) {
  const refreshJobs = useCallback(async () => {
    if (!projectId || !clip) {
      return;
    }

    try {
      const response = await socialApi.getPublishJobs(projectId, clip.name);
      setState((current) => ({ ...current, jobs: response.jobs ?? [] }));
    } catch {
      // optional refresh
    }
  }, [clip, projectId, setState]);

  const handleApprove = useCallback(async (jobId: string) => {
    try {
      await socialApi.approveJob(jobId);
      await refreshJobs();
    } catch (error) {
      setState((current) => ({
        ...current,
        error: getErrorMessage(error, tSafe('shareComposer.errors.approveFailed')),
      }));
    }
  }, [refreshJobs, setState]);

  const handleCancel = useCallback(async (jobId: string) => {
    try {
      await socialApi.cancelJob(jobId);
      await refreshJobs();
    } catch (error) {
      setState((current) => ({
        ...current,
        error: getErrorMessage(error, tSafe('shareComposer.errors.cancelFailed')),
      }));
    }
  }, [refreshJobs, setState]);

  return { handleApprove, handleCancel, refreshJobs };
}

function useShareComposerPublishAction({
  clip,
  projectId,
  refreshJobs,
  selectedTargets,
  setState,
  state,
}: UseShareComposerControllerParams & {
  projectId: string | null;
  refreshJobs: () => Promise<void>;
  selectedTargets: Array<{ account_id: string; platform: SocialPlatform; provider?: string }>;
  setState: Dispatch<SetStateAction<ShareComposerState>>;
  state: ShareComposerState;
}) {
  return useCallback(async (mode: 'now' | 'scheduled', approvalRequired: boolean) => {
    if (!projectId || !clip || !state.contentByPlatform) {
      setState((current) => ({ ...current, error: tSafe('shareComposer.publish.missingProject') }));
      return;
    }

    if (selectedTargets.length === 0) {
      setState((current) => ({ ...current, error: tSafe('shareComposer.accounts.selectAtLeastOne') }));
      return;
    }

    setState((current) => ({ ...current, error: null, publishing: true, success: null }));
    try {
      const response = await socialApi.publish({
        approval_required: approvalRequired,
        clip_name: clip.name,
        content_by_platform: state.contentByPlatform,
        mode,
        project_id: projectId,
        scheduled_at: mode === 'scheduled' ? state.scheduleAt : undefined,
        targets: selectedTargets,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      });
      const publishError = summarizePublishErrors(response.errors);
      setState((current) => ({
        ...current,
        error: publishError,
        success: publishError ? null : getPublishSuccessMessage(mode, approvalRequired),
      }));
      await refreshJobs();
    } catch (error) {
      setState((current) => ({
        ...current,
        error: getErrorMessage(error, tSafe('shareComposer.publish.startFailed')),
      }));
    } finally {
      setState((current) => ({ ...current, publishing: false }));
    }
  }, [clip, projectId, refreshJobs, selectedTargets, setState, state.contentByPlatform, state.scheduleAt]);
}

function useShareComposerDraftActions({
  clip,
  loadData,
  projectId,
  setState,
}: {
  clip: Clip | null;
  loadData: () => Promise<LoadedShareComposerData | null>;
  projectId: string | null;
  setState: Dispatch<SetStateAction<ShareComposerState>>;
}) {
  const updateActiveContent = useCallback((patch: Partial<ShareDraftContent>) => {
    setState((current) => {
      if (!current.contentByPlatform) {
        return current;
      }

      return {
        ...current,
        contentByPlatform: {
          ...current.contentByPlatform,
          [current.selectedPlatform]: {
            ...current.contentByPlatform[current.selectedPlatform],
            ...patch,
          },
        },
        hasDirtyEdits: true,
      };
    });
  }, [setState]);

  const updateActiveHashtags = useCallback((value: string) => {
    updateActiveContent({ hashtags: buildHashtagsFromInput(value) });
  }, [updateActiveContent]);

  const handleResetDrafts = useCallback(async () => {
    if (!projectId || !clip) {
      return;
    }

    setState((current) => ({ ...current, error: null, loading: true, success: null }));
    try {
      window.localStorage.removeItem(localDraftKey(projectId, clip.name));
      await socialApi.deleteDrafts(projectId, clip.name);
      await loadData();
      setState((current) => ({
        ...current,
        success: tSafe('shareComposer.content.resetSuccess'),
      }));
    } catch (error) {
      setState((current) => ({
        ...current,
        error: getErrorMessage(error, tSafe('shareComposer.content.resetFailed')),
      }));
    } finally {
      setState((current) => ({ ...current, loading: false }));
    }
  }, [clip, loadData, projectId, setState]);

  const toggleAccount = useCallback((accountId: string) => {
    setState((current) => ({
      ...current,
      selectedAccountIds: toggleSelection(current.selectedAccountIds, accountId),
    }));
  }, [setState]);

  return {
    handleResetDrafts,
    toggleAccount,
    updateActiveContent,
    updateActiveHashtags,
  };
}

export function useShareComposerController({ clip, open }: UseShareComposerControllerParams) {
  const [state, setState] = useShareComposerState();
  const projectId = resolveProjectId(clip);
  const selectedTargets = useMemo(
    () => buildPublishTargets(state.accounts, state.selectedAccountIds),
    [state.accounts, state.selectedAccountIds],
  );
  const activeContent = state.contentByPlatform?.[state.selectedPlatform] ?? null;
  const loadData = useShareComposerData({ clip, open, projectId, setState });
  const { handleConnect, handleDisconnect } = useShareComposerConnectionActions(setState);
  const { handleApprove, handleCancel, refreshJobs } = useShareComposerJobActions({ clip, open, projectId, setState });
  const submitPublish = useShareComposerPublishAction({
    clip,
    open,
    projectId,
    refreshJobs,
    selectedTargets,
    setState,
    state,
  });
  const draftActions = useShareComposerDraftActions({ clip, loadData, projectId, setState });
  const handleRefreshConnection = useCallback(async () => {
    await loadData();
  }, [loadData]);

  useShareComposerAutosave({
    clip,
    contentByPlatform: state.contentByPlatform,
    hasDirtyEdits: state.hasDirtyEdits,
    open,
    projectId,
  });

  useManagedConnectionSync({
    connectionMode: state.connectionMode,
    loadData,
    managedConnectionPending: state.managedConnectionPending,
    open,
    setState,
  });
  useManagedOAuthCallbackSignal({
    connectionMode: state.connectionMode,
    loadData,
    open,
    setState,
  });

  return {
    activeContent,
    apiKey: state.apiKey,
    accounts: state.accounts,
    connected: state.connected,
    connectionMode: state.connectionMode,
    connectUrl: state.connectUrl,
    draftState: state.draftState,
    error: state.error,
    handleApprove,
    handleCancel,
    handleConnect: () => handleConnect(state.apiKey),
    handleDisconnect,
    handleRefreshConnection,
    jobs: state.jobs,
    loading: state.loading,
    managedConnectionPending: state.managedConnectionPending,
    handleManagedConnectOpen: () => {
      markManagedConnectPending();
      setState((current) => ({
        ...current,
        managedConnectionPending: true,
        success: null,
      }));
    },
    projectId,
    publishing: state.publishing,
    scheduleAt: state.scheduleAt,
    selectedAccountIds: state.selectedAccountIds,
    selectedPlatform: state.selectedPlatform,
    setApiKey: (apiKey: string) => setState((current) => ({ ...current, apiKey })),
    setScheduleAt: (scheduleAt: string) => setState((current) => ({ ...current, scheduleAt })),
    setSelectedPlatform: (selectedPlatform: SocialPlatform) => setState((current) => ({ ...current, selectedPlatform })),
    submitPublish,
    success: state.success,
    ...draftActions,
  };
}

export type ShareComposerController = ReturnType<typeof useShareComposerController>;
