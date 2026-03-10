import React, { useEffect, useRef } from 'react';
import { useJobStore } from '../store/useJobStore';
import { Terminal, ShieldCheck } from 'lucide-react';

export const HoloTerminal: React.FC = () => {
    const { logs, jobs } = useJobStore();
    
    // Most recent log/job determines progress and status
    const lastLog = logs[logs.length - 1];
    const activeJob = jobs.find(j => j.status === 'processing');
    
    const progress = activeJob ? activeJob.progress : (lastLog ? lastLog.progress : 0);
    const status = activeJob ? activeJob.last_message : (lastLog ? lastLog.message : 'READY');
    const scrollRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [logs]);

    return (
        <div className="flex flex-col h-full min-h-[250px] overflow-hidden">
            <div className="px-4 py-3 border-b border-white/5 flex items-center justify-between bg-white/[0.02]">
                <div className="flex items-center gap-2">
                    <Terminal className="w-4 h-4 text-primary" />
                    <span className="text-xs font-mono font-bold uppercase tracking-[0.2em] holo-text text-primary">God-Tier Core Logs</span>
                </div>
                <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full animate-pulse ${progress === 100 ? 'bg-green-500' : progress === -1 ? 'bg-red-500' : 'bg-primary'}`} />
                    <span className="text-[11px] font-mono text-muted-foreground">{status}</span>
                </div>
            </div>

            <div
                ref={scrollRef}
                className="flex-1 p-4 font-mono text-[11px] overflow-y-auto space-y-2 scrollbar-hide selection:bg-primary/20"
            >
                {logs.map((log, i) => (
                    <div key={i} className="flex gap-4 animate-in fade-in slide-in-from-left-2 duration-500">
                        <span className="text-muted-foreground whitespace-nowrap">[{log.timestamp}]</span>
                        <span className={log.progress === -1 ? 'text-red-400' : 'text-primary/80'}>
                            {log.progress === -1 ? '!!!' : '>>>'} {log.message}
                        </span>
                    </div>
                ))}
                {logs.length === 0 && (
                    <div className="h-full flex flex-col items-center justify-center text-muted-foreground opacity-20 select-none">
                        <ShieldCheck className="w-12 h-12 mb-2" />
                        <p>Waiting for system handshake...</p>
                    </div>
                )}
            </div>

            <div className="p-4 border-t border-white/5 bg-black/40">
                <div className="flex justify-between text-[11px] font-mono mb-2">
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
