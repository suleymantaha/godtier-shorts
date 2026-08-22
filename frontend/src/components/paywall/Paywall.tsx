import { LockKeyhole } from 'lucide-react';
import { PlanCard } from './PlanCard';

const lockedFeatures = ['1080p export', 'Smart tracking', 'Batch render', 'Download'];

export function Paywall({ candidateCount }: { candidateCount: number }) {
  return (
    <section aria-label="Üretim seçenekleri" className="glass-card grid gap-6 rounded-3xl border border-primary/30 p-6 md:grid-cols-[1.2fr_0.8fr]">
      <div>
        <div className="flex items-center gap-2 text-primary"><LockKeyhole className="h-5 w-5" /><p className="font-mono text-xs uppercase tracking-[0.2em]">Üretim kilidi</p></div>
        <h2 className="mt-4 text-2xl font-bold text-foreground">{candidateCount} güçlü Short bulundu</h2>
        <p className="mt-3 text-sm leading-6 text-muted-foreground">Analiz ve adaylar ücretsiz. Ağır GPU kullanan üretim özellikleri ücretli planda açılır.</p>
        <div className="mt-5 flex flex-wrap gap-2">{lockedFeatures.map((feature) => <span key={feature} className="rounded-full border border-white/10 px-3 py-1 text-xs text-foreground">{feature}</span>)}</div>
        <a href="/?tab=config" className="mt-6 inline-flex rounded-xl bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground">Üretim seçeneklerini aç</a>
      </div>
      <PlanCard name="Creator" note="Aktif içerik üreticileri için önerilen plan." highlighted features={['1080p render', 'Smart tracking', 'Batch üretim', 'Social publish']} />
    </section>
  );
}
