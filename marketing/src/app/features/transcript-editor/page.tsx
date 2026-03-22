import Link from "next/link"

import { createMetadata } from "@/lib/metadata"
import { siteConfig } from "@/lib/site"

export const metadata = createMetadata({
  title: "Video Transcript Editor",
  description:
    "Learn how God-Tier Shorts handles video transcript editing, corrections, and reburn flows for short-form content teams.",
  path: "/features/transcript-editor",
})

export default function TranscriptEditorPage() {
  return (
    <div className="container section-block">
      <div className="section-heading">
        <p className="eyebrow">Feature</p>
        <h1 className="page-title" style={{ fontFamily: "var(--font-display)" }}>
          Transcript editing is where operator trust is won or lost.
        </h1>
        <p className="lead">
          This page speaks to teams who know that a fast first draft is useful,
          but a correction path is what makes the system deployable.
        </p>
      </div>
      <div className="grid-3">
        <article className="section-card">
          <h2>Fix text fast</h2>
          <p>
            Correct transcript errors before they become subtitle errors and
            before those errors reach published output.
          </p>
        </article>
        <article className="section-card">
          <h2>Save and reburn</h2>
          <p>
            A transcript editor matters because it is connected to a reliable
            reburn path, not because it exists in isolation.
          </p>
        </article>
        <article className="section-card">
          <h2>Better than cleanup debt</h2>
          <p>
            Give operators a direct correction surface instead of forcing manual
            workarounds after the export already feels wrong.
          </p>
        </article>
      </div>
      <section className="cta-shell">
        <div>
          <p className="eyebrow">Workflow</p>
          <h2 style={{ margin: 0, fontFamily: "var(--font-display)" }}>
            The transcript fix path should lead directly back into production.
          </h2>
        </div>
        <div className="hero-actions">
          <a className="button" href={siteConfig.appUrl}>
            Open app
          </a>
          <Link className="button button-secondary" href="/docs/youtube-shorts-workflow">
            Read workflow docs
          </Link>
        </div>
      </section>
    </div>
  )
}
