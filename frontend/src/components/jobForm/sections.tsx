import { AlertCircle, Cpu, Play, Settings, Sparkles, Subtitles, Zap } from 'lucide-react';
import type { Dispatch, SetStateAction } from 'react';

import { isStyleName, type StyleName } from '../../config/subtitleStyles';
import {
  ENGINE_SELECT_OPTIONS,
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

interface StyleAndEngineSectionProps {
  engine: string;
  engineId: string;
  isSubmitting: boolean;
  onEngineChange: Dispatch<SetStateAction<string>>;
  onSkipSubtitlesChange: Dispatch<SetStateAction<boolean>>;
  onStyleChange: Dispatch<SetStateAction<StyleName>>;
  skipSubtitles: boolean;
  style: StyleName;
  styleId: string;
}

interface ClipCountFieldProps {
  isSubmitting: boolean;
  numClips: number;
  numClipsId: string;
  onNumClipsChange: Dispatch<SetStateAction<number>>;
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
    <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
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

export function JobFormStyleAndEngineSection({
  engine,
  engineId,
  isSubmitting,
  onEngineChange,
  onSkipSubtitlesChange,
  onStyleChange,
  skipSubtitles,
  style,
  styleId,
}: StyleAndEngineSectionProps) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <div className="space-y-2">
        <div className="flex min-h-6 items-center justify-between">
          <label htmlFor={styleId} className="text-sm font-medium text-secondary uppercase tracking-widest ml-1 holo-text">
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
        </div>
        <Select
          id={styleId}
          value={style}
          onChange={(value) => onStyleChange(isStyleName(value) ? value : 'TIKTOK')}
          options={STYLE_SELECT_OPTIONS}
          disabled={isSubmitting || skipSubtitles}
          icon={<Sparkles className="w-4 h-4 text-secondary/50" />}
          className={skipSubtitles ? 'opacity-40' : ''}
        />
        {skipSubtitles && (
          <div className="flex items-center gap-1.5 text-[11px] font-mono text-red-400/80">
            <Subtitles className="w-3 h-3" aria-hidden="true" />
            Altyazi devre disi
          </div>
        )}
      </div>
      <div className="space-y-2">
        <div className="flex min-h-6 items-center">
          <label htmlFor={engineId} className="text-sm font-medium text-accent uppercase tracking-widest ml-1 holo-text">
            AI CORE ENGINE
          </label>
        </div>
        <Select
          id={engineId}
          value={engine}
          onChange={onEngineChange}
          options={ENGINE_SELECT_OPTIONS}
          disabled={isSubmitting}
          icon={<Cpu className="w-4 h-4 text-accent/50" />}
        />
      </div>
    </div>
  );
}

export function JobFormClipCountField({
  isSubmitting,
  numClips,
  numClipsId,
  onNumClipsChange,
}: ClipCountFieldProps) {
  return (
    <div className="space-y-2">
      <label htmlFor={numClipsId} className="text-sm font-medium text-accent uppercase tracking-[0.2em] ml-1">
        TARGET CLONE COUNT
      </label>
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
    <div className="space-y-2">
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
