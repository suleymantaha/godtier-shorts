import { PlanCard } from '../components/paywall/PlanCard';

const plans = [
  { name: 'Starter', note: 'Düzenli üretime başlayanlar için.', features: ['Sınırlı kaynak saati', '1080p Short üretimi'] },
  { name: 'Creator', note: 'Aktif içerik üreticileri için ana paket.', features: ['Daha yüksek kaynak kotası', 'Batch render', 'Smart tracking', 'Social publish'], highlighted: true },
  { name: 'Pro', note: 'Yüksek hacimli ekipler için.', features: ['Priority queue', 'Daha uzun saklama', 'Yüksek üretim kotası'] },
];

export function PricingPage() {
  return (
    <section id="pricing" aria-labelledby="pricing-title" className="mx-auto max-w-6xl py-16">
      <div className="text-center">
        <p className="font-mono text-xs uppercase tracking-[0.25em] text-primary">Planlar</p>
        <h2 id="pricing-title" className="mt-3 text-3xl font-bold text-foreground">GPU değil, yayınlanabilir Short satın al</h2>
        <p className="mx-auto mt-3 max-w-2xl text-sm text-muted-foreground">Güncel fiyat ve dönem seçenekleri ödeme adımından önce gösterilir; gizli ücret yoktur.</p>
      </div>
      <div className="mt-8 grid gap-5 md:grid-cols-3">{plans.map((plan) => <PlanCard key={plan.name} {...plan} />)}</div>
    </section>
  );
}
