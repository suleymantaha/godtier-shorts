import React, { useEffect, useMemo, useRef, useState } from 'react';
import type { AppErrorCode } from '../api/errors';
import { useAuthRuntimeStore } from '../auth/runtime';
import { useJobStore } from '../store/useJobStore';
import type { LogEntry, WsStatus } from '../types';
import { Expand, ShieldCheck, Terminal, X } from 'lucide-react';

const WS_STATUS_LABELS: Record<WsStatus, string> = {
    connected: 'WS:CONNECTED',
    connecting: 'WS:CONNECTING',
    reconnecting: 'WS:RECONNECTING',
    disconnected: 'WS:DISCONNECTED',
};

function resolveAuthStatusLabel(backendAuthStatus: 'fresh' | 'paused' | 'refreshing', pauseReason: AppErrorCode | null): string {
    if (backendAuthStatus === 'refreshing') {
        return 'AUTH:REFRESHING';
    }
    if (backendAuthStatus === 'paused') {
        return pauseReason === 'token_expired'
            ? 'AUTH:TOKEN-EXPIRED'
            : 'AUTH:PAUSED';
    }
    return 'AUTH:READY';
}

function renderLogEntries(logs: LogEntry[]) {
    return logs.map((log, index) => (
        <div key={`${log.timestamp}-${log.message}-${index}`} className="flex min-w-0 max-w-full items-start gap-3 overflow-hidden animate-in fade-in slide-in-from-left-2 duration-500">
            <span className="shrink-0 text-muted-foreground whitespace-nowrap">[{log.timestamp}]</span>
            <span
                className={`min-w-0 flex-1 overflow-hidden break-words whitespace-pre-wrap leading-relaxed ${log.progress === -1 ? 'text-red-400' : 'text-primary/80'}`}
            >
                {log.progress === -1 ? '!!!' : '>>>'} {log.message}
            </span>
        </div>
    ));
}

export const HoloTerminal: React.FC<{ compact?: boolean }> = ({ compact = false }) => {
    const { jobs, logs, wsStatus } = useJobStore();
    const backendAuthStatus = useAuthRuntimeStore((state) => state.backendAuthStatus);
    const pauseReason = useAuthRuntimeStore((state) => state.pauseReason);
    const [isLogsExpanded, setIsLogsExpanded] = useState(false);
    
    // Most recent log/job determines progress and status
    const lastLog = logs[logs.length - 1];
    const activeJob = jobs.find(j => j.status === 'processing');
    
    const progress = activeJob ? activeJob.progress : (lastLog ? lastLog.progress : 0);
    const status = activeJob ? activeJob.last_message : (lastLog ? lastLog.message : 'READY');
    const authStatusLabel = resolveAuthStatusLabel(backendAuthStatus, pauseReason);
    const wsStatusLabel = WS_STATUS_LABELS[wsStatus];
    const panelScrollRef = useRef<HTMLDivElement>(null);
    const expandedScrollRef = useRef<HTMLDivElement>(null);
    const visibleLogs = useMemo(() => (compact ? logs.slice(-3) : logs), [compact, logs]);

    const wsStatusTone = wsStatus === 'connected'
        ? 'border-emerald-400/30 bg-emerald-500/15 text-emerald-100'
        : wsStatus === 'disconnected'
            ? 'border-red-400/30 bg-red-500/15 text-red-100'
            : 'border-yellow-400/30 bg-yellow-500/15 text-yellow-100';
    const authStatusTone = backendAuthStatus === 'fresh'
        ? 'border-emerald-400/30 bg-emerald-500/15 text-emerald-100'
        : backendAuthStatus === 'refreshing'
            ? 'border-yellow-400/30 bg-yellow-500/15 text-yellow-100'
            : 'border-amber-400/30 bg-amber-500/15 text-amber-100';

    useEffect(() => {
        if (panelScrollRef.current) {
            panelScrollRef.current.scrollTop = panelScrollRef.current.scrollHeight;
        }
    }, [visibleLogs]);

    useEffect(() => {
        if (isLogsExpanded && expandedScrollRef.current) {
            expandedScrollRef.current.scrollTop = expandedScrollRef.current.scrollHeight;
        }
    }, [isLogsExpanded, logs]);

    useEffect(() => {
        if (!compact && isLogsExpanded) {
            setIsLogsExpanded(false);
        }
    }, [compact, isLogsExpanded]);

    useEffect(() => {
        if (!isLogsExpanded) {
            return;
        }

        const onKeyDown = (event: KeyboardEvent) => {
            if (event.key === 'Escape') {
                setIsLogsExpanded(false);
            }
        };

        window.addEventListener('keydown', onKeyDown);
        return () => window.removeEventListener('keydown', onKeyDown);
    }, [isLogsExpanded]);

    return (
        <>
            <div className={`flex h-full w-full max-w-full min-w-0 flex-col overflow-hidden ${compact ? 'min-h-[160px]' : 'min-h-[250px]'}`}>
                <div className={`border-b border-white/5 flex min-w-0 items-center justify-between gap-3 bg-white/[0.02] ${compact ? 'px-3.5 py-2' : 'px-4 py-3'}`}>
                    <div className="flex min-w-0 flex-1 items-center gap-2 overflow-hidden">
                        <Terminal className="h-4 w-4 shrink-0 text-primary" />
                        <span className="truncate text-xs font-mono font-bold uppercase tracking-[0.2em] holo-text text-primary">
                            {compact ? 'Core Logs' : 'God-Tier Core Logs'}
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
                        <span
                            className="min-w-0 max-w-full truncate text-[11px] font-mono text-muted-foreground"
                            title={status}
                        >
                            {status}
                        </span>
                        {compact && (
                            <button
                                type="button"
                                onClick={() => setIsLogsExpanded(true)}
                                className="inline-flex items-center gap-1 rounded-lg border border-white/15 bg-white/5 px-2.5 py-1 text-[10px] font-mono uppercase tracking-wider text-foreground transition-colors hover:bg-white/10"
                                aria-label="Expand Logs"
                            >
                                <Expand className="h-3 w-3" />
                                Expand Logs
                            </button>
                        )}
                    </div>
                </div>

                <div className="flex min-w-0 flex-1 items-center gap-2 overflow-hidden">
                    <div
                        ref={panelScrollRef}
                        className={`flex-1 min-w-0 overflow-x-hidden overflow-y-auto font-mono text-[11px] space-y-2 scrollbar-hide selection:bg-primary/20 ${compact ? 'p-2.5' : 'p-4'}`}
                    >
                        {renderLogEntries(visibleLogs)}
                        {visibleLogs.length === 0 && (
                            <div className="h-full flex flex-col items-center justify-center text-muted-foreground opacity-20 select-none">
                                <ShieldCheck className="w-12 h-12 mb-2" />
                                <p>Waiting for system handshake...</p>
                            </div>
                        )}
                    </div>
                </div>
                <div
                    className={`border-t border-white/5 bg-black/40 ${compact ? 'p-2.5' : 'p-4'}`}
                >
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
            {compact && isLogsExpanded && (
                <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm p-4 md:p-6 flex items-center justify-center">
                    <div
                        role="dialog"
                        aria-modal="true"
                        aria-label="Core logs history"
                        className="w-full max-w-4xl max-h-[90vh] h-full glass-card border-white/15 overflow-hidden flex flex-col"
                    >
                        <div className="border-b border-white/10 px-4 py-3 flex items-center justify-between gap-3 bg-white/[0.02]">
                            <div className="flex items-center gap-2 min-w-0">
                                <Terminal className="h-4 w-4 text-primary shrink-0" />
                                <span className="truncate text-xs font-mono font-bold uppercase tracking-[0.2em] text-primary">
                                    Core Logs History
                                </span>
                            </div>
                            <div className="flex items-center gap-2">
                                <span className={`inline-flex items-center rounded-full px-2 py-1 text-[10px] font-mono uppercase tracking-wider ${wsStatusTone}`}>
                                    {wsStatusLabel}
                                </span>
                                <span className={`inline-flex items-center rounded-full px-2 py-1 text-[10px] font-mono uppercase tracking-wider ${authStatusTone}`}>
                                    {authStatusLabel}
                                </span>
                                <button
                                    type="button"
                                    onClick={() => setIsLogsExpanded(false)}
                                    className="inline-flex items-center gap-1 rounded-lg border border-white/15 bg-white/5 px-2.5 py-1 text-[10px] font-mono uppercase tracking-wider text-foreground transition-colors hover:bg-white/10"
                                    aria-label="Close expanded logs"
                                >
                                    <X className="h-3 w-3" />
                                    Close
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
                                    <p>Waiting for system handshake...</p>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </>
    );
};
