import { useEffect, useState } from 'react';

import { adminApi, type AdminOverview, type JobEconomics } from '../api/admin';

type Operation = 'credit' | 'suspend' | 'subscription' | 'retry';

const EMPTY_OVERVIEW: AdminOverview = { users: 0, subscriptions: 0, jobs: 0, failed_jobs: 0, risk_events: 0 };

export function AdminPage() {
  const [overview, setOverview] = useState(EMPTY_OVERVIEW);
  const [economics, setEconomics] = useState<JobEconomics | null>(null);
  const [operation, setOperation] = useState<Operation>('credit');
  const [targetId, setTargetId] = useState('');
  const [amount, setAmount] = useState(0);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void adminApi.getOverview().then(setOverview).catch((value) => setError(value instanceof Error ? value.message : 'Admin özeti yüklenemedi'));
    void adminApi.getEconomics().then(setEconomics).catch((value) => setError(value instanceof Error ? value.message : 'GPU ekonomisi yüklenemedi'));
  }, []);

  async function submit() {
    if (!targetId.trim() || reason.trim().length < 10 || (operation === 'credit' && amount === 0)) {
      setError('Hedef kimliği, sıfır olmayan miktarı ve en az 10 karakterlik nedeni girin.');
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      if (operation === 'credit') {
        const result = await adminApi.adjustCredit(targetId.trim(), amount, reason.trim());
        setMessage(`Yeni kullanılabilir bakiye: ${result.available_credits}`);
      } else if (operation === 'suspend') {
        await adminApi.suspendUser(targetId.trim(), reason.trim());
        setMessage('Kullanıcı askıya alındı.');
      } else if (operation === 'subscription') {
        const result = await adminApi.syncSubscription(targetId.trim(), reason.trim());
        setMessage(`Abonelik durumu: ${result.status}`);
      } else {
        await adminApi.retryJob(targetId.trim(), reason.trim());
        setMessage('Failed job yeniden kuyruğa alındı.');
      }
    } catch (value) {
      setError(value instanceof Error ? value.message : 'Admin işlemi tamamlanamadı');
    } finally {
      setBusy(false);
    }
  }

  const metrics = [
    ['Kullanıcılar', overview.users],
    ['Abonelikler', overview.subscriptions],
    ['Toplam işler', overview.jobs],
    ['Failed işler', overview.failed_jobs],
    ['Risk olayları', overview.risk_events],
  ];
  const targetLabel = operation === 'subscription' ? 'Abonelik ID' : operation === 'retry' ? 'Job ID' : 'Kullanıcı ID';
  const buttonLabel = operation === 'credit' ? 'Krediyi düzelt' : operation === 'suspend' ? 'Kullanıcıyı askıya al' : operation === 'subscription' ? 'Aboneliği senkronize et' : 'Failed job’ı yeniden dene';

  return (
    <section className="space-y-6" aria-labelledby="admin-title">
      <div className="glass-card rounded-2xl border border-primary/20 p-6">
        <h2 id="admin-title" className="text-2xl font-black">Production Admin</h2>
        <p className="mt-2 text-sm text-muted-foreground">Kritik işlemler MFA, zorunlu neden ve append-only audit kaydıyla korunur.</p>
        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {metrics.map(([label, value]) => <div key={String(label)} className="rounded-xl border border-white/10 bg-black/20 p-4"><p className="text-xs text-muted-foreground">{label}</p><strong className="mt-2 block text-2xl">{value}</strong></div>)}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <AdminTable title="Kullanıcılar" rows={(overview.recent_users ?? []).map((row) => [row.id, row.status, row.role])} />
        <AdminTable title="Abonelikler" rows={(overview.recent_subscriptions ?? []).map((row) => [row.id, row.user_id, row.status])} />
        <AdminTable title="İşler / failed işler" rows={(overview.recent_jobs ?? []).map((row) => [row.id, row.user_id, row.status])} />
        <AdminTable title="Risk olayları" rows={(overview.recent_risk_events ?? []).map((row) => [String(row.id), row.signal, String(row.weight)])} />
      </div>

      <div className="glass-card rounded-2xl border border-secondary/20 p-6">
        <h3 className="text-lg font-bold">GPU ekonomisi</h3>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Metric label="Başarı oranı" value={economics ? `${Math.round(economics.success_rate * 100)}%` : '—'} />
          <Metric label="Kaynak saat maliyeti" value={economics ? `$${economics.cost_per_source_hour_usd}` : '—'} />
          <Metric label="Short maliyeti" value={economics ? `$${economics.cost_per_short_usd}` : '—'} />
          <Metric label="Ortalama render" value={economics ? `${Math.round(economics.average_render_seconds)} sn` : '—'} />
        </div>
      </div>

      <div className="glass-card rounded-2xl border border-accent/20 p-6">
        <h3 className="text-lg font-bold">Auditli kritik işlem</h3>
        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <label className="text-sm">İşlem<select aria-label="İşlem" value={operation} onChange={(event) => setOperation(event.target.value as Operation)} className="mt-2 w-full rounded-xl border border-white/10 bg-background p-3"><option value="credit">Kredi düzeltme</option><option value="suspend">Kullanıcı askıya alma</option><option value="subscription">Abonelik manuel sync</option><option value="retry">Failed job retry</option></select></label>
          <label className="text-sm">{targetLabel}<input aria-label={targetLabel} value={targetId} onChange={(event) => setTargetId(event.target.value)} className="mt-2 w-full rounded-xl border border-white/10 bg-background p-3" /></label>
          {operation === 'credit' ? <label className="text-sm">Kredi miktarı<input aria-label="Kredi miktarı" type="number" value={amount} onChange={(event) => setAmount(Number(event.target.value))} className="mt-2 w-full rounded-xl border border-white/10 bg-background p-3" /></label> : null}
          <label className="text-sm md:col-span-2">İşlem nedeni<textarea aria-label="İşlem nedeni" value={reason} onChange={(event) => setReason(event.target.value)} minLength={10} maxLength={500} className="mt-2 min-h-24 w-full rounded-xl border border-white/10 bg-background p-3" /></label>
        </div>
        {error ? <p role="alert" className="mt-4 text-sm text-red-300">{error}</p> : null}
        {message ? <p role="status" className="mt-4 text-sm text-emerald-300">{message}</p> : null}
        <button type="button" disabled={busy} onClick={() => void submit()} className="mt-5 rounded-xl bg-primary px-5 py-3 text-sm font-bold text-primary-foreground disabled:opacity-50">{buttonLabel}</button>
      </div>
    </section>
  );
}

export default AdminPage;

function AdminTable({ title, rows }: { title: string; rows: string[][] }) {
  return <section className="glass-card min-w-0 rounded-2xl border border-white/10 p-5"><h3 className="font-bold">{title}</h3><div className="mt-3 overflow-x-auto"><table className="w-full text-left text-xs"><tbody>{rows.length ? rows.map((row) => <tr key={row.join(':')} className="border-t border-white/5">{row.map((value) => <td key={value} className="max-w-52 truncate px-2 py-3">{value}</td>)}</tr>) : <tr><td className="py-3 text-muted-foreground">Kayıt yok</td></tr>}</tbody></table></div></section>;
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-xl border border-white/10 bg-black/20 p-4"><p className="text-xs text-muted-foreground">{label}</p><strong className="mt-2 block text-xl">{value}</strong></div>;
}
