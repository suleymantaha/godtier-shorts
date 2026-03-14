import type { CSSProperties } from 'react';
import { Subtitles, EyeOff } from 'lucide-react';
import { HIGHLIGHT_INDEX, PREVIEW_WORDS, getSubtitlePreviewModel } from './subtitlePreview/helpers';

interface SubtitlePreviewProps {
  disabled: boolean;
  styleName: string;
}

export function SubtitlePreview({ styleName, disabled }: SubtitlePreviewProps) {
  const preview = getSubtitlePreviewModel(styleName);
  return (
    <section className="glass-card p-6 border-accent/10 ring-1 ring-accent/5">
      <PreviewHeader disabled={disabled} styleLabel={preview.styleLabel} />
      <div className="relative flex items-center justify-center min-h-[90px] rounded-lg bg-black/70 overflow-hidden">
        {disabled ? (
          <DisabledPreview />
        ) : (
          <EnabledPreview preview={preview} />
        )}
      </div>
      {!disabled && <ColorLegend highlightColor={preview.highlightColor} primaryColor={preview.primaryColor} />}
    </section>
  );
}

function PreviewHeader({ disabled, styleLabel }: { disabled: boolean; styleLabel: string }) {
  return (
    <div className="flex items-center justify-between mb-4">
      <div className="flex items-center gap-2">
        <Subtitles className="w-4 h-4 text-accent/70" aria-hidden="true" />
        <h3 className="text-xs font-mono uppercase tracking-[0.2em] text-accent/80">
          Altyazi Onizleme
        </h3>
      </div>
      {!disabled && (
        <span className="text-[11px] font-mono text-muted-foreground/50">
          {styleLabel}
        </span>
      )}
    </div>
  );
}

function DisabledPreview() {
  return (
    <div className="relative flex items-center gap-2 text-sm font-mono text-muted-foreground/60">
      <EyeOff className="w-4 h-4" aria-hidden="true" />
      Altyazi devre disi
    </div>
  );
}

function EnabledPreview({
  preview,
}: {
  preview: ReturnType<typeof getSubtitlePreviewModel>;
}) {
  const containerClassName = preview.isGlass
    ? 'relative text-center px-5 py-3 rounded bg-white/10 backdrop-blur-md border border-white/20 shadow-xl'
    : 'relative text-center px-5 py-3 rounded';
  const containerStyle: CSSProperties | undefined = preview.hasBackground && !preview.isGlass
    ? preview.wrapperStyle
    : undefined;

  return (
    <div className={containerClassName} style={containerStyle}>
      {PREVIEW_WORDS.map((word, index) => (
        <PreviewWord
          key={word}
          index={index}
          preview={preview}
          word={word}
        />
      ))}
    </div>
  );
}

function PreviewWord({
  index,
  preview,
  word,
}: {
  index: number;
  preview: ReturnType<typeof getSubtitlePreviewModel>;
  word: string;
}) {
  const wordStyle: CSSProperties = {
    ...(index === HIGHLIGHT_INDEX ? preview.baseStyleHighlight : preview.baseStylePrimary),
    ...(preview.isTypewriter && index > HIGHLIGHT_INDEX ? { opacity: 0 } : {}),
  };

  return (
    <span style={wordStyle}>
      {word}
      {index < PREVIEW_WORDS.length - 1 ? ' ' : ''}
    </span>
  );
}

function ColorLegend({
  highlightColor,
  primaryColor,
}: {
  highlightColor: string;
  primaryColor: string;
}) {
  return (
    <div className="mt-3 flex items-center justify-center gap-3">
      <ColorLegendItem color={primaryColor} label="primary" />
      {primaryColor !== highlightColor && <ColorLegendItem color={highlightColor} label="highlight" />}
    </div>
  );
}

function ColorLegendItem({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="w-2.5 h-2.5 rounded-full border border-white/20" style={{ backgroundColor: color }} />
      <span className="text-[10px] font-mono text-muted-foreground/40">{label}</span>
    </div>
  );
}
