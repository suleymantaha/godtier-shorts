import { ArrowRight, Captions, ScanSearch, WandSparkles } from 'lucide-react';
import { useState } from 'react';
import { PENDING_PREVIEW_URL_KEY } from '../marketing/funnel';
import { PricingPage } from './PricingPage';

const steps = [
  { icon: ScanSearch, title: 'Videonu tara', text: 'YouTube linkini güvenli analiz akışına gönder.' },
  { icon: Captions, title: 'Güçlü anları gör', text: 'Hook, viral score, transcript ve zaman damgalarını incele.' },
  { icon: WandSparkles, title: 'Short üret', text: 'Ücretli planda smart tracking, altyazı ve 1080p çıktıyı aç.' },
];

function ProductSteps() {
  return <section className="mx-auto grid max-w-6xl gap-4 py-12 md:grid-cols-3">{steps.map(({ icon: Icon, text, title }) => <article data-testid="product-step" key={title} className="glass-card rounded-2xl p-5"><Icon className="h-5 w-5 text-primary" /><h2 className="mt-4 text-lg text-foreground">{title}</h2><p className="mt-2 text-sm leading-6 text-muted-foreground">{text}</p></article>)}</section>;
}

export function LandingPage({ onStart = () => window.location.assign('/sign-up') }: { onStart?: () => void }) {
  const [url, setUrl] = useState('');
  function submit(event: React.FormEvent) {
    event.preventDefault();
    window.sessionStorage.setItem(PENDING_PREVIEW_URL_KEY, url.trim());
    onStart();
  }
  return (
    <main className="mx-auto w-full max-w-7xl px-2">
      <nav className="flex items-center justify-between py-4"><strong className="text-lg text-foreground">GodTier Shorts</strong><a href="/sign-in" className="text-sm text-primary">Giriş yap</a></nav>
      <section className="mx-auto max-w-4xl py-16 text-center sm:py-24">
        <p className="font-mono text-xs uppercase tracking-[0.3em] text-primary">AI video repurposing</p>
        <h1 className="mt-5 text-4xl font-extrabold leading-tight text-foreground sm:text-6xl">Uzun videondan yayınlanabilir Short’lar çıkar</h1>
        <p className="mx-auto mt-5 max-w-2xl text-base leading-7 text-muted-foreground">Önce güçlü anları ücretsiz gör. Yalnız üretime geçtiğinde GPU kullanan özellikleri aç.</p>
        <form onSubmit={submit} className="mx-auto mt-8 flex max-w-3xl flex-col gap-3 rounded-2xl border border-primary/30 bg-black/30 p-3 sm:flex-row">
          <label htmlFor="landing-youtube-url" className="sr-only">YouTube video URL</label>
          <input id="landing-youtube-url" type="url" required value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://youtube.com/watch?v=..." className="min-w-0 flex-1 rounded-xl bg-background/80 px-4 py-3 text-foreground" />
          <button className="inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-5 py-3 font-semibold text-primary-foreground">YouTube linkini yapıştır <ArrowRight className="h-4 w-4" /></button>
        </form>
      </section>
      <ProductSteps />
      <section className="grid gap-5 rounded-3xl border border-white/10 bg-black/20 p-6 md:grid-cols-2"><div><p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Before</p><p className="mt-3 text-xl text-foreground">60 dakikalık ham konuşma</p></div><div><p className="text-xs uppercase tracking-[0.2em] text-primary">After</p><p className="mt-3 text-xl text-foreground">Hook’u, altyazısı ve kadrajı hazır Short’lar</p></div></section>
      <PricingPage />
    </main>
  );
}
