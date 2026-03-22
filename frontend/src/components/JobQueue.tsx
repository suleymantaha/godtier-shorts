import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { useJobStore } from '../store/useJobStore';
import { Loader2, Clock, XCircle, AlertCircle } from 'lucide-react';
import { IconButton } from './ui/IconButton';
import type { DownloadProgress, Job } from '../types';

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

function resolveDownloadDetail(downloadProgress?: DownloadProgress) {
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

function resolveDisplayProgress(job: Job): number {
    if (job.status === 'processing' && job.download_progress?.phase === 'download' && typeof job.download_progress.percent === 'number') {
        return Math.max(0, Math.min(100, job.download_progress.percent));
    }
    return Math.max(0, Math.min(100, job.progress));
}

export const JobQueue: React.FC = () => {
    const { t } = useTranslation();
    const { jobs, cancelJob, lastError, clearError } = useJobStore();
    const [pendingCancelJobId, setPendingCancelJobId] = useState<string | null>(null);

    const activeOrQueuedJobs = jobs
        .filter(j => ['queued', 'processing'].includes(j.status))
        .sort((left, right) => left.created_at - right.created_at);
    const activeJob = activeOrQueuedJobs.find((job) => job.status === 'processing');
    const queuedCount = activeOrQueuedJobs.filter((job) => job.status === 'queued').length;

    useEffect(() => {
        if (!pendingCancelJobId) {
            return undefined;
        }

        const timeoutId = window.setTimeout(() => {
            setPendingCancelJobId((current) => (current === pendingCancelJobId ? null : current));
        }, 4000);

        return () => window.clearTimeout(timeoutId);
    }, [pendingCancelJobId]);

    if (activeOrQueuedJobs.length === 0 && !lastError) return null;

    return (
        <div className="space-y-4">
            {lastError && (
                <div className="glass-card p-4 flex items-center justify-between gap-3 border-red-500/30 bg-red-500/5 animate-in fade-in slide-in-from-bottom-2">
                    <div className="flex items-center gap-2 text-red-400 text-sm">
                        <AlertCircle className="w-4 h-4 shrink-0" />
                        <span>{lastError}</span>
                    </div>
                    <IconButton label={t('common.actions.close')} icon={<XCircle className="w-4 h-4" />} onClick={clearError} className="hover:text-red-300" />
                </div>
            )}
            {activeOrQueuedJobs.length > 0 && (
        <section className="glass-card p-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <h2 className="text-sm uppercase tracking-[0.2em] font-bold mb-4 flex items-center gap-2 text-primary holo-text">
                <Clock className="w-4 h-4" />
                {t('jobQueue.title')}
            </h2>
            <div className="mb-4 grid gap-2 md:grid-cols-2">
                <div className="rounded-xl border border-border/70 bg-foreground/5 px-3 py-2">
                    <div className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground">
                        {t('jobQueue.currentJob')}
                    </div>
                    <div className="mt-1 text-sm font-medium text-foreground" aria-live="polite">
                        {activeJob ? activeJob.job_id : t('jobQueue.noActiveJob')}
                    </div>
                    <div className="mt-1 truncate text-[11px] text-muted-foreground">
                        {activeJob?.last_message || t('jobQueue.idle')}
                    </div>
                </div>
                <div className="rounded-xl border border-border/70 bg-foreground/5 px-3 py-2">
                    <div className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground">
                        {t('jobQueue.queuedJobs')}
                    </div>
                    <div className="mt-1 text-sm font-medium text-foreground" aria-live="polite">
                        {queuedCount}
                    </div>
                    <div className="mt-1 text-[11px] text-muted-foreground">
                        {queuedCount === 0 ? t('jobQueue.noWaitingJobs') : t('jobQueue.waitingForSlot')}
                    </div>
                </div>
            </div>

            <div className="space-y-4">
                {activeOrQueuedJobs.map((job) => (
                    <div key={job.job_id} className="relative group border-b border-border pb-4 last:border-0 last:pb-0">
                        {(() => {
                            const displayProgress = resolveDisplayProgress(job);
                            const downloadDetail = resolveDownloadDetail(job.download_progress);
                            const isCancelPending = pendingCancelJobId === job.job_id;

                            return (
                                <>
                        <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-3 overflow-hidden">
                                {job.status === 'processing' ? (
                                    <Loader2 className="w-4 h-4 text-primary animate-spin" />
                                ) : (
                                    <Clock className="w-4 h-4 text-muted-foreground" />
                                )}
                                <div className="flex flex-col truncate">
                                    <span className="text-[11px] font-mono text-muted-foreground uppercase">ID: {job.job_id}</span>
                                    <span className="text-xs font-medium truncate">{job.url}</span>
                                </div>
                            </div>

                            <IconButton
                                label={isCancelPending ? t('jobQueue.confirmCancel') : t('jobQueue.cancel')}
                                icon={<XCircle className="w-4 h-4" />}
                                onClick={() => {
                                    if (!isCancelPending) {
                                        setPendingCancelJobId(job.job_id);
                                        return;
                                    }
                                    setPendingCancelJobId(null);
                                    void cancelJob(job.job_id);
                                }}
                                variant={isCancelPending ? 'danger' : 'ghost'}
                                className="hover:text-red-400"
                            />
                        </div>

                        {job.status === 'processing' && (
                            <div className="space-y-1.5">
                                <div className="flex justify-between text-[11px] font-mono uppercase text-muted-foreground">
                                    <span aria-live="polite">{job.last_message}</span>
                                    <span>{Math.round(displayProgress)}%</span>
                                </div>
                                {downloadDetail && (
                                    <div className="text-[11px] font-mono text-muted-foreground/80" aria-live="polite">
                                        {downloadDetail}
                                    </div>
                                )}
                                <div
                                    className="h-1 bg-foreground/5 rounded-full overflow-hidden"
                                    role="progressbar"
                                    aria-valuenow={Math.round(displayProgress)}
                                    aria-valuemin={0}
                                    aria-valuemax={100}
                                    aria-label={t('jobQueue.progressLabel', { jobId: job.job_id })}
                                >
                                    <div
                                        className="h-full bg-gradient-to-r from-primary to-accent transition-all duration-500 ease-out shadow-md shadow-primary/20"
                                        style={{ width: `${displayProgress}%` }}
                                    />
                                </div>
                            </div>
                        )}

                        {job.status === 'queued' && (
                            <div className="space-y-1">
                                <span className="text-[11px] font-mono text-muted-foreground italic px-2 py-0.5 bg-foreground/5 rounded">
                                    {job.last_message || t('jobQueue.waitingForSlot')}
                                </span>
                                {isCancelPending && (
                                    <div className="text-[11px] font-mono text-red-300/90">
                                        {t('jobQueue.confirmCancelHint')}
                                    </div>
                                )}
                            </div>
                        )}
                        {job.status === 'processing' && isCancelPending && (
                            <div className="mt-2 text-[11px] font-mono text-red-300/90">
                                {t('jobQueue.confirmCancelHint')}
                            </div>
                        )}
                                </>
                            );
                        })()}
                    </div>
                ))}
            </div>
        </section>
            )}
        </div>
    );
};
