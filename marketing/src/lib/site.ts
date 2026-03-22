function normalizeUrl(value: string | undefined, fallback: string): string {
  try {
    return new URL(value || fallback).toString().replace(/\/$/, "")
  } catch {
    return fallback
  }
}

export type SiteNavItem = {
  href: string
  label: string
}

export type SiteLinkCard = {
  href: string
  title: string
  description: string
}

export const siteConfig = {
  name: "God-Tier Shorts",
  shortName: "GTS",
  description:
    "Turn long-form video into publish-ready shorts with AI clip detection, kinetic subtitles, transcript editing, and operator-grade control.",
  siteUrl: normalizeUrl(process.env.NEXT_PUBLIC_SITE_URL, "http://localhost:3000"),
  appUrl: normalizeUrl(process.env.NEXT_PUBLIC_APP_URL, "http://localhost:5173"),
}

export const navigation: SiteNavItem[] = [
  { href: "/features", label: "Features" },
  { href: "/use-cases", label: "Use Cases" },
  { href: "/pricing", label: "Pricing" },
  { href: "/compare", label: "Compare" },
  { href: "/blog", label: "Blog" },
  { href: "/docs/youtube-shorts-workflow", label: "Docs" },
]

export const featureHighlights: SiteLinkCard[] = [
  {
    href: "/features/auto-cut",
    title: "AI Auto Cut",
    description:
      "Detect the moments that deserve to become short-form content without throwing away editor control.",
  },
  {
    href: "/features/kinetic-subtitles",
    title: "Kinetic Subtitles",
    description:
      "Use premium subtitle styling and animated emphasis that still maps cleanly to final render output.",
  },
  {
    href: "/features/transcript-editor",
    title: "Transcript Editing",
    description:
      "Fix transcript issues, save changes, and reburn without rebuilding your whole workflow from scratch.",
  },
  {
    href: "/features/clip-editor",
    title: "Clip Recovery",
    description:
      "Stay operational when a clip needs another pass, a subtitle correction, or an alternate framing decision.",
  },
]

export const workflowSteps = [
  "Ingest a long-form source from upload or YouTube workflow.",
  "Run transcription and identify likely high-retention clip windows.",
  "Review clips, refine transcript text, and adjust subtitle styling.",
  "Ship a vertical short that looks polished instead of fully automated.",
]

export const featurePages: SiteLinkCard[] = [
  {
    href: "/features/auto-cut",
    title: "Auto clip generator",
    description:
      "Identify candidate moments quickly, then keep a human operator in control before publishing.",
  },
  {
    href: "/features/kinetic-subtitles",
    title: "Kinetic subtitle generator",
    description:
      "Create subtitle motion and emphasis that looks premium instead of low-effort automation.",
  },
  {
    href: "/features/viral-clip-detection",
    title: "Viral clip detection",
    description:
      "Use AI-assisted clip scoring to surface promising short-form moments from long-form source video.",
  },
  {
    href: "/features/transcript-editor",
    title: "Video transcript editor",
    description:
      "Correct transcript text, preserve operator trust, and reburn without rebuilding the full workflow.",
  },
  {
    href: "/features/clip-editor",
    title: "Clip editor for shorts",
    description:
      "Handle framing, overlays, and final polish when automated output needs a second pass.",
  },
]

export const useCases: SiteLinkCard[] = [
  {
    href: "/use-cases/youtube-to-shorts",
    title: "YouTube to Shorts",
    description:
      "Turn long-form YouTube videos into shorts while keeping transcript and subtitle quality under control.",
  },
  {
    href: "/use-cases/podcast-to-clips",
    title: "Podcast to Clips",
    description:
      "Convert long podcast episodes into social clips with a workflow that still supports editorial review.",
  },
  {
    href: "/use-cases/for-agencies",
    title: "For Agencies",
    description:
      "Package repeatable short-form output for multiple clients without forcing every clip into the same template.",
  },
]

export const comparisons: SiteLinkCard[] = [
  {
    href: "/compare/opus-clip-alternative",
    title: "Opus Clip alternative",
    description:
      "Position God-Tier Shorts for teams that need more correction paths and editorial control.",
  },
  {
    href: "/compare/submagic-alternative",
    title: "Submagic alternative",
    description:
      "Speak to subtitle-focused buyers who care about polish, styling, and post-generation fixes.",
  },
  {
    href: "/compare/captions-alternative",
    title: "Captions alternative",
    description:
      "Capture buyers comparing all-in-one caption apps with workflow-oriented repurposing tools.",
  },
]

export const blogPosts: SiteLinkCard[] = [
  {
    href: "/blog/how-to-turn-youtube-videos-into-shorts",
    title: "How to turn YouTube videos into shorts",
    description:
      "A practical guide that bridges educational search intent into a product workflow.",
  },
  {
    href: "/blog/how-to-add-kinetic-subtitles-to-video",
    title: "How to add kinetic subtitles to video",
    description:
      "Explain subtitle design, timing, and when animated text improves short-form retention.",
  },
]

export const tools: SiteLinkCard[] = [
  {
    href: "/tools/youtube-shorts-hook-ideas",
    title: "YouTube shorts hook generator",
    description:
      "Offer a small, useful free tool that captures upper-funnel traffic without distracting from the product.",
  },
]
