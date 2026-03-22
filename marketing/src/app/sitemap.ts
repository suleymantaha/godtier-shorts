import type { MetadataRoute } from "next"

import { siteConfig } from "@/lib/site"

const routes = [
  "",
  "/blog",
  "/blog/how-to-add-kinetic-subtitles-to-video",
  "/blog/how-to-turn-youtube-videos-into-shorts",
  "/compare",
  "/compare/captions-alternative",
  "/features",
  "/features/auto-cut",
  "/features/clip-editor",
  "/features/kinetic-subtitles",
  "/features/transcript-editor",
  "/features/viral-clip-detection",
  "/pricing",
  "/tools",
  "/tools/youtube-shorts-hook-ideas",
  "/use-cases",
  "/use-cases/for-agencies",
  "/use-cases/podcast-to-clips",
  "/use-cases/youtube-to-shorts",
  "/compare/opus-clip-alternative",
  "/compare/submagic-alternative",
  "/docs/youtube-shorts-workflow",
]

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date()

  return routes.map((route) => ({
    url: `${siteConfig.siteUrl}${route}`,
    lastModified: now,
    changeFrequency: route === "" ? "weekly" : "monthly",
    priority: route === "" ? 1 : 0.7,
  }))
}
