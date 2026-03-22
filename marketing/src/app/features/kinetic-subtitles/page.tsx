import Link from "next/link"

import { createMetadata } from "@/lib/metadata"

export const metadata = createMetadata({
  title: "Kinetic Subtitle Generator",
  description:
    "Learn how God-Tier Shorts approaches kinetic subtitle generation for short-form video with correction paths and render-aware styling.",
  path: "/features/kinetic-subtitles",
})

export default function KineticSubtitlesPage() {
  return (
    <div className="container section-block">
      <div className="section-heading">
        <p className="eyebrow">Feature</p>
        <h1 className="page-title" style={{ fontFamily: "var(--font-display)" }}>
          Kinetic subtitles that feel edited, not stamped onto the clip.
        </h1>
        <p className="lead">
          Buyers looking for subtitle polish usually care about more than style
          presets. They care about timing, readability, and whether mistakes can
          be corrected without breaking the workflow.
        </p>
      </div>
      <div className="grid-3">
        <article className="section-card">
          <h2>Animated emphasis</h2>
          <p>
            Create motion and emphasis patterns that feel native to short-form
            platforms without losing readability.
          </p>
        </article>
        <article className="section-card">
          <h2>Render-aware correction</h2>
          <p>
            Subtitle edits stay connected to the final reburn path, which is a
            major trust signal when teams need to fix output after the first pass.
          </p>
        </article>
        <article className="section-card">
          <h2>Workflow fit</h2>
          <p>
            The subtitle layer is not a toy add-on. It sits inside a broader
            clip, transcript, and export workflow that still expects human review.
          </p>
        </article>
      </div>
      <section className="cta-shell">
        <div>
          <p className="eyebrow">Related</p>
          <h2 style={{ margin: 0, fontFamily: "var(--font-display)" }}>
            Turn subtitle intent into a concrete workflow page.
          </h2>
        </div>
        <div className="hero-actions">
          <Link className="button" href="/use-cases/podcast-to-clips">
            Podcast workflow
          </Link>
          <Link className="button button-secondary" href="/blog/how-to-turn-youtube-videos-into-shorts">
            Read the guide
          </Link>
        </div>
      </section>
    </div>
  )
}
