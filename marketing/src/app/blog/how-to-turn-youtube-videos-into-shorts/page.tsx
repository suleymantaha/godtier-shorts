import Link from "next/link"

import { createMetadata } from "@/lib/metadata"
import { siteConfig } from "@/lib/site"

export const metadata = createMetadata({
  title: "How to Turn YouTube Videos into Shorts",
  description:
    "A practical guide to turning long-form YouTube videos into shorts with better clip selection, subtitle polish, and editorial control.",
  path: "/blog/how-to-turn-youtube-videos-into-shorts",
})

const steps = [
  "Start from a long-form source that already has a clear thesis or memorable moments.",
  "Use AI to surface candidate clips, but review them through an operator lens before shipping.",
  "Treat transcript correction as part of the workflow, not a clean-up afterthought.",
  "Use subtitle styling to clarify emphasis and pacing, not just to fill screen space.",
  "Export only after the clip feels intentional on mobile, not merely complete.",
]

export default function YoutubeShortsGuidePage() {
  return (
    <div className="container section-block">
      <div className="section-heading">
        <p className="eyebrow">Guide</p>
        <h1 className="page-title" style={{ fontFamily: "var(--font-display)" }}>
          How to turn YouTube videos into shorts that still look edited.
        </h1>
        <p className="lead">
          Most people searching this query do not only want automation. They
          want a repeatable process that still leaves room for transcript,
          framing, and subtitle quality.
        </p>
      </div>
      <div className="grid-2">
        {steps.map((step, index) => (
          <article className="section-card" key={step}>
            <h2>Step {index + 1}</h2>
            <p>{step}</p>
          </article>
        ))}
      </div>
      <section className="cta-shell">
        <div>
          <p className="eyebrow">Bridge to product</p>
          <h2 style={{ margin: 0, fontFamily: "var(--font-display)" }}>
            Turn the guide into action inside the existing app.
          </h2>
        </div>
        <div className="hero-actions">
          <a className="button" href={siteConfig.appUrl}>
            Open app
          </a>
          <Link className="button button-secondary" href="/use-cases/youtube-to-shorts">
            View use case
          </Link>
        </div>
      </section>
    </div>
  )
}
