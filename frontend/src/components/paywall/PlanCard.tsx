import { Check } from 'lucide-react';

export function PlanCard({ features, highlighted = false, name, note }: {
  features: string[];
  highlighted?: boolean;
  name: string;
  note: string;
}) {
  return (
    <article className={`rounded-3xl border p-6 ${highlighted ? 'border-primary bg-primary/10 shadow-xl shadow-primary/10' : 'border-white/10 bg-black/20'}`}>
      {highlighted ? <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">Önerilen</p> : null}
      <h3 className="mt-2 text-xl font-bold text-foreground">{name}</h3>
      <p className="mt-2 text-sm text-muted-foreground">{note}</p>
      <ul className="mt-5 space-y-3">
        {features.map((feature) => <li key={feature} className="flex gap-2 text-sm text-foreground"><Check className="h-4 w-4 shrink-0 text-primary" />{feature}</li>)}
      </ul>
    </article>
  );
}
