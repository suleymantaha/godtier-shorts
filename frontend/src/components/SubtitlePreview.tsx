import type { CSSProperties } from 'react';
import { Subtitles, EyeOff } from 'lucide-react';
import { SUBTITLE_INLINE_STYLES, isStyleName } from '../config/subtitleStyles';
import type { StyleName } from '../config/subtitleStyles';

interface SubtitlePreviewProps {
  styleName: string;
  disabled: boolean;
}

const PREVIEW_WORDS = ['Bu', 'bir', 'ornek', 'altyazi'];
const HIGHLIGHT_INDEX = 2;

const STYLE_LABELS: Record<StyleName, string> = {
  HORMOZI: 'Hormozi',
  MRBEAST: 'MrBeast',
  MINIMALIST: 'Minimalist',
  TIKTOK: 'TikTok',
  YOUTUBE_SHORT: 'YouTube Shorts',
  PODCAST: 'Podcast',
  CORPORATE: 'Kurumsal',
  HIGHCARE: 'Yuksek Kontrast',
  CUSTOM: 'Ozel',
};

function buildTextShadow(outlineColor: string, width: number): string {
  if (width <= 0) return 'none';
  const px = Math.min(width, 6);
  const spread = `${px}px`;
  return [
    `${spread} ${spread} 0 ${outlineColor}`,
    `-${spread} -${spread} 0 ${outlineColor}`,
    `${spread} -${spread} 0 ${outlineColor}`,
    `-${spread} ${spread} 0 ${outlineColor}`,
    `0 ${spread} 0 ${outlineColor}`,
    `0 -${spread} 0 ${outlineColor}`,
    `${spread} 0 0 ${outlineColor}`,
    `-${spread} 0 0 ${outlineColor}`,
  ].join(', ');
}

export const SubtitlePreview = ({ styleName, disabled }: SubtitlePreviewProps) => {
  const resolvedStyle: StyleName = isStyleName(styleName) ? styleName : 'HORMOZI';
  const s = SUBTITLE_INLINE_STYLES[resolvedStyle];
  const textShadow = buildTextShadow(s.outlineColor, s.outlineWidth);

  const baseStyle: CSSProperties = {
    fontSize: s.fontSize,
    fontWeight: s.fontWeight,
    fontFamily: s.fontFamily,
    textShadow,
    lineHeight: 1.3,
  };

  const primaryStyle: CSSProperties = { ...baseStyle, color: s.primaryColor };
  const highlightStyle: CSSProperties = { ...baseStyle, color: s.highlightColor };

  const containerBg = s.backgroundColor ?? 'transparent';
  const hasBg = s.backgroundColor !== null;

  return (
    <section className="glass-card p-6 border-accent/10 ring-1 ring-accent/5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Subtitles className="w-4 h-4 text-accent/70" aria-hidden="true" />
          <h3 className="text-xs font-mono uppercase tracking-[0.2em] text-accent/80">
            Altyazi Onizleme
          </h3>
        </div>
        {!disabled && (
          <span className="text-[11px] font-mono text-muted-foreground/50">
            {STYLE_LABELS[resolvedStyle]}
          </span>
        )}
      </div>

      <div className="relative flex items-center justify-center min-h-[90px] rounded-lg bg-black/70 overflow-hidden">
        {disabled ? (
          <div className="relative flex items-center gap-2 text-sm font-mono text-muted-foreground/60">
            <EyeOff className="w-4 h-4" aria-hidden="true" />
            Altyazi devre disi
          </div>
        ) : (
          <div
            className="relative text-center px-5 py-3 rounded"
            style={{ backgroundColor: hasBg ? containerBg : 'transparent' }}
          >
            {PREVIEW_WORDS.map((word, i) => (
              <span key={i} style={i === HIGHLIGHT_INDEX ? highlightStyle : primaryStyle}>
                {word}{i < PREVIEW_WORDS.length - 1 ? ' ' : ''}
              </span>
            ))}
          </div>
        )}
      </div>

      {!disabled && (
        <div className="mt-3 flex items-center justify-center gap-3">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full border border-white/20" style={{ backgroundColor: s.primaryColor }} />
            <span className="text-[10px] font-mono text-muted-foreground/40">primary</span>
          </div>
          {s.primaryColor !== s.highlightColor && (
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full border border-white/20" style={{ backgroundColor: s.highlightColor }} />
              <span className="text-[10px] font-mono text-muted-foreground/40">highlight</span>
            </div>
          )}
        </div>
      )}
    </section>
  );
};
