import Link from "next/link"

import { createMetadata } from "@/lib/metadata"
import { featurePages } from "@/lib/site"

export const metadata = createMetadata({
  title: "Video Repurposing Features",
  description:
    "Explore the core God-Tier Shorts workflow: AI clip detection, kinetic subtitles, transcript editing, and clip-level refinement.",
  path: "/features",
})

export default function FeaturesPage() {
  return (
    <div className="container section-block">
      <div className="section-heading">
        <p className="eyebrow">Features</p>
        <h1 className="page-title" style={{ fontFamily: "var(--font-display)" }}>
          The feature set that makes automation usable.
        </h1>
        <p className="lead">
          The product is strongest when it combines speed with recovery paths:
          clip detection, transcript correction, subtitle control, and
          post-detection editing.
        </p>
      </div>
      <div className="grid-2">
        {featurePages.map((card) => (
          <article className="section-card" key={card.href}>
            <h2>{card.title}</h2>
            <p>{card.description}</p>
            <Link className="button button-secondary" href={card.href}>
              View feature
            </Link>
          </article>
        ))}
      </div>
      <section className="cta-shell">
        <div>
          <p className="eyebrow">Use case</p>
          <h2 style={{ margin: 0, fontFamily: "var(--font-display)" }}>
            See the YouTube-to-shorts flow end to end.
          </h2>
        </div>
        <div className="hero-actions">
          <Link className="button" href="/features/kinetic-subtitles">
            View subtitle feature
          </Link>
          <Link className="button button-secondary" href="/use-cases/youtube-to-shorts">
            View use case
          </Link>
        </div>
      </section>
    </div>
  )
}
