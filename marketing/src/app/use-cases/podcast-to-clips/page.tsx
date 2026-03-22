import Link from "next/link"

import { createMetadata } from "@/lib/metadata"
import { siteConfig } from "@/lib/site"

export const metadata = createMetadata({
  title: "Podcast to Clips",
  description:
    "Turn long podcast episodes into social clips with AI-assisted discovery, transcript fixes, and subtitle polish.",
  path: "/use-cases/podcast-to-clips",
})

export default function PodcastToClipsPage() {
  return (
    <div className="container section-block">
      <div className="section-heading">
        <p className="eyebrow">Use case</p>
        <h1 className="page-title" style={{ fontFamily: "var(--font-display)" }}>
          Turn podcast episodes into clips without making every moment feel machine-cut.
        </h1>
        <p className="lead">
          Podcast teams need speed, but they also need trust in subtitles,
          speaker context, and the final social edit. This page speaks directly
          to that buyer intent.
        </p>
      </div>
      <div className="grid-2">
        <article className="section-card">
          <h2>Where this use case wins</h2>
          <ul className="checklist">
            <li>Long interview and panel formats with many clip candidates</li>
            <li>Teams that need transcript correction after the first pass</li>
            <li>Operators balancing speed with premium-looking subtitles</li>
          </ul>
        </article>
        <article className="section-card">
          <h2>What the page should sell</h2>
          <ul className="checklist">
            <li>AI helps find moments, but humans still shape the final output</li>
            <li>Transcript and subtitle fixes are part of the workflow, not an exception</li>
            <li>Short-form output can still look intentional and branded</li>
          </ul>
        </article>
      </div>
      <section className="cta-shell">
        <div>
          <p className="eyebrow">Next</p>
          <h2 style={{ margin: 0, fontFamily: "var(--font-display)" }}>
            Route podcast search traffic into the same product operators already use.
          </h2>
        </div>
        <div className="hero-actions">
          <a className="button" href={siteConfig.appUrl}>
            Launch app
          </a>
          <Link className="button button-secondary" href="/features/kinetic-subtitles">
            See subtitles
          </Link>
        </div>
      </section>
    </div>
  )
}
