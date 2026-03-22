import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { AppErrorCode } from '../api/errors';
import { useAuthRuntimeStore } from '../auth/runtime';
import { tSafe } from '../i18n';
import { getFlattenedJobLogs, useJobStore, type JobState } from '../store/useJobStore';
import type { DownloadProgress, Job, LogEntry, WsStatus } from '../types';
import { Expand, ShieldCheck, Terminal, Trash2, X } from 'lucide-react';

function resolveAuthStatusLabel(
    backendAuthStatus: 'fresh' | 'paused' | 'refreshing',
    canUseProtectedRequests: boolean,
    pauseReason: AppErrorCode | null,
    t: (key: string) => string,
): string {
    if (backendAuthStatus === 'refreshing') {
        return t('terminal.status.auth.refreshing');
    }
    if (backendAuthStatus === 'paused') {
        return pauseReason === 'token_expired'
            ? t('terminal.status.auth.tokenExpired')
            : canUseProtectedRequests
                ? t('terminal.status.auth.fallback')
                : t('terminal.status.auth.paused');
    }
    return t('terminal.status.auth.ready');
}

function resolveWsStatusLabel(
    status: WsStatus,
    t: (key: string) => string,
): string {
    return t(`terminal.status.ws.${status}`);
}

function renderLogEntries(logs: LogEntry[]) {
    return logs.map((log, index) => (
        <div key={`${log.id}-${index}`} className="flex min-w-0 max-w-full items-start gap-3 overflow-hidden animate-in fade-in slide-in-from-left-2 duration-500">
            <span className="shrink-0 text-muted-foreground whitespace-nowrap">[{log.timestamp}]</span>
            <span
                className={`min-w-0 flex-1 overflow-hidden break-words whitespace-pre-wrap leading-relaxed ${log.progress === -1 ? 'text-red-400' : 'text-primary/80'}`}
            >
                {log.progress === -1 ? '!!!' : '>>>'} {log.message}
            </span>
        </div>
    ));
}

function resolveEmptyState(
    backendAuthStatus: 'fresh' | 'paused' | 'refreshing',
    canUseProtectedRequests: boolean,
    pauseReason: AppErrorCode | null,
    wsStatus: WsStatus,
    hasJobs: boolean,
    t: (key: string) => string,
) {
    if (backendAuthStatus === 'paused') {
        return pauseReason === 'token_expired'
            ? t('terminal.empty.authRefreshRequired')
            : canUseProtectedRequests
                ? t('terminal.empty.authFallback')
                : t('terminal.empty.authPaused');
    }
    if (wsStatus === 'connecting' || wsStatus === 'reconnecting') {
        return t('terminal.empty.connecting');
    }
    if (wsStatus === 'connected') {
        return hasJobs ? t('terminal.empty.connectedSyncing') : t('terminal.empty.connectedIdle');
    }
    return t('terminal.empty.offline');
}

function resolveTerminalSnapshot(
    jobs: JobState['jobs'],
    logs: LogEntry[],
    backendAuthStatus: 'fresh' | 'paused' | 'refreshing',
    effectiveWsStatus: WsStatus,
    t: (key: string) => string,
) {
    const lastLog = logs[logs.length - 1];
    const activeJob = jobs.find((job) => job.status === 'processing') ?? jobs.find((job) => job.status === 'queued');
    const progress = activeJob ? resolveJobDisplayProgress(activeJob) : (lastLog ? lastLog.progress : 0);

    if (activeJob) {
        return {
            progress,
            status: activeJob.last_message,
            summary: resolveJobSummary(activeJob),
        };
    }
    if (lastLog) {
        return { progress, status: lastLog.message, summary: null };
    }
    if (backendAuthStatus === 'paused') {
        return { progress, status: t('terminal.snapshot.authPaused'), summary: null };
    }
    if (effectiveWsStatus === 'connecting' || effectiveWsStatus === 'reconnecting') {
        return { progress, status: t('terminal.snapshot.connecting'), summary: null };
    }
    return { progress, status: t('terminal.snapshot.ready'), summary: null };
}

function resolveJobDisplayProgress(job: Job): number {
    if (job.download_progress?.phase === 'download' && typeof job.download_progress.percent === 'number') {
        return Math.max(0, Math.min(100, job.download_progress.percent));
    }
    return job.progress;
}

function formatByteCount(value?: number): string | null {
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
    const precision = unitIndex === 0 ? 0 : 1;
    return `${normalized.toFixed(precision)} ${units[unitIndex]}`;
}

function resolveDownloadSummary(downloadProgress?: DownloadProgress): string | null {
    if (!downloadProgress || downloadProgress.phase !== 'download') {
        return null;
    }

    const downloaded = formatByteCount(downloadProgress.downloaded_bytes);
    const total = formatByteCount(downloadProgress.total_bytes ?? downloadProgress.total_bytes_estimate);
    const parts = [
        downloaded && total ? `${downloaded} / ${total}` : null,
        typeof downloadProgress.percent === 'number' ? `${downloadProgress.percent.toFixed(1)}%` : null,
        downloadProgress.speed_text ?? null,
        downloadProgress.eta_text ? `ETA ${downloadProgress.eta_text}` : null,
    ].filter(Boolean);

    return parts.length > 0 ? parts.join(' • ') : null;
}

function resolveJobSummary(job: Job): string | null {
    return resolveDownloadSummary(job.download_progress);
}

function resolveStatusTone(
    status: 'connected' | 'connecting' | 'disconnected' | 'fresh' | 'paused' | 'reconnecting' | 'refreshing' | 'other',
): string {
    if (status === 'connected' || status === 'fresh') {
        return 'border-emerald-400/30 bg-emerald-500/15 text-emerald-100';
    }
    if (status === 'disconnected') {
        return 'border-red-400/30 bg-red-500/15 text-red-100';
    }
    return 'border-yellow-400/30 bg-yellow-500/15 text-yellow-100';
}

function formatRetentionCountdown(expiresAt: number, now: number): string {
    const remainingMs = Math.max(0, expiresAt - now);
    const totalSeconds = Math.ceil(remainingMs / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;

    if (minutes <= 0) {
        return tSafe('common.time.autoClearInSeconds', { seconds });
    }
    if (seconds === 0) {
        return tSafe('common.time.autoClearInMinutes', { minutes });
    }
    return tSafe('common.time.autoClearInMinutesSeconds', { minutes, seconds });
}

function TerminalChrome({
    authStatusLabel,
    authStatusTone,
    canClearHistory,
    compact,
    hasRetainedHistory,
    historyRetentionLabel,
    onClearHistory,
    onExpand,
    progress,
    summary,
    status,
    wsStatusLabel,
    wsStatusTone,
}: {
    authStatusLabel: string;
    authStatusTone: string;
    canClearHistory: boolean;
    compact: boolean;
    hasRetainedHistory: boolean;
    historyRetentionLabel: string | null;
    onClearHistory: () => void;
    onExpand: () => void;
    progress: number;
    summary: string | null;
    status: string;
    wsStatusLabel: string;
    wsStatusTone: string;
}) {
    const { t } = useTranslation();
    return (
        <div className={`border-b border-white/5 flex min-w-0 items-center justify-between gap-3 bg-white/[0.02] ${compact ? 'px-3.5 py-2' : 'px-4 py-3'}`}>
            <div className="flex min-w-0 flex-1 items-center gap-2 overflow-hidden">
                <Terminal className="h-4 w-4 shrink-0 text-primary" />
                <span className="truncate text-xs font-mono font-bold uppercase tracking-[0.2em] holo-text text-primary">
                    {compact ? t('terminal.compactTitle') : t('terminal.fullTitle')}
                </span>
            </div>
            <div className="flex min-w-0 flex-1 items-center justify-end gap-2 overflow-hidden">
                <span className={`inline-flex items-center rounded-full px-2 py-1 text-[10px] font-mono uppercase tracking-wider ${wsStatusTone}`}>
                    {wsStatusLabel}
                </span>
                <span className={`inline-flex items-center rounded-full px-2 py-1 text-[10px] font-mono uppercase tracking-wider ${authStatusTone}`}>
                    {authStatusLabel}
                </span>
                <div className={`h-2 w-2 shrink-0 rounded-full animate-pulse ${progress === 100 ? 'bg-green-500' : progress === -1 ? 'bg-red-500' : 'bg-primary'}`} />
                <div className="min-w-0 max-w-full overflow-hidden text-right">
                    <span className="block truncate text-[11px] font-mono text-muted-foreground" title={status}>
                        {status}
                    </span>
                    {summary && (
                        <span className="block truncate text-[10px] font-mono text-primary/80" title={summary}>
                            {summary}
                        </span>
                    )}
                    {historyRetentionLabel && (
                        <span className="block truncate text-[10px] font-mono text-muted-foreground/80" title={historyRetentionLabel}>
                            {historyRetentionLabel}
                        </span>
                    )}
                </div>
                {hasRetainedHistory && (
                    <button
                        type="button"
                        onClick={onClearHistory}
                        disabled={!canClearHistory}
                        className="inline-flex items-center gap-1 rounded-lg border border-white/15 bg-white/5 px-2.5 py-1 text-[10px] font-mono uppercase tracking-wider text-foreground transition-colors hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-white/5"
                        aria-label={t('common.actions.clearHistory')}
                    >
                        <Trash2 className="h-3 w-3" />
                        {t('common.actions.clearHistory')}
                    </button>
                )}
                {compact && (
                    <button
                        type="button"
                        onClick={onExpand}
                        className="inline-flex items-center gap-1 rounded-lg border border-white/15 bg-white/5 px-2.5 py-1 text-[10px] font-mono uppercase tracking-wider text-foreground transition-colors hover:bg-white/10"
                        aria-label={t('common.actions.expandLogs')}
                    >
                        <Expand className="h-3 w-3" />
                        {t('common.actions.expandLogs')}
                    </button>
                )}
            </div>
        </div>
    );
}

function TerminalBody({
    compact,
    emptyStateMessage,
    panelScrollRef,
    visibleLogs,
}: {
    compact: boolean;
    emptyStateMessage: string;
    panelScrollRef: React.RefObject<HTMLDivElement | null>;
    visibleLogs: LogEntry[];
}) {
    return (
        <div className="flex min-w-0 flex-1 items-center gap-2 overflow-hidden">
            <div
                ref={panelScrollRef}
                className={`flex-1 min-w-0 overflow-x-hidden overflow-y-auto font-mono text-[11px] space-y-2 scrollbar-hide selection:bg-primary/20 ${compact ? 'p-2.5' : 'p-4'}`}
            >
                {renderLogEntries(visibleLogs)}
                {visibleLogs.length === 0 && (
                    <div className="h-full flex flex-col items-center justify-center text-muted-foreground opacity-20 select-none">
                        <ShieldCheck className="w-12 h-12 mb-2" />
                        <p>{emptyStateMessage}</p>
                    </div>
                )}
            </div>
        </div>
    );
}

function TerminalProgress({ compact, progress }: { compact: boolean; progress: number }) {
    const { t } = useTranslation();

    return (
        <div className={`border-t border-white/5 bg-black/40 ${compact ? 'p-2.5' : 'p-4'}`}>
            <div className={`flex justify-between font-mono ${compact ? 'mb-1.5 text-[10px]' : 'mb-2 text-[11px]'}`}>
                <span className="text-muted-foreground">{t('terminal.systemProgress')}</span>
                <span className="text-primary" aria-live="polite">{Math.max(0, progress)}%</span>
            </div>
            <div
                className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden"
                role="progressbar"
                aria-valuenow={Math.max(0, progress)}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={t('terminal.systemProgressAria')}
            >
                <div
                    className="h-full bg-gradient-to-r from-primary via-secondary to-accent transition-all duration-1000 ease-out shadow-[0_0_10px_rgba(0,242,255,0.5)]"
                    style={{ width: `${Math.max(0, progress)}%` }}
                />
            </div>
        </div>
    );
}

function ExpandedLogsDialog({
    authStatusLabel,
    authStatusTone,
    canClearHistory,
    emptyStateMessage,
    expandedScrollRef,
    hasRetainedHistory,
    historyRetentionLabel,
    logs,
    onClearHistory,
    onClose,
    wsStatusLabel,
    wsStatusTone,
}: {
    authStatusLabel: string;
    authStatusTone: string;
    canClearHistory: boolean;
    emptyStateMessage: string;
    expandedScrollRef: React.RefObject<HTMLDivElement | null>;
    hasRetainedHistory: boolean;
    historyRetentionLabel: string | null;
    logs: LogEntry[];
    onClearHistory: () => void;
    onClose: () => void;
    wsStatusLabel: string;
    wsStatusTone: string;
}) {
    const { t } = useTranslation();

    return (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm p-4 md:p-6 flex items-center justify-center">
            <div
                role="dialog"
                aria-modal="true"
                aria-label={t('terminal.historyTitle')}
                className="w-full max-w-4xl max-h-[90vh] h-full glass-card border-white/15 overflow-hidden flex flex-col"
            >
                <div className="border-b border-white/10 px-4 py-3 flex items-center justify-between gap-3 bg-white/[0.02]">
                    <div className="flex items-center gap-2 min-w-0">
                        <Terminal className="h-4 w-4 text-primary shrink-0" />
                        <span className="truncate text-xs font-mono font-bold uppercase tracking-[0.2em] text-primary">
                            {t('terminal.historyTitle')}
                        </span>
                    </div>
                    <div className="flex items-center gap-2">
                        {historyRetentionLabel && (
                            <span className="hidden text-[10px] font-mono uppercase tracking-wider text-muted-foreground md:inline">
                                {historyRetentionLabel}
                            </span>
                        )}
                        <span className={`inline-flex items-center rounded-full px-2 py-1 text-[10px] font-mono uppercase tracking-wider ${wsStatusTone}`}>
                            {wsStatusLabel}
                        </span>
                        <span className={`inline-flex items-center rounded-full px-2 py-1 text-[10px] font-mono uppercase tracking-wider ${authStatusTone}`}>
                            {authStatusLabel}
                        </span>
                        {hasRetainedHistory && (
                            <button
                                type="button"
                                onClick={onClearHistory}
                                disabled={!canClearHistory}
                                className="inline-flex items-center gap-1 rounded-lg border border-white/15 bg-white/5 px-2.5 py-1 text-[10px] font-mono uppercase tracking-wider text-foreground transition-colors hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-white/5"
                                aria-label={t('common.actions.clearHistory')}
                            >
                                <Trash2 className="h-3 w-3" />
                                {t('common.actions.clearHistory')}
                            </button>
                        )}
                        <button
                            type="button"
                            onClick={onClose}
                            className="inline-flex items-center gap-1 rounded-lg border border-white/15 bg-white/5 px-2.5 py-1 text-[10px] font-mono uppercase tracking-wider text-foreground transition-colors hover:bg-white/10"
                            aria-label={t('terminal.closeExpanded')}
                        >
                            <X className="h-3 w-3" />
                            {t('common.actions.close')}
                        </button>
                    </div>
                </div>
                <div
                    ref={expandedScrollRef}
                    className="flex-1 overflow-y-auto overflow-x-hidden p-4 font-mono text-[11px] space-y-2 selection:bg-primary/20"
                >
                    {renderLogEntries(logs)}
                    {logs.length === 0 && (
                        <div className="h-full flex flex-col items-center justify-center text-muted-foreground opacity-20 select-none">
                            <ShieldCheck className="w-12 h-12 mb-2" />
                            <p>{emptyStateMessage}</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

function useTerminalPanels({
    expandedScrollRef,
    isExpanded,
    onEscape,
    panelScrollRef,
    visibleLogs,
    logs,
}: {
    expandedScrollRef: React.RefObject<HTMLDivElement | null>;
    isExpanded: boolean;
    logs: ReturnType<typeof getFlattenedJobLogs>;
    onEscape: () => void;
    panelScrollRef: React.RefObject<HTMLDivElement | null>;
    visibleLogs: ReturnType<typeof getFlattenedJobLogs>;
}) {
    useEffect(() => {
        if (panelScrollRef.current) {
            panelScrollRef.current.scrollTop = panelScrollRef.current.scrollHeight;
        }
    }, [panelScrollRef, visibleLogs]);

    useEffect(() => {
        if (isExpanded && expandedScrollRef.current) {
            expandedScrollRef.current.scrollTop = expandedScrollRef.current.scrollHeight;
        }
    }, [expandedScrollRef, isExpanded, logs]);

    useEffect(() => {
        if (!isExpanded) {
            return;
        }

        const onKeyDown = (event: KeyboardEvent) => {
            if (event.key === 'Escape') {
                onEscape();
            }
        };

        window.addEventListener('keydown', onKeyDown);
        return () => window.removeEventListener('keydown', onKeyDown);
    }, [isExpanded, onEscape]);
}

export const HoloTerminal: React.FC<{ compact?: boolean }> = ({ compact = false }) => {
    const {
        clearRetainedHistory,
        hasRetainedHistory,
        jobHistoryExpiresAt,
        jobs,
        wsStatus,
    } = useJobStore();
    const backendAuthStatus = useAuthRuntimeStore((state) => state.backendAuthStatus);
    const canUseProtectedRequests = useAuthRuntimeStore((state) => state.canUseProtectedRequests);
    const pauseReason = useAuthRuntimeStore((state) => state.pauseReason);
    const [isLogsExpanded, setIsLogsExpanded] = useState(false);
    const [retentionNow, setRetentionNow] = useState(() => Date.now());
    const { t } = useTranslation();

    const effectiveWsStatus = backendAuthStatus === 'paused' ? 'disconnected' : wsStatus;
    const logs = useMemo(() => getFlattenedJobLogs(jobs), [jobs]);
    const { progress, status, summary } = useMemo(
        () => resolveTerminalSnapshot(jobs, logs, backendAuthStatus, effectiveWsStatus, t),
        [backendAuthStatus, effectiveWsStatus, jobs, logs, t],
    );
    const authStatusLabel = resolveAuthStatusLabel(backendAuthStatus, canUseProtectedRequests, pauseReason, t);
    const wsStatusLabel = resolveWsStatusLabel(effectiveWsStatus, t);
    const panelScrollRef = useRef<HTMLDivElement>(null);
    const expandedScrollRef = useRef<HTMLDivElement>(null);
    const visibleLogs = useMemo(() => (compact ? logs.slice(-3) : logs), [compact, logs]);
    const isExpanded = compact && isLogsExpanded;
    const closeExpandedLogs = () => setIsLogsExpanded(false);
    const hasActiveJobs = useMemo(
        () => jobs.some((job) => job.status === 'processing' || job.status === 'queued'),
        [jobs],
    );
    const canClearHistory = hasRetainedHistory && !hasActiveJobs;
    const historyRetentionLabel = useMemo(() => {
        if (jobHistoryExpiresAt === null || hasActiveJobs) {
            return null;
        }
        return formatRetentionCountdown(jobHistoryExpiresAt, retentionNow);
    }, [hasActiveJobs, jobHistoryExpiresAt, retentionNow]);
    const emptyStateMessage = useMemo(
        () => resolveEmptyState(backendAuthStatus, canUseProtectedRequests, pauseReason, effectiveWsStatus, jobs.length > 0, t),
        [backendAuthStatus, canUseProtectedRequests, effectiveWsStatus, jobs.length, pauseReason, t],
    );
    const wsStatusTone = resolveStatusTone(effectiveWsStatus);
    const authStatusTone = resolveStatusTone(backendAuthStatus);

    useEffect(() => {
        if (jobHistoryExpiresAt === null || hasActiveJobs) {
            return undefined;
        }

        setRetentionNow(Date.now());
        const intervalId = window.setInterval(() => {
            setRetentionNow(Date.now());
        }, 1000);

        return () => window.clearInterval(intervalId);
    }, [hasActiveJobs, jobHistoryExpiresAt]);

    const expandedLogsDialog = isExpanded ? (
        <ExpandedLogsDialog
            authStatusLabel={authStatusLabel}
            authStatusTone={authStatusTone}
            canClearHistory={canClearHistory}
            emptyStateMessage={emptyStateMessage}
            expandedScrollRef={expandedScrollRef}
            hasRetainedHistory={hasRetainedHistory}
            historyRetentionLabel={historyRetentionLabel}
            logs={logs}
            onClearHistory={clearRetainedHistory}
            onClose={closeExpandedLogs}
            wsStatusLabel={wsStatusLabel}
            wsStatusTone={wsStatusTone}
        />
    ) : null;
    useTerminalPanels({
        expandedScrollRef,
        isExpanded,
        logs,
        onEscape: closeExpandedLogs,
        panelScrollRef,
        visibleLogs,
    });

    return (
        <>
            <div className={`flex h-full w-full max-w-full min-w-0 flex-col overflow-hidden ${compact ? 'min-h-[160px]' : 'min-h-[250px]'}`}>
                <TerminalChrome
                    authStatusLabel={authStatusLabel}
                    authStatusTone={authStatusTone}
                    canClearHistory={canClearHistory}
                    compact={compact}
                    hasRetainedHistory={hasRetainedHistory}
                    historyRetentionLabel={historyRetentionLabel}
                    onClearHistory={clearRetainedHistory}
                    onExpand={() => setIsLogsExpanded(true)}
                    progress={progress}
                    summary={summary}
                    status={status}
                    wsStatusLabel={wsStatusLabel}
                    wsStatusTone={wsStatusTone}
                />
                <TerminalBody
                    compact={compact}
                    emptyStateMessage={emptyStateMessage}
                    panelScrollRef={panelScrollRef}
                    visibleLogs={visibleLogs}
                />
                <TerminalProgress compact={compact} progress={progress} />
            </div>
            {expandedLogsDialog}
        </>
    );
};
