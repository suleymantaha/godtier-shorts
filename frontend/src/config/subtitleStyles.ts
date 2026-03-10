export const STYLE_OPTIONS = [
  'HORMOZI',
  'MRBEAST',
  'MINIMALIST',
  'TIKTOK',
  'YOUTUBE_SHORT',
  'PODCAST',
  'CORPORATE',
  'HIGHCARE',
  'CYBER_PUNK',
  'STORY_TELLER',
  'GLOW_KARAOKE',
  'GLASS_MORPH',
  'ALI_ABDAAL',
  'RETRO_WAVE',
  'HACKER_TERMINAL',
  'CINEMATIC_FILM',
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
  CYBER_PUNK: 'Cyber Glitch',
  STORY_TELLER: 'Storyteller',
  GLOW_KARAOKE: 'Neon Karaoke',
  GLASS_MORPH: 'Glassmorphism',
  ALI_ABDAAL: 'Productivity Vlog',
  RETRO_WAVE: '80s Synthwave',
  HACKER_TERMINAL: 'Terminal Code',
  CINEMATIC_FILM: 'Documentary Film',
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
  CYBER_PUNK:    'text-4xl text-white font-bold',
  STORY_TELLER:  'text-xl text-gray-200 font-mono',
  GLOW_KARAOKE:  'text-4xl text-white font-black',
  GLASS_MORPH:   'text-2xl text-white/50 font-semibold p-2 rounded bg-white/20 backdrop-blur-md border border-black/20',
  ALI_ABDAAL:    'text-3xl text-white font-bold tracking-tight',
  RETRO_WAVE:    'text-4xl text-pink-500 font-black italic tracking-widest',
  HACKER_TERMINAL: 'text-xl text-green-500 font-mono bg-black/80 px-2 py-1',
  CINEMATIC_FILM: 'text-2xl text-gray-200 font-serif italic tracking-wide',
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
  CYBER_PUNK: {
    primaryColor:    assToHex('&H00FFFFFF'),
    highlightColor:  assToHex('&H0000FFFF'),
    outlineColor:    assToHex('&H00FF00FF'),
    outlineWidth:    4,
    fontSize:        '2.2rem',
    fontWeight:      700,
    fontFamily:      '"Orbitron", "Outfit", sans-serif',
    backgroundColor: null,
  },
  STORY_TELLER: {
    primaryColor:    assToHex('&H00E0E0E0'),
    highlightColor:  assToHex('&H00E0E0E0'),
    outlineColor:    assToHex('&H00000000'),
    outlineWidth:    0,
    fontSize:        '1.2rem',
    fontWeight:      400,
    fontFamily:      '"Courier New", "Courier", monospace',
    backgroundColor: null,
  },
  GLOW_KARAOKE: {
    primaryColor:    assToHex('&H80FFFFFF'),
    highlightColor:  assToHex('&H0000FFFF'),
    outlineColor:    assToHex('&H00000000'),
    outlineWidth:    2,
    fontSize:        '1.8rem',
    fontWeight:      800,
    fontFamily:      '"Montserrat", "Outfit", sans-serif',
    backgroundColor: null,
  },
  GLASS_MORPH: {
    primaryColor:    assToHex('&H20FFFFFF'),
    highlightColor:  assToHex('&H20FFFFFF'),
    outlineColor:    assToHex('&H40000000'),
    outlineWidth:    1,
    fontSize:        '1.2rem',
    fontWeight:      600,
    fontFamily:      '"Inter", "Outfit", sans-serif',
    backgroundColor: assToRgba('&H80FFFFFF'),
  },
  ALI_ABDAAL: {
    primaryColor:    assToHex('&H00FFFFFF'),
    highlightColor:  assToHex('&H0032CD32'),
    outlineColor:    assToHex('&H60000000'),
    outlineWidth:    0,
    fontSize:        '1.6rem',
    fontWeight:      700,
    fontFamily:      '"Outfit", "Inter", sans-serif',
    backgroundColor: null,
  },
  RETRO_WAVE: {
    primaryColor:    assToHex('&H00FF00FF'),
    highlightColor:  assToHex('&H0000FFFF'),
    outlineColor:    assToHex('&H00000000'),
    outlineWidth:    6,
    fontSize:        '2.2rem',
    fontWeight:      900,
    fontFamily:      '"Vampire", "Impact", sans-serif',
    backgroundColor: null,
  },
  HACKER_TERMINAL: {
    primaryColor:    assToHex('&H0000FF00'),
    highlightColor:  assToHex('&H00FFFFFF'),
    outlineColor:    assToHex('&H00000000'),
    outlineWidth:    0,
    fontSize:        '1.1rem',
    fontWeight:      400,
    fontFamily:      '"Consolas", "Courier New", monospace',
    backgroundColor: assToRgba('&HB0000000'),
  },
  CINEMATIC_FILM: {
    primaryColor:    assToHex('&H00E6E6E6'),
    highlightColor:  assToHex('&H00D4AF37'),
    outlineColor:    assToHex('&H40000000'),
    outlineWidth:    1,
    fontSize:        '1.3rem',
    fontWeight:      400,
    fontFamily:      '"Times New Roman", "Georgia", serif',
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
