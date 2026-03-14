import { useCallback, useEffect, useMemo, useState, type Dispatch, type SetStateAction } from 'react';

import { socialApi } from '../../api/client';
import type { Clip, PublishJob, ShareDraftContent, SocialAccount, SocialPlatform } from '../../types';
import {
  DEFAULT_PLATFORM,
  buildDraftState,
  buildHashtagsFromInput,
  buildPublishTargets,
  getErrorMessage,
  getPublishSuccessMessage,
  localDraftKey,
  mergeDraftContent,
  nowPlusHourLocal,
  parseLocalDraftBuffer,
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
  contentByPlatform: ShareComposerContentMap | null;
  draftState: DraftState;
  error: string | null;
  hasDirtyEdits: boolean;
  jobs: PublishJob[];
  loading: boolean;
  publishing: boolean;
  scheduleAt: string;
  selectedAccountIds: string[];
  selectedPlatform: SocialPlatform;
  success: string | null;
}

interface LoadedShareComposerData {
  accounts: SocialAccount[];
  connected: boolean;
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
    contentByPlatform: null,
    draftState: { hasLocalBuffer: false, hasServerDrafts: false },
    error: null,
    hasDirtyEdits: false,
    jobs: [],
    loading: false,
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
      return;
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
    } catch (error) {
      setState((current) => ({
        ...current,
        error: getErrorMessage(error, 'Paylaşım verileri yüklenemedi.'),
      }));
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
      setState((current) => ({ ...current, error: 'API key girin.' }));
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
        success: 'Postiz hesabı bağlandı.',
      }));
    } catch (error) {
      setState((current) => ({
        ...current,
        error: getErrorMessage(error, 'Postiz bağlantısı başarısız.'),
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
        success: 'Postiz bağlantısı kaldırıldı.',
      }));
    } catch (error) {
      setState((current) => ({
        ...current,
        error: getErrorMessage(error, 'Bağlantı kaldırılamadı.'),
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
        error: getErrorMessage(error, 'Onay başarısız.'),
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
        error: getErrorMessage(error, 'İptal başarısız.'),
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
      setState((current) => ({ ...current, error: 'Geçerli proje/klip seçilemedi.' }));
      return;
    }

    if (selectedTargets.length === 0) {
      setState((current) => ({ ...current, error: 'En az bir bağlı hesap seçin.' }));
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
        error: getErrorMessage(error, 'Paylaşım başlatılamadı.'),
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
  loadData: () => Promise<void>;
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
        success: 'Kayıtlı paylaşım taslağı temizlendi. AI önerisi tekrar yüklendi.',
      }));
    } catch (error) {
      setState((current) => ({
        ...current,
        error: getErrorMessage(error, 'Taslak temizlenemedi.'),
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

  useShareComposerAutosave({
    clip,
    contentByPlatform: state.contentByPlatform,
    hasDirtyEdits: state.hasDirtyEdits,
    open,
    projectId,
  });

  return {
    activeContent,
    apiKey: state.apiKey,
    accounts: state.accounts,
    connected: state.connected,
    draftState: state.draftState,
    error: state.error,
    handleApprove,
    handleCancel,
    handleConnect: () => handleConnect(state.apiKey),
    handleDisconnect,
    jobs: state.jobs,
    loading: state.loading,
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
