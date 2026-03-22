import Link from "next/link"

import { createMetadata } from "@/lib/metadata"

export const metadata = createMetadata({
  title: "Auto Clip Generator",
  description:
    "Explore God-Tier Shorts auto clip generation for teams that want faster first-pass clip selection without giving up review control.",
  path: "/features/auto-cut",
})

export default function AutoCutPage() {
  return (
    <div className="container section-block">
      <div className="section-heading">
        <p className="eyebrow">Feature</p>
        <h1 className="page-title" style={{ fontFamily: "var(--font-display)" }}>
          Auto clip generation that still expects an editor to care.
        </h1>
        <p className="lead">
          The value here is not just speed. It is getting to promising clip
          candidates quickly while preserving a review loop before anything
          becomes publish-ready output.
        </p>
      </div>
      <div className="grid-3">
        <article className="section-card">
          <h2>Faster first pass</h2>
          <p>
            Shorten the time from long-form source to a workable set of clip
            candidates.
          </p>
        </article>
        <article className="section-card">
          <h2>Human review still matters</h2>
          <p>
            The strongest workflow uses AI to narrow the field, then relies on
            an operator to decide what deserves polish.
          </p>
        </article>
        <article className="section-card">
          <h2>Connected downstream</h2>
          <p>
            Auto cut is strongest when it flows directly into subtitles,
            transcript fixes, and clip-level editing.
          </p>
        </article>
      </div>
      <section className="cta-shell">
        <div>
          <p className="eyebrow">Related</p>
          <h2 style={{ margin: 0, fontFamily: "var(--font-display)" }}>
            Pair auto detection with a real use-case page.
          </h2>
        </div>
        <div className="hero-actions">
          <Link className="button" href="/use-cases/youtube-to-shorts">
            YouTube workflow
          </Link>
          <Link className="button button-secondary" href="/features/viral-clip-detection">
            Viral detection
          </Link>
        </div>
      </section>
    </div>
  )
}
