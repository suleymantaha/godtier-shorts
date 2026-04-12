import { useCallback, useEffect, useMemo, useState } from 'react';
import type { TFunction } from 'i18next';
import { useTranslation } from 'react-i18next';

import { socialApi } from '../../api/client';
import { SOCIAL_COMPOSE_PATH } from '../../app/helpers';
import type {
  PublishJob,
  SocialAccount,
  SocialAccountAnalytics,
  SocialAnalyticsOverview,
  SocialPlatform,
  SocialPlatformAnalytics,
  SocialPostAnalytics,
  SocialProviderStatus,
} from '../../types';
import { resolveApiUrl } from '../../utils/url';
import {
  clearSocialConnectStatusQuery,
  readSocialConnectStatusFromQuery,
} from '../shareComposer/helpers';
import {
  buildComposeHref,
  readSocialWorkspaceClipContext,
  resolveSocialWorkspaceLocale,
  type SocialWorkspaceClipContext,
} from './helpers';

type SocialWorkspaceDataState = {
  accountAnalytics: SocialAccountAnalytics[];
  accounts: SocialAccount[];
  calendar: PublishJob[];
  error: string | null;
  loading: boolean;
  overview: SocialAnalyticsOverview | null;
  platformAnalytics: SocialPlatformAnalytics[];
  postAnalytics: SocialPostAnalytics[];
  providers: SocialProviderStatus[];
  queue: PublishJob[];
  refreshing: boolean;
  success: string | null;
};

type SocialWorkspaceDataController = SocialWorkspaceDataState & {
  loadWorkspace: (refreshAnalytics?: boolean) => Promise<void>;
  setError: (value: string | null) => void;
  setLoading: (value: boolean) => void;
  setRefreshing: (value: boolean) => void;
  setSuccess: (value: string | null) => void;
};

function resolveWorkspaceError(error: unknown, fallbackMessage: string): string {
  return error instanceof Error ? error.message : fallbackMessage;
}

async function readSocialWorkspaceData(refreshAnalytics: boolean) {
  const [
    providersResp,
    connectionsResp,
    queueResp,
    calendarResp,
    overviewResp,
    accountsResp,
    postsResp,
  ] = await Promise.all([
    socialApi.getProviders(),
    socialApi.getConnections(),
    socialApi.getQueue(),
    socialApi.getCalendar({ include_past: true }),
    socialApi.getAnalyticsOverview(refreshAnalytics),
    socialApi.getAnalyticsAccounts(refreshAnalytics),
    socialApi.getAnalyticsPosts(refreshAnalytics),
  ]);

  return {
    accountAnalytics: accountsResp.accounts ?? [],
    accounts: connectionsResp.accounts ?? [],
    calendar: calendarResp.items ?? [],
    overview: overviewResp.overview ?? null,
    platformAnalytics: overviewResp.platforms ?? [],
    postAnalytics: postsResp.posts ?? [],
    providers: providersResp.providers ?? [],
    queue: queueResp.jobs ?? [],
  };
}

function useSocialWorkspaceData(t: TFunction): SocialWorkspaceDataController {
  const [providers, setProviders] = useState<SocialProviderStatus[]>([]);
  const [accounts, setAccounts] = useState<SocialAccount[]>([]);
  const [queue, setQueue] = useState<PublishJob[]>([]);
  const [calendar, setCalendar] = useState<PublishJob[]>([]);
  const [overview, setOverview] = useState<SocialAnalyticsOverview | null>(null);
  const [platformAnalytics, setPlatformAnalytics] = useState<SocialPlatformAnalytics[]>([]);
  const [accountAnalytics, setAccountAnalytics] = useState<SocialAccountAnalytics[]>([]);
  const [postAnalytics, setPostAnalytics] = useState<SocialPostAnalytics[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const loadWorkspace = useCallback(async (refreshAnalytics = false) => {
    setError(null);
    try {
      const nextState = await readSocialWorkspaceData(refreshAnalytics);
      setProviders(nextState.providers);
      setAccounts(nextState.accounts);
      setQueue(nextState.queue);
      setCalendar(nextState.calendar);
      setOverview(nextState.overview);
      setPlatformAnalytics(nextState.platformAnalytics);
      setAccountAnalytics(nextState.accountAnalytics);
      setPostAnalytics(nextState.postAnalytics);
    } catch (error) {
      setError(resolveWorkspaceError(error, t('socialWorkspace.errors.loadFailed')));
    }
  }, [t]);

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      setLoading(true);
      await loadWorkspace();
      if (!cancelled) {
        setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [loadWorkspace]);

  return {
    accountAnalytics,
    accounts,
    calendar,
    error,
    loading,
    loadWorkspace,
    overview,
    platformAnalytics,
    postAnalytics,
    providers,
    queue,
    refreshing,
    setError,
    setLoading,
    setRefreshing,
    setSuccess,
    success,
  };
}

function useSocialConnectCallbackEffect({
  loadWorkspace,
  setError,
  setRefreshing,
  setSuccess,
  t,
}: Pick<SocialWorkspaceDataController, 'loadWorkspace' | 'setError' | 'setRefreshing' | 'setSuccess'>
  & { t: TFunction }) {
  useEffect(() => {
    const connectStatus = readSocialConnectStatusFromQuery(window.location.search);
    if (!connectStatus) {
      return;
    }

    clearSocialConnectStatusQuery();
    if (connectStatus === 'error') {
      setError(t('socialWorkspace.errors.connectionCallbackFailed'));
      return;
    }

    setRefreshing(true);
    setError(null);
    void (async () => {
      try {
        await socialApi.syncConnections();
        await loadWorkspace(true);
        setSuccess(t('socialWorkspace.connections.connected'));
      } catch (error) {
        setError(resolveWorkspaceError(error, t('socialWorkspace.errors.syncFailed')));
      } finally {
        setRefreshing(false);
      }
    })();
  }, [loadWorkspace, setError, setRefreshing, setSuccess, t]);
}

function useSocialConnectionActions({
  loadWorkspace,
  providers,
  setError,
  setRefreshing,
  setSuccess,
  t,
}: Pick<SocialWorkspaceDataController, 'loadWorkspace' | 'providers' | 'setError' | 'setRefreshing' | 'setSuccess'>
  & { t: TFunction }) {
  useSocialConnectCallbackEffect({ loadWorkspace, setError, setRefreshing, setSuccess, t });

  const handleSyncConnections = useCallback(async () => {
    setRefreshing(true);
    setError(null);
    try {
      await socialApi.syncConnections();
      await loadWorkspace();
      setSuccess(t('socialWorkspace.connections.synced'));
    } catch (error) {
      setError(resolveWorkspaceError(error, t('socialWorkspace.errors.syncFailed')));
    } finally {
      setRefreshing(false);
    }
  }, [loadWorkspace, setError, setRefreshing, setSuccess, t]);

  const handleStartConnection = useCallback(async (platform: SocialPlatform) => {
    setRefreshing(true);
    setError(null);
    setSuccess(null);
    try {
      const response = await socialApi.startConnection({ platform, return_url: window.location.href });
      window.open(resolveApiUrl(response.launch_url), '_blank', 'noopener,noreferrer');
      setSuccess(t('socialWorkspace.connections.connectionStarted', {
        platform: providers.find((item) => item.platform === platform)?.title ?? platform,
      }));
    } catch (error) {
      setError(resolveWorkspaceError(error, t('socialWorkspace.errors.connectionStartFailed')));
    } finally {
      setRefreshing(false);
    }
  }, [providers, setError, setRefreshing, setSuccess, t]);

  const handleDeleteConnection = useCallback(async (accountId: string) => {
    setRefreshing(true);
    setError(null);
    try {
      await socialApi.deleteConnection(accountId);
      await handleSyncConnections();
    } catch (error) {
      setError(resolveWorkspaceError(error, t('socialWorkspace.errors.disconnectFailed')));
      setRefreshing(false);
    }
  }, [handleSyncConnections, setError, setRefreshing, t]);

  return {
    handleDeleteConnection,
    handleStartConnection,
    handleSyncConnections,
  };
}

function useSocialPublicationActions({
  loadWorkspace,
  setError,
  setRefreshing,
  setSuccess,
  t,
}: Pick<SocialWorkspaceDataController, 'loadWorkspace' | 'setError' | 'setRefreshing' | 'setSuccess'>
  & { t: TFunction }) {
  const handleRefreshAnalytics = useCallback(async () => {
    setRefreshing(true);
    setError(null);
    try {
      await loadWorkspace(true);
      setSuccess(t('socialWorkspace.analytics.refreshed'));
    } finally {
      setRefreshing(false);
    }
  }, [loadWorkspace, setError, setRefreshing, setSuccess, t]);

  const handleQueueAction = useCallback(async (job: PublishJob, action: 'approve' | 'cancel') => {
    setRefreshing(true);
    setError(null);
    try {
      if (action === 'approve') {
        await socialApi.approveJob(job.id);
      } else {
        await socialApi.cancelJob(job.id);
      }
      await loadWorkspace(true);
    } catch (error) {
      setError(resolveWorkspaceError(error, t('socialWorkspace.errors.queueActionFailed')));
    } finally {
      setRefreshing(false);
    }
  }, [loadWorkspace, setError, setRefreshing, t]);

  const handleReschedule = useCallback(async (
    job: PublishJob,
    nextValue: string,
  ) => {
    if (!nextValue) {
      return;
    }

    setRefreshing(true);
    setError(null);
    try {
      await socialApi.updateCalendarItem(job.id, {
        scheduled_at: nextValue,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      });
      await loadWorkspace(true);
      setSuccess(t('socialWorkspace.calendar.updated'));
    } catch (error) {
      setError(resolveWorkspaceError(error, t('socialWorkspace.errors.calendarUpdateFailed')));
    } finally {
      setRefreshing(false);
    }
  }, [loadWorkspace, setError, setRefreshing, setSuccess, t]);

  return {
    handleQueueAction,
    handleRefreshAnalytics,
    handleReschedule,
  };
}

export function useSocialWorkspaceController() {
  const { t, i18n } = useTranslation();
  const locationSearch = typeof window !== 'undefined' ? window.location.search : '';
  const clipContext = useMemo<SocialWorkspaceClipContext>(
    () => readSocialWorkspaceClipContext(locationSearch),
    [locationSearch],
  );
  const data = useSocialWorkspaceData(t);
  const connectionActions = useSocialConnectionActions({ ...data, t });
  const publicationActions = useSocialPublicationActions({ ...data, t });

  return {
    ...data,
    ...connectionActions,
    ...publicationActions,
    clipContext,
    connectedAccountCount: data.overview?.connected_accounts ?? data.accounts.length,
    contextComposeHref: buildComposeHref(clipContext.projectId, clipContext.clipName),
    defaultComposeHref: SOCIAL_COMPOSE_PATH,
    locale: resolveSocialWorkspaceLocale(i18n.language),
    t,
  };
}
