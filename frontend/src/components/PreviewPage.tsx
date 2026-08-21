import { useState } from 'react';
import { Sparkles } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { previewApi } from '../api/preview';
import type { PreviewAnalyzeResponse, ViralCandidate } from '../types/preview';


function timestamp(seconds: number): string {
  const whole = Math.max(0, Math.floor(seconds));
  return `${String(Math.floor(whole / 60)).padStart(2, '0')}:${String(whole % 60).padStart(2, '0')}`;
}

function CandidateCard({ candidate, fallbackTitle }: { candidate: ViralCandidate; fallbackTitle: string }) {
  return (
    <article className="rounded-2xl border border-primary/20 bg-black/20 p-5">
      <div className="flex items-center justify-between gap-3">
        <h3 className="font-semibold text-foreground">{candidate.ui_title || candidate.hook_text || fallbackTitle}</h3>
        {typeof candidate.viral_score === 'number' ? (
          <span className="rounded-full bg-primary/10 px-3 py-1 text-xs text-primary">{candidate.viral_score}/100</span>
        ) : null}
      </div>
      <p className="mt-3 font-mono text-xs text-muted-foreground">
        {timestamp(candidate.start_time)} – {timestamp(candidate.end_time)}
      </p>
      {candidate.hook_text ? <p className="mt-3 text-sm text-muted-foreground">{candidate.hook_text}</p> : null}
    </article>
  );
}

export function PreviewPage() {
  const { t } = useTranslation();
  const [url, setUrl] = useState('');
  const [result, setResult] = useState<PreviewAnalyzeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      setResult(await previewApi.analyze(url.trim()));
    } catch (caught) {
      setResult(null);
      setError(caught instanceof Error ? caught.message : t('previewPage.error'));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto max-w-5xl space-y-6">
      <section className="glass-card rounded-3xl border border-primary/20 p-6 sm:p-8">
        <div className="flex items-center gap-3 text-primary">
          <Sparkles className="h-5 w-5" aria-hidden="true" />
          <p className="font-mono text-xs uppercase tracking-[0.2em]">{t('previewPage.eyebrow')}</p>
        </div>
        <h2 className="mt-4 text-2xl font-bold text-foreground">{t('previewPage.title')}</h2>
        <p className="mt-2 text-sm text-muted-foreground">{t('previewPage.description')}</p>
        <form onSubmit={submit} className="mt-6 flex flex-col gap-3 sm:flex-row">
          <label className="sr-only" htmlFor="preview-url">{t('previewPage.urlLabel')}</label>
          <input
            id="preview-url"
            type="url"
            required
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="https://youtube.com/watch?v=..."
            className="min-w-0 flex-1 rounded-xl border border-border bg-background/60 px-4 py-3 text-sm text-foreground"
          />
          <button
            type="submit"
            disabled={loading}
            className="rounded-xl bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground disabled:opacity-60"
          >
            {loading ? t('previewPage.loading') : t('previewPage.submit')}
          </button>
        </form>
        {error ? <p role="alert" className="mt-4 text-sm text-red-300">{error}</p> : null}
      </section>

      {result ? (
        <section aria-label={t('previewPage.resultsLabel')} className="space-y-4">
          <div>
            <h2 className="text-xl font-semibold text-foreground">{result.source.title}</h2>
            <p className="mt-1 text-xs text-muted-foreground">{t('previewPage.resultMeta', { count: result.candidates.length })}</p>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            {result.candidates.map((candidate) => (
              <CandidateCard key={`${candidate.start_time}-${candidate.end_time}`} candidate={candidate} fallbackTitle={t('previewPage.candidateFallback')} />
            ))}
          </div>
        </section>
      ) : null}
    </main>
  );
}
