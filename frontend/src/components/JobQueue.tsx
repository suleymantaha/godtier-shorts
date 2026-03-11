import { useJobStore } from '../store/useJobStore';
import { Loader2, Clock, XCircle, AlertCircle } from 'lucide-react';
import { IconButton } from './ui/IconButton';

export const JobQueue: React.FC = () => {
    const { jobs, cancelJob, lastError, clearError } = useJobStore();

    const activeOrQueuedJobs = jobs.filter(j => ['queued', 'processing'].includes(j.status));

    if (activeOrQueuedJobs.length === 0 && !lastError) return null;

    return (
        <div className="space-y-4">
            {lastError && (
                <div className="glass-card p-4 flex items-center justify-between gap-3 border-red-500/30 bg-red-500/5 animate-in fade-in slide-in-from-bottom-2">
                    <div className="flex items-center gap-2 text-red-400 text-sm">
                        <AlertCircle className="w-4 h-4 shrink-0" />
                        <span>{lastError}</span>
                    </div>
                    <IconButton label="Kapat" icon={<XCircle className="w-4 h-4" />} onClick={clearError} className="hover:text-red-300" />
                </div>
            )}
            {activeOrQueuedJobs.length > 0 && (
        <section className="glass-card p-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <h2 className="text-sm uppercase tracking-[0.2em] font-bold mb-4 flex items-center gap-2 text-primary holo-text">
                <Clock className="w-4 h-4" />
                ORBITAL MISSION QUEUE
            </h2>

            <div className="space-y-4">
                {activeOrQueuedJobs.map((job) => (
                    <div key={job.job_id} className="relative group border-b border-border pb-4 last:border-0 last:pb-0">
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
                                label="Isi iptal et"
                                icon={<XCircle className="w-4 h-4" />}
                                onClick={() => cancelJob(job.job_id)}
                                className="hover:text-red-400"
                            />
                        </div>

                        {job.status === 'processing' && (
                            <div className="space-y-1.5">
                                <div className="flex justify-between text-[11px] font-mono uppercase text-muted-foreground">
                                    <span aria-live="polite">{job.last_message}</span>
                                    <span>{Math.round(job.progress)}%</span>
                                </div>
                                <div
                                    className="h-1 bg-foreground/5 rounded-full overflow-hidden"
                                    role="progressbar"
                                    aria-valuenow={Math.round(job.progress)}
                                    aria-valuemin={0}
                                    aria-valuemax={100}
                                    aria-label={`${job.job_id} islemi`}
                                >
                                    <div
                                        className="h-full bg-gradient-to-r from-primary to-accent transition-all duration-500 ease-out shadow-md shadow-primary/20"
                                        style={{ width: `${job.progress}%` }}
                                    />
                                </div>
                            </div>
                        )}

                        {job.status === 'queued' && (
                            <span className="text-[11px] font-mono text-muted-foreground uppercase italic px-2 py-0.5 bg-foreground/5 rounded">
                                Waiting for GPU clearance...
                            </span>
                        )}
                    </div>
                ))}
            </div>
        </section>
            )}
        </div>
    );
};
