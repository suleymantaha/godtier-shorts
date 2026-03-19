import { AlertCircle, Cpu, Play, Settings, Sparkles, Subtitles, Waves, Zap } from 'lucide-react';
import type { Dispatch, ReactNode, SetStateAction } from 'react';

import { isStyleName, isSubtitleAnimationType, type StyleName, type SubtitleAnimationType } from '../../config/subtitleStyles';
import {
  ENGINE_SELECT_OPTIONS,
  LAYOUT_SELECT_OPTIONS,
  MOTION_SELECT_OPTIONS,
  RESOLUTION_OPTIONS,
  STYLE_SELECT_OPTIONS,
  clampClipCount,
  clampDurationSeconds,
} from './helpers';
import { Select } from '../ui/Select';

interface SourceSectionProps {
  isSubmitting: boolean;
  onResolutionChange: Dispatch<SetStateAction<string>>;
  onUrlChange: Dispatch<SetStateAction<string>>;
  resolution: string;
  resolutionId: string;
  url: string;
  urlId: string;
}

interface ControlGridSectionProps {
  animationId: string;
  animationType: SubtitleAnimationType;
  engine: string;
  engineId: string;
  isSubmitting: boolean;
  layout: string;
  layoutId: string;
  numClips: number;
  numClipsId: string;
  onAnimationChange: Dispatch<SetStateAction<SubtitleAnimationType>>;
  onEngineChange: Dispatch<SetStateAction<string>>;
  onLayoutChange: Dispatch<SetStateAction<'auto' | 'single' | 'split'>>;
  onNumClipsChange: Dispatch<SetStateAction<number>>;
  onSkipSubtitlesChange: Dispatch<SetStateAction<boolean>>;
  onStyleChange: Dispatch<SetStateAction<StyleName>>;
  skipSubtitles: boolean;
  style: StyleName;
  styleId: string;
}

interface AutoPilotSectionProps {
  autoMode: boolean;
  durationMax: number;
  durationMaxId: string;
  durationMin: number;
  durationMinId: string;
  isSubmitting: boolean;
  onAutoModeChange: Dispatch<SetStateAction<boolean>>;
  onDurationMaxChange: Dispatch<SetStateAction<number>>;
  onDurationMinChange: Dispatch<SetStateAction<number>>;
}

export function JobFormSourceSection({
  isSubmitting,
  onResolutionChange,
  onUrlChange,
  resolution,
  resolutionId,
  url,
  urlId,
}: SourceSectionProps) {
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
      <div className="space-y-2 md:col-span-3">
        <label htmlFor={urlId} className="text-sm font-medium text-primary uppercase tracking-widest ml-1 holo-text">
          SOURCE FEED URL
        </label>
        <div className="relative group">
          <input
            id={urlId}
            type="url"
            value={url}
            onChange={(event) => onUrlChange(event.target.value)}
            placeholder="https://youtube.com/watch?v=..."
            className="input-field w-full pl-12 group-hover:border-primary/30 transition-all"
            disabled={isSubmitting}
            autoComplete="url"
          />
          <Play className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-primary/50 pointer-events-none" aria-hidden="true" />
        </div>
      </div>
      <div className="space-y-2 md:col-span-1">
        <label htmlFor={resolutionId} className="text-sm font-medium text-primary uppercase tracking-widest ml-1 holo-text">
          RESOLUTION
        </label>
        <Select
          id={resolutionId}
          value={resolution}
          onChange={onResolutionChange}
          options={RESOLUTION_OPTIONS}
          disabled={isSubmitting}
          icon={<Settings className="w-4 h-4 text-accent/50" />}
        />
      </div>
    </div>
  );
}

export function JobFormControlGridSection({
  animationId,
  animationType,
  engine,
  engineId,
  isSubmitting,
  layout,
  layoutId,
  numClips,
  numClipsId,
  onAnimationChange,
  onEngineChange,
  onLayoutChange,
  onNumClipsChange,
  onSkipSubtitlesChange,
  onStyleChange,
  skipSubtitles,
  style,
  styleId,
}: ControlGridSectionProps) {
  return (
    <div
      data-testid="job-form-control-grid"
      className="grid grid-cols-1 gap-3 lg:grid-cols-2"
    >
      <JobFormControlCard
        accentClassName="border-secondary/20"
        header={(
          <>
            <label htmlFor={styleId} className="ml-1 block text-sm font-medium leading-tight text-secondary uppercase tracking-widest holo-text">
              VISUAL STYLE
            </label>
            <button
              type="button"
              role="switch"
              aria-checked={skipSubtitles}
              aria-label="Altyazi islemeyi atla"
              onClick={() => onSkipSubtitlesChange((previous) => !previous)}
              className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border-2 transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary ${skipSubtitles ? 'bg-red-500/30 border-red-500/50' : 'bg-primary/20 border-primary/40'}`}
            >
              <span
                className={`pointer-events-none inline-block h-4 w-4 rounded-full shadow-sm transition-transform ${skipSubtitles ? 'translate-x-5 bg-red-400' : 'translate-x-0.5 bg-primary'}`}
              />
            </button>
          </>
        )}
        control={(
          <Select
            id={styleId}
            value={style}
            onChange={(value) => onStyleChange(isStyleName(value) ? value : 'TIKTOK')}
            options={STYLE_SELECT_OPTIONS}
            disabled={isSubmitting || skipSubtitles}
            icon={<Sparkles className="w-4 h-4 text-secondary/50" />}
            className={skipSubtitles ? 'opacity-40' : ''}
          />
        )}
        footer={skipSubtitles ? (
          <div className="flex items-center gap-1.5 text-[11px] font-mono text-red-400/80">
            <Subtitles className="w-3 h-3" aria-hidden="true" />
            Altyazi devre disi
          </div>
        ) : null}
      />
      <JobFormControlCard
        accentClassName="border-secondary/20"
        header={(
          <label htmlFor={animationId} className="ml-1 block text-sm font-medium leading-tight text-secondary uppercase tracking-widest holo-text">
            MOTION STYLE
          </label>
        )}
        control={(
          <Select
            id={animationId}
            value={animationType}
            onChange={(value) => onAnimationChange(isSubtitleAnimationType(value) ? value : 'default')}
            options={MOTION_SELECT_OPTIONS}
            disabled={isSubmitting || skipSubtitles}
            icon={<Waves className="w-4 h-4 text-secondary/50" />}
            className={skipSubtitles ? 'opacity-40' : ''}
          />
        )}
      />
      <JobFormControlCard
        accentClassName="border-accent/20"
        header={(
          <label htmlFor={engineId} className="ml-1 block max-w-full text-sm font-medium leading-tight text-accent uppercase tracking-[0.18em] holo-text">
            AI CORE ENGINE
          </label>
        )}
        control={(
          <Select
            id={engineId}
            value={engine}
            onChange={onEngineChange}
            options={ENGINE_SELECT_OPTIONS}
            disabled={isSubmitting}
            icon={<Cpu className="w-4 h-4 text-accent/50" />}
          />
        )}
      />
      <JobFormControlCard
        accentClassName="border-accent/20"
        header={(
          <label htmlFor={numClipsId} className="ml-1 block max-w-full text-sm font-medium leading-tight text-accent uppercase tracking-[0.16em]">
            TARGET CLONE COUNT
          </label>
        )}
        control={(
          <input
            id={numClipsId}
            type="number"
            min={1}
            max={20}
            value={numClips}
            onChange={(event) => onNumClipsChange(clampClipCount(Number(event.target.value) || 1))}
            className="input-field w-full"
            disabled={isSubmitting}
          />
        )}
      />
      <JobFormControlCard
        accentClassName="border-accent/20"
        header={(
          <label htmlFor={layoutId} className="ml-1 block max-w-full text-sm font-medium leading-tight text-accent uppercase tracking-[0.16em]">
            FRAME LAYOUT
          </label>
        )}
        control={(
          <Select
            id={layoutId}
            value={layout}
            onChange={(value) => onLayoutChange(value === 'split' ? 'split' : value === 'single' ? 'single' : 'auto')}
            options={LAYOUT_SELECT_OPTIONS}
            disabled={isSubmitting}
            icon={<Zap className="w-4 h-4 text-accent/50" />}
          />
        )}
      />
    </div>
  );
}

function JobFormControlCard({
  accentClassName,
  control,
  footer,
  header,
}: {
  accentClassName: string;
  control: ReactNode;
  footer?: ReactNode;
  header: ReactNode;
}) {
  return (
    <div className={`rounded-2xl border bg-foreground/5 p-3 h-full ${accentClassName}`}>
      <div className="grid h-full grid-rows-[minmax(1.75rem,auto)_3.25rem_1rem] gap-2.5">
        <div className="flex min-h-8 items-start justify-between gap-3">{header}</div>
        <div className="min-w-0">{control}</div>
        <div className="flex items-center">{footer ? footer : <span aria-hidden="true" className="invisible text-[11px]">placeholder</span>}</div>
      </div>
    </div>
  );
}

export function JobFormAutoPilotSection({
  autoMode,
  durationMax,
  durationMaxId,
  durationMin,
  durationMinId,
  isSubmitting,
  onAutoModeChange,
  onDurationMaxChange,
  onDurationMinChange,
}: AutoPilotSectionProps) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-accent/80 uppercase tracking-widest ml-1">
          AUTO PILOT (120-180s)
        </label>
        <button
          type="button"
          role="switch"
          aria-checked={autoMode}
          aria-label="Otomatik mod"
          onClick={() => onAutoModeChange((previous) => !previous)}
          className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border-2 transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary ${autoMode ? 'bg-primary/20 border-primary/40' : 'bg-foreground/10 border-border'}`}
        >
          <span
            className={`pointer-events-none inline-block h-4 w-4 rounded-full shadow-sm transition-transform ${autoMode ? 'translate-x-5 bg-primary' : 'translate-x-0.5 bg-foreground/60'}`}
          />
        </button>
      </div>
      {!autoMode && (
        <div className="grid grid-cols-2 gap-4">
          <DurationField
            disabled={isSubmitting}
            id={durationMinId}
            label="Min sure (sn)"
            max={300}
            min={30}
            onChange={onDurationMinChange}
            value={durationMin}
          />
          <DurationField
            disabled={isSubmitting}
            id={durationMaxId}
            label="Max sure (sn)"
            max={300}
            min={30}
            onChange={onDurationMaxChange}
            value={durationMax}
          />
        </div>
      )}
    </div>
  );
}

export function JobFormErrorAlert({ error }: { error: string | null }) {
  if (!error) {
    return null;
  }

  return (
    <div role="alert" className="flex items-center gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-xs font-mono text-red-400">
      <AlertCircle className="w-4 h-4 shrink-0" aria-hidden="true" />
      {error}
    </div>
  );
}

export function JobFormSubmitButton({
  disabled,
  isSubmitting,
}: {
  disabled: boolean;
  isSubmitting: boolean;
}) {
  return (
    <button
      type="submit"
      disabled={disabled}
      className={`btn-primary w-full flex items-center justify-center gap-3 ${isSubmitting ? 'opacity-50 cursor-not-allowed' : ''}`}
    >
      {isSubmitting ? (
        <>
          <div className="w-5 h-5 border-2 border-background/30 border-t-background animate-spin rounded-full" />
          INITIATING...
        </>
      ) : (
        <>
          <Zap className="w-5 h-5 animate-pulse" aria-hidden="true" />
          INITIALIZE SEQUENCE
        </>
      )}
    </button>
  );
}

function DurationField({
  disabled,
  id,
  label,
  max,
  min,
  onChange,
  value,
}: {
  disabled: boolean;
  id: string;
  label: string;
  max: number;
  min: number;
  onChange: Dispatch<SetStateAction<number>>;
  value: number;
}) {
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="text-xs font-mono text-muted-foreground">
        {label}
      </label>
      <input
        id={id}
        type="number"
        min={min}
        max={max}
        value={value}
        onChange={(event) => onChange(clampDurationSeconds(Number(event.target.value) || min))}
        className="input-field w-full"
        disabled={disabled}
      />
    </div>
  );
}
