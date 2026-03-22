import { AlertCircle, CheckCircle2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import type { RenderMetadata } from '../../types';

const QUALITY_TONE_CLASSNAMES = {
  degraded: 'border-red-500/25 bg-red-500/8 text-red-100',
  good: 'border-emerald-500/25 bg-emerald-500/8 text-emerald-100',
  watch: 'border-amber-500/25 bg-amber-500/8 text-amber-100',
} as const;

const QUALITY_DRIFT_WARNING_MS = 80;

type RenderWarningContext = {
  audioStatus?: string;
  durationValidationStatus?: string | null;
  hasAudio?: boolean;
  layoutValidationStatus?: string | null;
  lowerThirdCollisionDetected: boolean;
  maxCenterJump: number;
  mergedOutputDriftMs: number;
  nvencFallbackUsed: boolean;
  panelSwapCount: number;
  predictFallbackActive: boolean;
  simultaneousOverlapCount: number;
  startupSettleMs: number;
  subtitleOverflowDetected: boolean;
  trackingStatus?: string;
  transcriptStatus?: string;
};

type RenderWarningRule = {
  key: string;
  matches: (context: RenderWarningContext) => boolean;
};

function resolveQualityTone(score?: number | null): keyof typeof QUALITY_TONE_CLASSNAMES {
  if ((score ?? 0) >= 85) {
    return 'good';
  }
  if ((score ?? 0) >= 70) {
    return 'watch';
  }
  return 'degraded';
}

function resolveMaxCenterJump(trackingQuality: RenderMetadata['tracking_quality']) {
  return Math.max(
    trackingQuality?.primary_p95_center_jump_px ?? 0,
    trackingQuality?.secondary_p95_center_jump_px ?? 0,
  );
}

function resolveSimultaneousOverlapCount(renderMetadata: RenderMetadata) {
  return renderMetadata.transcript_quality?.simultaneous_event_overlap_count
    ?? renderMetadata.subtitle_layout_quality?.simultaneous_event_overlap_count
    ?? 0;
}

function resolveSubtitleOverflowDetected(renderMetadata: RenderMetadata) {
  return Boolean(
    renderMetadata.subtitle_layout_quality?.subtitle_overflow_detected
    || renderMetadata.transcript_quality?.subtitle_overflow_detected,
  );
}

function resolveRenderAudioContext(renderMetadata: RenderMetadata) {
  return {
    audioStatus: renderMetadata.audio_validation?.audio_validation_status,
    hasAudio: renderMetadata.audio_validation?.has_audio,
  };
}

function resolveRenderLayoutContext(renderMetadata: RenderMetadata) {
  return {
    durationValidationStatus: renderMetadata.duration_validation_status,
    layoutValidationStatus: renderMetadata.layout_validation_status,
    lowerThirdCollisionDetected: Boolean(renderMetadata.subtitle_layout_quality?.lower_third_collision_detected),
    mergedOutputDriftMs: renderMetadata.debug_timing?.merged_output_drift_ms ?? 0,
    nvencFallbackUsed: Boolean(renderMetadata.subtitle_layout_quality?.nvenc_fallback_used),
    simultaneousOverlapCount: resolveSimultaneousOverlapCount(renderMetadata),
    subtitleOverflowDetected: resolveSubtitleOverflowDetected(renderMetadata),
    transcriptStatus: renderMetadata.transcript_quality?.status,
  };
}

function resolveRenderTrackingContext(trackingQuality: RenderMetadata['tracking_quality']) {
  return {
    maxCenterJump: resolveMaxCenterJump(trackingQuality),
    panelSwapCount: trackingQuality?.panel_swap_count ?? 0,
    predictFallbackActive: Boolean(trackingQuality?.predict_fallback_active),
    startupSettleMs: trackingQuality?.startup_settle_ms ?? 0,
    trackingStatus: trackingQuality?.status,
  };
}

function buildRenderWarningContext(renderMetadata: RenderMetadata): RenderWarningContext {
  const trackingQuality = renderMetadata.tracking_quality;

  return {
    ...resolveRenderAudioContext(renderMetadata),
    ...resolveRenderLayoutContext(renderMetadata),
    ...resolveRenderTrackingContext(trackingQuality),
  };
}

const RENDER_WARNING_RULES: RenderWarningRule[] = [
  { key: 'subtitleEditor.renderQuality.warnings.overlap', matches: (context) => context.simultaneousOverlapCount > 0 },
  {
    key: 'subtitleEditor.renderQuality.warnings.duration',
    matches: (context) => Boolean(context.durationValidationStatus && context.durationValidationStatus !== 'ok'),
  },
  { key: 'subtitleEditor.renderQuality.warnings.openingDelayed', matches: (context) => context.layoutValidationStatus === 'opening_subject_delayed' },
  { key: 'subtitleEditor.renderQuality.warnings.openingMissing', matches: (context) => context.layoutValidationStatus === 'opening_subject_missing' },
  { key: 'subtitleEditor.renderQuality.warnings.trackingFallback', matches: (context) => context.trackingStatus === 'fallback' },
  { key: 'subtitleEditor.renderQuality.warnings.jitter', matches: (context) => context.panelSwapCount > 0 || context.maxCenterJump > 12 },
  { key: 'subtitleEditor.renderQuality.warnings.startupSettle', matches: (context) => context.startupSettleMs > 250 },
  { key: 'subtitleEditor.renderQuality.warnings.stableFallback', matches: (context) => context.predictFallbackActive },
  {
    key: 'subtitleEditor.renderQuality.warnings.transcriptDegraded',
    matches: (context) => context.transcriptStatus === 'partial' || context.transcriptStatus === 'degraded',
  },
  { key: 'subtitleEditor.renderQuality.warnings.overflow', matches: (context) => context.subtitleOverflowDetected },
  { key: 'subtitleEditor.renderQuality.warnings.lowerThird', matches: (context) => context.lowerThirdCollisionDetected },
  { key: 'subtitleEditor.renderQuality.warnings.nvencFallback', matches: (context) => context.nvencFallbackUsed },
  { key: 'subtitleEditor.renderQuality.warnings.drift', matches: (context) => context.mergedOutputDriftMs >= QUALITY_DRIFT_WARNING_MS },
  {
    key: 'subtitleEditor.renderQuality.warnings.audioInvalid',
    matches: (context) => context.audioStatus === 'missing' || context.audioStatus === 'invalid' || context.hasAudio === false,
  },
];

function buildRenderWarnings(renderMetadata: RenderMetadata, t: (key: string) => string): string[] {
  const context = buildRenderWarningContext(renderMetadata);

  return RENDER_WARNING_RULES
    .filter((rule) => rule.matches(context))
    .map((rule) => t(rule.key))
    .slice(0, 3);
}

function MetricPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-current/15 bg-black/15 px-3 py-2">
      <p className="text-[10px] font-mono uppercase tracking-[0.2em] opacity-75">{label}</p>
      <p className="mt-1 font-medium uppercase tracking-[0.08em]">{value}</p>
    </div>
  );
}

export function RenderQualitySummaryCard({ renderMetadata }: { renderMetadata: RenderMetadata }) {
  const { t } = useTranslation();
  const score = renderMetadata.render_quality_score ?? 0;
  const tone = resolveQualityTone(score);
  const warnings = buildRenderWarnings(renderMetadata, t);
  const transcriptStatus = renderMetadata.transcript_quality?.status ?? 'unknown';
  const trackingStatus = renderMetadata.tracking_quality?.status ?? 'unknown';
  const driftMs = renderMetadata.debug_timing?.merged_output_drift_ms ?? 0;
  const audioStatus = renderMetadata.audio_validation?.audio_validation_status ?? 'unknown';

  return (
    <div className={`glass-card p-5 space-y-4 ${QUALITY_TONE_CLASSNAMES[tone]}`} data-testid="render-quality-summary">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="space-y-1">
          <p className="text-[11px] font-mono uppercase tracking-[0.24em] opacity-80">{t('subtitleEditor.renderQuality.renderQuality')}</p>
          <h3 className="text-sm font-bold uppercase tracking-[0.18em]">{t('subtitleEditor.renderQuality.qualitySummary')}</h3>
        </div>
        <div className="rounded-full border border-current/25 px-3 py-1 text-[11px] font-mono uppercase tracking-widest">
          {t('subtitleEditor.renderQuality.score', { score })}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 text-xs sm:grid-cols-4">
        <MetricPill label={t('subtitleEditor.renderQuality.metrics.tracking')} value={trackingStatus} />
        <MetricPill label={t('subtitleEditor.renderQuality.metrics.transcript')} value={transcriptStatus} />
        <MetricPill label={t('subtitleEditor.renderQuality.metrics.drift')} value={`${driftMs.toFixed(1)} ms`} />
        <MetricPill label={t('subtitleEditor.renderQuality.metrics.audio')} value={audioStatus} />
      </div>

      {warnings.length > 0 ? (
        <div className="space-y-2">
          {warnings.map((warning) => (
            <div key={warning} className="flex items-start gap-2 text-xs leading-5">
              <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>{warning}</span>
            </div>
          ))}
        </div>
      ) : (
        <div className="flex items-start gap-2 text-xs leading-5">
          <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>{t('subtitleEditor.renderQuality.clean')}</span>
        </div>
      )}
    </div>
  );
}
