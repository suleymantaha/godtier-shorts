export const STYLE_OPTIONS = [
  'HORMOZI',
  'MRBEAST',
  'MINIMALIST',
  'TIKTOK',
  'YOUTUBE_SHORT',
  'PODCAST',
  'CORPORATE',
  'HIGHCARE',
  'CUSTOM',
] as const;

export type StyleName = (typeof STYLE_OPTIONS)[number];

export const STYLE_LABELS: Record<StyleName, string> = {
  HORMOZI: 'Hormozi',
  MRBEAST: 'MrBeast',
  MINIMALIST: 'Minimalist',
  TIKTOK: 'TikTok',
  YOUTUBE_SHORT: 'YouTube Shorts',
  PODCAST: 'Podcast',
  CORPORATE: 'Kurumsal',
  HIGHCARE: 'Yüksek Kontrast',
  CUSTOM: 'Özel',
};

export const SUBTITLE_STYLES: Record<StyleName, string> = {
  HORMOZI:       'text-4xl text-yellow-400 italic',
  MRBEAST:       'text-3xl text-white underline decoration-blue-500 decoration-8',
  MINIMALIST:    'text-xl text-white font-mono lowercase',
  TIKTOK:        'text-4xl text-white font-black tracking-tighter',
  YOUTUBE_SHORT: 'text-3xl text-white font-bold',
  PODCAST:       'text-xl text-gray-200 font-sans',
  CORPORATE:     'text-lg text-white font-medium',
  HIGHCARE:      'text-2xl text-yellow-400 font-black',
  CUSTOM:        'text-2xl text-primary',
};

/**
 * ASS renk formati &HAABBGGRR -> CSS hex donusumu.
 * ASS'de byte sirasi: Alpha, Blue, Green, Red (BGR).
 */
function assToHex(ass: string): string {
  const h = ass.replace('&H', '');
  const r = h.slice(6, 8);
  const g = h.slice(4, 6);
  const b = h.slice(2, 4);
  return `#${r}${g}${b}`;
}

function assToRgba(ass: string): string {
  const h = ass.replace('&H', '');
  const a = parseInt(h.slice(0, 2), 16);
  const r = parseInt(h.slice(6, 8), 16);
  const g = parseInt(h.slice(4, 6), 16);
  const b = parseInt(h.slice(2, 4), 16);
  const alpha = +(1 - a / 255).toFixed(2);
  return `rgba(${r},${g},${b},${alpha})`;
}

export interface SubtitleInlineStyle {
  primaryColor: string;
  highlightColor: string;
  outlineColor: string;
  outlineWidth: number;
  fontSize: string;
  fontWeight: number;
  fontFamily: string;
  backgroundColor: string | null;
}

/*
 * Backend subtitle_styles.py ile birebir eslestirilmis stil haritasi.
 * ASS &HAABBGGRR formatindan CSS'e donusturulmustur.
 *
 * Backend kaynak:
 *   HORMOZI:       primary=&H00FFFFFF(white),  highlight=&H0000FFFF(yellow),  font=Montserrat Black 120pt, outline=10
 *   MRBEAST:       primary=&H00FFFFFF(white),  highlight=&H0000FF00(green),   font=Komika Axis 130pt,      outline=12
 *   MINIMALIST:    primary=&H00E0E0E0(gray),   highlight=&H00FFFFFF(white),   font=Helvetica Neue 18pt,    outline=0
 *   TIKTOK:        primary=&H00FFFFFF(white),  highlight=&H00FF00FF(magenta), font=Montserrat Black 140pt, outline=8
 *   YOUTUBE_SHORT: primary=&H00FFFFFF(white),  highlight=&H0000FFFF(yellow),  font=Poppins Bold 110pt,     outline=10, bg=semi-black
 *   PODCAST:       primary=&H00F0F0F0(lgray),  highlight=&H00FFFFFF(white),   font=Inter 32pt,             outline=0,  bg=semi-black
 *   CORPORATE:     primary=&H00FFFFFF(white),  highlight=default,             font=Roboto 36pt w500,       outline=2
 *   HIGHCARE:      primary=&H00FFFF00(cyan),   highlight=&H00FFFFFF(white),   font=Arial Black 48pt w900,  outline=4
 */
export const SUBTITLE_INLINE_STYLES: Record<StyleName, SubtitleInlineStyle> = {
  HORMOZI: {
    primaryColor:    assToHex('&H00FFFFFF'),
    highlightColor:  assToHex('&H0000FFFF'),
    outlineColor:    assToHex('&H00000000'),
    outlineWidth:    10,
    fontSize:        '2rem',
    fontWeight:      900,
    fontFamily:      '"Montserrat", "Outfit", sans-serif',
    backgroundColor: null,
  },
  MRBEAST: {
    primaryColor:    assToHex('&H00FFFFFF'),
    highlightColor:  assToHex('&H0000FF00'),
    outlineColor:    assToHex('&H00000000'),
    outlineWidth:    12,
    fontSize:        '2.2rem',
    fontWeight:      900,
    fontFamily:      '"Comic Sans MS", "Outfit", cursive',
    backgroundColor: null,
  },
  MINIMALIST: {
    primaryColor:    assToHex('&H00E0E0E0'),
    highlightColor:  assToHex('&H00FFFFFF'),
    outlineColor:    assToHex('&H00000000'),
    outlineWidth:    0,
    fontSize:        '1rem',
    fontWeight:      400,
    fontFamily:      '"Helvetica Neue", "Inter", sans-serif',
    backgroundColor: null,
  },
  TIKTOK: {
    primaryColor:    assToHex('&H00FFFFFF'),
    highlightColor:  assToHex('&H00FF00FF'),
    outlineColor:    assToHex('&H00000000'),
    outlineWidth:    8,
    fontSize:        '2.2rem',
    fontWeight:      900,
    fontFamily:      '"Montserrat", "Outfit", sans-serif',
    backgroundColor: null,
  },
  YOUTUBE_SHORT: {
    primaryColor:    assToHex('&H00FFFFFF'),
    highlightColor:  assToHex('&H0000FFFF'),
    outlineColor:    assToHex('&H00000000'),
    outlineWidth:    10,
    fontSize:        '1.8rem',
    fontWeight:      700,
    fontFamily:      '"Poppins", "Outfit", sans-serif',
    backgroundColor: assToRgba('&H80000000'),
  },
  PODCAST: {
    primaryColor:    assToHex('&H00F0F0F0'),
    highlightColor:  assToHex('&H00FFFFFF'),
    outlineColor:    assToHex('&H00000000'),
    outlineWidth:    0,
    fontSize:        '1.1rem',
    fontWeight:      400,
    fontFamily:      '"Inter", sans-serif',
    backgroundColor: assToRgba('&H40000000'),
  },
  CORPORATE: {
    primaryColor:    assToHex('&H00FFFFFF'),
    highlightColor:  assToHex('&H00FFFFFF'),
    outlineColor:    assToHex('&H00000000'),
    outlineWidth:    2,
    fontSize:        '1.15rem',
    fontWeight:      500,
    fontFamily:      '"Inter", "Roboto", sans-serif',
    backgroundColor: null,
  },
  HIGHCARE: {
    primaryColor:    assToHex('&H00FFFF00'),
    highlightColor:  assToHex('&H00FFFFFF'),
    outlineColor:    assToHex('&H00000000'),
    outlineWidth:    4,
    fontSize:        '1.5rem',
    fontWeight:      900,
    fontFamily:      '"Arial Black", "Outfit", sans-serif',
    backgroundColor: null,
  },
  CUSTOM: {
    primaryColor:    '#00f2ff',
    highlightColor:  '#00f2ff',
    outlineColor:    '#000000',
    outlineWidth:    2,
    fontSize:        '1.5rem',
    fontWeight:      600,
    fontFamily:      '"Outfit", sans-serif',
    backgroundColor: null,
  },
};

export function isStyleName(value: unknown): value is StyleName {
  return typeof value === 'string' && STYLE_OPTIONS.includes(value as StyleName);
}
