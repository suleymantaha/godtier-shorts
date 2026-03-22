import Link from "next/link"

import { createMetadata } from "@/lib/metadata"
import { siteConfig } from "@/lib/site"

export const metadata = createMetadata({
  title: "YouTube to Shorts",
  description:
    "See how God-Tier Shorts turns long-form YouTube videos into polished vertical clips with AI clip detection and subtitle control.",
  path: "/use-cases/youtube-to-shorts",
})

export default function YoutubeToShortsPage() {
  return (
    <div className="container section-block">
      <div className="section-heading">
        <p className="eyebrow">Use case</p>
        <h1 className="page-title" style={{ fontFamily: "var(--font-display)" }}>
          Turn one YouTube video into multiple publish-ready shorts without losing edit control.
        </h1>
        <p className="lead">
          This is the core commercial use case: get from long-form source to a
          backlog of strong clip candidates faster, then keep transcript,
          subtitle, and final polish decisions inside an operator-friendly flow.
        </p>
      </div>

      <div className="grid-2">
        <article className="section-card">
          <h2>Best fit</h2>
          <ul className="checklist">
            <li>YouTube creators with existing long-form inventory</li>
            <li>Teams repurposing interviews, podcasts, and explainers</li>
            <li>Operators who still need a transcript correction path</li>
          </ul>
        </article>
        <article className="section-card">
          <h2>What you get</h2>
          <ul className="checklist">
            <li>Faster first-pass clip discovery from long-form content</li>
            <li>A believable path to transcript and subtitle corrections</li>
            <li>Final shorts that look edited instead of mass-produced</li>
          </ul>
        </article>
      </div>

      <section className="section-block" style={{ paddingBottom: 0 }}>
        <div className="section-heading">
          <p className="eyebrow">Workflow narrative</p>
          <h2 style={{ fontFamily: "var(--font-display)" }}>
            From upload to polished short.
          </h2>
        </div>
        <div className="grid-2">
          <article className="section-card">
            <h3>1. Ingest</h3>
            <p>Bring in a long-form YouTube source and prepare it for analysis.</p>
          </article>
          <article className="section-card">
            <h3>2. Detect</h3>
            <p>Surface candidate clip windows that deserve operator review.</p>
          </article>
          <article className="section-card">
            <h3>3. Refine</h3>
            <p>Edit transcript details and subtitle styling before final burn.</p>
          </article>
          <article className="section-card">
            <h3>4. Publish</h3>
            <p>Export a vertical clip that looks intentional instead of generic.</p>
          </article>
        </div>
      </section>

      <section className="cta-shell">
        <div>
          <p className="eyebrow">Next step</p>
          <h2 style={{ margin: 0, fontFamily: "var(--font-display)" }}>
            If this is your workflow, the product should feel immediately familiar.
          </h2>
        </div>
        <div className="hero-actions">
          <a className="button" href={siteConfig.appUrl}>
            Launch product app
          </a>
          <Link className="button button-secondary" href="/features">
            Explore key features
          </Link>
        </div>
      </section>
    </div>
  )
}
