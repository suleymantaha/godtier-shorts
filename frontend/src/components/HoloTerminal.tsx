import React, { useEffect, useMemo, useRef } from 'react';
import { useJobStore } from '../store/useJobStore';
import { Terminal, ShieldCheck } from 'lucide-react';

export const HoloTerminal: React.FC<{ compact?: boolean }> = ({ compact = false }) => {
    const { logs, jobs } = useJobStore();
    
    // Most recent log/job determines progress and status
    const lastLog = logs[logs.length - 1];
    const activeJob = jobs.find(j => j.status === 'processing');
    
    const progress = activeJob ? activeJob.progress : (lastLog ? lastLog.progress : 0);
    const status = activeJob ? activeJob.last_message : (lastLog ? lastLog.message : 'READY');
    const scrollRef = useRef<HTMLDivElement>(null);
    const visibleLogs = useMemo(() => (compact ? logs.slice(-3) : logs), [compact, logs]);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [visibleLogs]);

    return (
        <div className={`flex h-full w-full max-w-full min-w-0 flex-col overflow-hidden ${compact ? 'min-h-[160px]' : 'min-h-[250px]'}`}>
            <div className={`border-b border-white/5 flex min-w-0 items-center justify-between gap-3 bg-white/[0.02] ${compact ? 'px-3.5 py-2' : 'px-4 py-3'}`}>
                <div className="flex min-w-0 flex-1 items-center gap-2 overflow-hidden">
                    <Terminal className="h-4 w-4 shrink-0 text-primary" />
                    <span className="truncate text-xs font-mono font-bold uppercase tracking-[0.2em] holo-text text-primary">
                        {compact ? 'Core Logs' : 'God-Tier Core Logs'}
                    </span>
                </div>
                <div className="flex min-w-0 flex-1 items-center justify-end gap-2 overflow-hidden">
                    <div className={`h-2 w-2 shrink-0 rounded-full animate-pulse ${progress === 100 ? 'bg-green-500' : progress === -1 ? 'bg-red-500' : 'bg-primary'}`} />
                    <span
                        className="min-w-0 max-w-full truncate text-[11px] font-mono text-muted-foreground"
                        title={status}
                    >
                        {status}
                    </span>
                </div>
            </div>

            <div
                ref={scrollRef}
                className={`flex-1 min-w-0 overflow-x-hidden overflow-y-auto font-mono text-[11px] space-y-2 scrollbar-hide selection:bg-primary/20 ${compact ? 'p-2.5' : 'p-4'}`}
            >
                {visibleLogs.map((log, i) => (
                    <div key={i} className="flex min-w-0 max-w-full items-start gap-3 overflow-hidden animate-in fade-in slide-in-from-left-2 duration-500">
                        <span className="shrink-0 text-muted-foreground whitespace-nowrap">[{log.timestamp}]</span>
                        <span
                            className={`min-w-0 flex-1 overflow-hidden break-words whitespace-pre-wrap leading-relaxed ${log.progress === -1 ? 'text-red-400' : 'text-primary/80'}`}
                        >
                            {log.progress === -1 ? '!!!' : '>>>'} {log.message}
                        </span>
                    </div>
                ))}
                {visibleLogs.length === 0 && (
                    <div className="h-full flex flex-col items-center justify-center text-muted-foreground opacity-20 select-none">
                        <ShieldCheck className="w-12 h-12 mb-2" />
                        <p>Waiting for system handshake...</p>
                    </div>
                )}
            </div>

            <div className={`border-t border-white/5 bg-black/40 ${compact ? 'p-2.5' : 'p-4'}`}>
                <div className={`flex justify-between font-mono ${compact ? 'mb-1.5 text-[10px]' : 'mb-2 text-[11px]'}`}>
                    <span className="text-muted-foreground">SYSTEM PROGRESS</span>
                    <span className="text-primary" aria-live="polite">{Math.max(0, progress)}%</span>
                </div>
                <div
                    className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden"
                    role="progressbar"
                    aria-valuenow={Math.max(0, progress)}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-label="Sistem ilerlemesi"
                >
                    <div
                        className="h-full bg-gradient-to-r from-primary via-secondary to-accent transition-all duration-1000 ease-out shadow-[0_0_10px_rgba(0,242,255,0.5)]"
                        style={{ width: `${Math.max(0, progress)}%` }}
                    />
                </div>
            </div>
        </div>
    );
};
