import { CheckCircle2, AlertTriangle, XCircle, RefreshCw, Zap } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { settingsApi, type AiStatusResponse, type TestAiResponse } from '../../api/client';

interface AiStatusBadgeProps {
  engine: string;
}

export function AiStatusBadge({ engine }: AiStatusBadgeProps) {
  const [statusData, setStatusData] = useState<AiStatusResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<TestAiResponse | null>(null);

  const fetchStatus = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await settingsApi.getAiStatus();
      setStatusData(data);
    } catch {
      setStatusData(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  const handleTestConnection = async () => {
    setIsTesting(true);
    setTestResult(null);
    try {
      const res = await settingsApi.testAi(engine);
      setTestResult(res);
    } catch (err) {
      setTestResult({
        ok: false,
        engine,
        actual_engine: engine,
        message: err instanceof Error ? err.message : 'Bağlantı testi başarısız oldu.',
      });
    } finally {
      setIsTesting(false);
    }
  };

  const currentEngineInfo = statusData?.engines?.[engine];

  let badgeColor = 'bg-slate-800 text-slate-400 border-slate-700';
  let icon = <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />;
  let labelText = 'Kontrol ediliyor...';

  if (!isLoading && statusData) {
    if (engine === 'cloud') {
      if (currentEngineInfo?.configured) {
        badgeColor = 'bg-emerald-950/60 text-emerald-300 border-emerald-800/80';
        icon = <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />;
        labelText = `OpenRouter Hazır (${currentEngineInfo.masked_key ?? 'Anahtar Aktif'})`;
      } else if (currentEngineInfo?.fallback_to_nvidia) {
        badgeColor = 'bg-cyan-950/60 text-cyan-300 border-cyan-800/80';
        icon = <Zap className="w-3.5 h-3.5 text-cyan-400" />;
        labelText = 'NVIDIA NIM Aktif (OpenRouter Fallback)';
      } else {
        badgeColor = 'bg-rose-950/60 text-rose-300 border-rose-800/80';
        icon = <XCircle className="w-3.5 h-3.5 text-rose-400" />;
        labelText = 'API Anahtarı Eksik (Fallback Analiz)';
      }
    } else if (engine === 'nvidia') {
      if (currentEngineInfo?.configured) {
        badgeColor = 'bg-emerald-950/60 text-emerald-300 border-emerald-800/80';
        icon = <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />;
        labelText = `NVIDIA NIM Hazır (${currentEngineInfo.masked_key ?? 'nvapi-***'})`;
      } else {
        badgeColor = 'bg-rose-950/60 text-rose-300 border-rose-800/80';
        icon = <XCircle className="w-3.5 h-3.5 text-rose-400" />;
        labelText = 'NVIDIA_API_KEY Bulunamadı';
      }
    } else if (engine === 'lmstudio') {
      if (currentEngineInfo?.configured) {
        badgeColor = 'bg-purple-950/60 text-purple-300 border-purple-800/80';
        icon = <CheckCircle2 className="w-3.5 h-3.5 text-purple-400" />;
        labelText = `LM Studio (${currentEngineInfo.host ?? 'http://localhost:1234'})`;
      } else {
        badgeColor = 'bg-amber-950/60 text-amber-300 border-amber-800/80';
        icon = <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />;
        labelText = 'LM Studio Yapılandırılmadı';
      }
    } else {
      badgeColor = 'bg-slate-800 text-slate-300 border-slate-700';
      icon = <CheckCircle2 className="w-3.5 h-3.5 text-slate-400" />;
      labelText = 'Kural Bazlı Yerel Fallback Motoru';
    }
  }

  return (
    <div className="flex flex-col gap-1.5 mt-2">
      <div className="flex items-center justify-between gap-2 text-xs">
        <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border text-xs font-medium ${badgeColor}`}>
          {icon}
          <span>{labelText}</span>
        </div>

        <button
          type="button"
          onClick={handleTestConnection}
          disabled={isTesting || isLoading}
          className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-slate-300 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-md transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-3 h-3 ${isTesting ? 'animate-spin' : ''}`} />
          <span>{isTesting ? 'Test Ediliyor...' : 'Bağlantıyı Test Et'}</span>
        </button>
      </div>

      {testResult && (
        <div
          className={`text-xs px-2.5 py-1.5 rounded border ${
            testResult.ok
              ? 'bg-emerald-950/50 text-emerald-200 border-emerald-800'
              : 'bg-rose-950/50 text-rose-200 border-rose-800'
          }`}
        >
          {testResult.ok ? '✅ ' : '❌ '}
          {testResult.message}
        </div>
      )}
    </div>
  );
}
