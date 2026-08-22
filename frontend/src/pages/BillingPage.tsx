import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { AlertTriangle, CreditCard, RefreshCw } from 'lucide-react';

import { billingApi } from '../api/billing';
import type { BillingAccount, BillingPlan, CheckoutCustomer } from '../types/billing';

const emptyCustomer: CheckoutCustomer = {
  name: '', surname: '', email: '', gsm_number: '', identity_number: '',
  address: '', contact_name: '', city: '', country: 'Turkey', zip_code: '',
};

function money(amountMinor: number, currency: string): string {
  return new Intl.NumberFormat('tr-TR', { style: 'currency', currency }).format(amountMinor / 100);
}

function statusLabel(status: string): string {
  return ({ active: 'Aktif', pending: 'Beklemede', past_due: 'Ödeme gecikmiş', cancelled: 'İptal edildi', expired: 'Süresi doldu' } as Record<string, string>)[status] ?? status;
}

function dateLabel(value: string | null): string {
  return value ? new Intl.DateTimeFormat('tr-TR', { dateStyle: 'medium' }).format(new Date(value)) : '—';
}

export function BillingPage() {
  const [account, setAccount] = useState<BillingAccount | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState<BillingPlan | null>(null);
  const [customer, setCustomer] = useState<CheckoutCustomer>(emptyCustomer);
  const [hostedForm, setHostedForm] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setAccount(await billingApi.getAccount());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Faturalandırma hesabı yüklenemedi.');
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function cancelSubscription() {
    setBusy(true);
    setError(null);
    try {
      await billingApi.cancel();
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Abonelik iptal edilemedi.');
    } finally {
      setBusy(false);
    }
  }

  async function startCheckout(event: FormEvent) {
    event.preventDefault();
    if (!selectedPlan) return;
    setBusy(true);
    setError(null);
    try {
      const session = await billingApi.checkout(selectedPlan.code, 'monthly', customer);
      setHostedForm(session.checkout_form_content);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Ödeme oturumu başlatılamadı.');
    } finally {
      setBusy(false);
    }
  }

  async function changePlan(plan: BillingPlan) {
    if (!account?.subscription || account.subscription.plan.code === plan.code) return;
    setBusy(true);
    setError(null);
    try {
      const interval = account.subscription.interval === 'yearly' ? 'yearly' : 'monthly';
      await billingApi.changePlan(plan.code, interval);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Plan değiştirilemedi.');
    } finally {
      setBusy(false);
    }
  }

  if (!account && !error) {
    return <main className="glass-card p-8 text-sm text-muted-foreground">Faturalandırma hesabı yükleniyor…</main>;
  }

  return (
    <main className="space-y-6" aria-label="Faturalandırma hesabı">
      <section className="glass-card rounded-3xl border border-primary/20 p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div><p className="font-mono text-xs uppercase tracking-[0.2em] text-primary">Plan ve kullanım</p><h2 className="mt-2 text-3xl font-bold">Faturalandırma hesabı</h2></div>
          <button type="button" onClick={() => void load()} className="inline-flex items-center gap-2 rounded-xl border border-white/10 px-4 py-2 text-sm"><RefreshCw className="h-4 w-4" /> Yenile</button>
        </div>
        {error ? <p role="alert" className="mt-4 rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{error}</p> : null}
        {account?.subscription?.status === 'past_due' ? <div className="mt-5 flex gap-3 rounded-2xl border border-amber-500/40 bg-amber-500/10 p-4 text-amber-100"><AlertTriangle className="h-5 w-5 shrink-0" /><div><strong>Ödeme gecikmiş</strong><p className="mt-1 text-sm">Üyelik durumu backend ve ödeme sağlayıcısından yeniden doğrulandı. Ödeme bilgilerinizi güncelleyin.</p></div></div> : null}
      </section>

      {account ? <>
        <section className="grid gap-4 md:grid-cols-4">
          <Metric label="Mevcut plan" value={account.subscription?.plan.name ?? 'Ücretsiz'} note={account.subscription ? statusLabel(account.subscription.status) : 'Aktif abonelik yok'} />
          <Metric label="Kalan compute kredisi" value={String(account.usage.compute_credits_available)} note={`${account.usage.compute_credits_reserved} kredi rezerve`} />
          <Metric label="Dönem kaynak kullanımı" value={`${Math.round(account.usage.current_period_source_seconds / 60)} dk`} note={`İş başına sınır ${Math.round(account.usage.source_seconds_per_job_limit / 60)} dk`} />
          <Metric label="Dönem compute kullanımı" value={String(account.usage.compute_credits_used)} note={`Dönem sonu ${dateLabel(account.subscription?.period_end ?? null)}`} />
        </section>

        <section className="glass-card rounded-3xl border border-white/10 p-6">
          <div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="text-xl font-bold">Planı yönet</h3><p className="mt-1 text-sm text-muted-foreground">Fiyatlar ve haklar backend plan kataloğundan gelir.</p></div>{account.subscription && account.subscription.status !== 'cancelled' ? <button disabled={busy} type="button" onClick={() => void cancelSubscription()} className="rounded-xl border border-red-400/40 px-4 py-2 text-sm text-red-200 disabled:opacity-50">Aboneliği iptal et</button> : null}</div>
          <div className="mt-5 grid gap-4 md:grid-cols-3">{account.plans.map((plan) => { const current = account.subscription?.plan.code === plan.code; return <button disabled={busy || current} type="button" key={plan.code} onClick={() => account.subscription ? void changePlan(plan) : setSelectedPlan(plan)} className="rounded-2xl border border-white/10 p-5 text-left hover:border-primary/50 disabled:cursor-default disabled:opacity-70"><strong className="text-lg">{plan.name}</strong><p className="mt-2 text-2xl font-bold text-primary">{money(plan.monthly_price_minor, plan.currency)}<span className="text-xs font-normal text-muted-foreground"> / ay</span></p><p className="mt-3 text-sm text-muted-foreground">{plan.monthly_compute_credits} compute kredisi · {plan.max_source_minutes_per_job} dk/iş</p><span className="mt-4 inline-block text-sm font-semibold text-primary">{current ? 'Mevcut plan' : 'Bu plana geç'}</span></button>; })}</div>
        </section>

        {selectedPlan ? <CheckoutForm plan={selectedPlan} customer={customer} setCustomer={setCustomer} busy={busy} onSubmit={startCheckout} onClose={() => { setSelectedPlan(null); setHostedForm(null); }} hostedForm={hostedForm} /> : null}

        <section className="glass-card rounded-3xl border border-white/10 p-6"><h3 className="text-xl font-bold">Ödeme geçmişi</h3>{account.payments.length ? <div className="mt-4 overflow-x-auto"><table className="w-full text-left text-sm"><thead className="text-muted-foreground"><tr><th className="py-2">Tarih</th><th>Durum</th><th className="text-right">Tutar</th></tr></thead><tbody>{account.payments.map((payment) => <tr key={payment.id} className="border-t border-white/10"><td className="py-3">{dateLabel(payment.created_at)}</td><td>{statusLabel(payment.status)}</td><td className="text-right font-mono">{money(payment.amount_minor, payment.currency)}</td></tr>)}</tbody></table></div> : <p className="mt-3 text-sm text-muted-foreground">Henüz ödeme kaydı yok.</p>}</section>
      </> : null}
    </main>
  );
}

function Metric({ label, value, note }: { label: string; value: string; note: string }) {
  return <article className="glass-card rounded-2xl border border-white/10 p-5"><p className="text-xs uppercase tracking-wider text-muted-foreground">{label}</p><p className="mt-2 text-2xl font-bold">{value}</p><p className="mt-2 text-xs text-muted-foreground">{note}</p></article>;
}

function CheckoutForm({ plan, customer, setCustomer, busy, onSubmit, onClose, hostedForm }: { plan: BillingPlan; customer: CheckoutCustomer; setCustomer: (customer: CheckoutCustomer) => void; busy: boolean; onSubmit: (event: FormEvent) => void; onClose: () => void; hostedForm: string | null }) {
  const fields: Array<[keyof CheckoutCustomer, string, string]> = [['name', 'Ad', 'text'], ['surname', 'Soyad', 'text'], ['email', 'E-posta', 'email'], ['gsm_number', 'Telefon', 'tel'], ['identity_number', 'Kimlik numarası', 'text'], ['contact_name', 'Adres iletişim adı', 'text'], ['address', 'Adres', 'text'], ['city', 'Şehir', 'text'], ['country', 'Ülke', 'text'], ['zip_code', 'Posta kodu', 'text']];
  return <section className="glass-card rounded-3xl border border-primary/30 p-6"><div className="flex justify-between gap-4"><div><h3 className="text-xl font-bold">{plan.name} ödeme adımı</h3><p className="mt-1 text-sm text-muted-foreground">Ödeme tamamlandıktan sonra üyelik backend’den yeniden doğrulanır.</p></div><button type="button" onClick={onClose} className="text-sm text-muted-foreground">Kapat</button></div>{hostedForm ? <iframe title="iyzico güvenli ödeme formu" sandbox="allow-forms allow-scripts" srcDoc={hostedForm} className="mt-5 min-h-[620px] w-full rounded-2xl border-0 bg-white" /> : <form onSubmit={onSubmit} className="mt-5 grid gap-4 md:grid-cols-2">{fields.map(([key, label, type]) => <label key={key} className={key === 'address' ? 'md:col-span-2' : ''}><span className="mb-1 block text-xs text-muted-foreground">{label}</span><input required={key !== 'zip_code'} type={type} value={customer[key] ?? ''} onChange={(event) => setCustomer({ ...customer, [key]: event.target.value })} className="w-full rounded-xl border border-white/10 bg-black/20 px-3 py-2" /></label>)}<button disabled={busy} type="submit" className="md:col-span-2 inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-5 py-3 font-semibold text-primary-foreground disabled:opacity-50"><CreditCard className="h-4 w-4" /> Güvenli ödemeye geç</button></form>}</section>;
}
