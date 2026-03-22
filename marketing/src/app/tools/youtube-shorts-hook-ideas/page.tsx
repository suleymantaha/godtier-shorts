import Link from "next/link"

import { HookIdeaGenerator } from "@/components/hook-idea-generator"
import { createMetadata } from "@/lib/metadata"
import { siteConfig } from "@/lib/site"

export const metadata = createMetadata({
  title: "YouTube Shorts Hook Generator",
  description:
    "Generate hook ideas for YouTube shorts and short-form clips with a lightweight free tool connected to the God-Tier Shorts workflow.",
  path: "/tools/youtube-shorts-hook-ideas",
})

export default function YoutubeShortsHookIdeasPage() {
  return (
    <div className="container section-block">
      <div className="section-heading">
        <p className="eyebrow">Free tool</p>
        <h1 className="page-title" style={{ fontFamily: "var(--font-display)" }}>
          Generate hook ideas for short-form clips in seconds.
        </h1>
        <p className="lead">
          This is a simple, useful top-of-funnel tool. It should help the user
          quickly, then point them toward the full workflow where clips are
          actually selected, edited, subtitled, and exported.
        </p>
      </div>
      <HookIdeaGenerator />
      <section className="cta-shell">
        <div>
          <p className="eyebrow">Next step</p>
          <h2 style={{ margin: 0, fontFamily: "var(--font-display)" }}>
            Use the tool here, then use the product to ship the actual clip.
          </h2>
        </div>
        <div className="hero-actions">
          <a className="button" href={siteConfig.appUrl}>
            Launch app
          </a>
          <Link className="button button-secondary" href="/blog/how-to-turn-youtube-videos-into-shorts">
            Read the guide
          </Link>
        </div>
      </section>
    </div>
  )
}
