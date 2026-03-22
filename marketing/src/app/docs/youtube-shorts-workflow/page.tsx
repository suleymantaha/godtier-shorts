import Link from "next/link"

import { createMetadata } from "@/lib/metadata"

export const metadata = createMetadata({
  title: "YouTube Shorts Workflow",
  description:
    "Understand the God-Tier Shorts workflow from ingest and transcription to subtitle correction and final export.",
  path: "/docs/youtube-shorts-workflow",
})

export default function YoutubeShortsWorkflowDocsPage() {
  return (
    <div className="container section-block">
      <div className="section-heading">
        <p className="eyebrow">Docs</p>
        <h1 className="page-title" style={{ fontFamily: "var(--font-display)" }}>
          The YouTube-to-shorts workflow, explained for search and onboarding.
        </h1>
        <p className="lead">
          Public docs do not replace the product UI. They clarify the workflow,
          improve search coverage, and hand qualified visitors to the app.
        </p>
      </div>

      <div className="grid-2">
        <article className="section-card">
          <h2>Ingest and transcription</h2>
          <p>
            Start from a source video, generate transcript data, and prepare the
            clip detection stage.
          </p>
        </article>
        <article className="section-card">
          <h2>Candidate clip selection</h2>
          <p>
            Surface likely moments, then let the operator decide which clips
            deserve refinement.
          </p>
        </article>
        <article className="section-card">
          <h2>Subtitle and transcript pass</h2>
          <p>
            Correct text, adjust subtitle behavior, and keep preview aligned
            with the final rendered output.
          </p>
        </article>
        <article className="section-card">
          <h2>Export and review</h2>
          <p>
            Finalize vertical output and use follow-up correction paths where a
            clip needs another pass.
          </p>
        </article>
      </div>

      <section className="cta-shell">
        <div>
          <p className="eyebrow">Related page</p>
          <h2 style={{ margin: 0, fontFamily: "var(--font-display)" }}>
            Turn workflow documentation into product intent.
          </h2>
        </div>
        <div className="hero-actions">
          <Link className="button" href="/use-cases/youtube-to-shorts">
            View use case
          </Link>
          <Link className="button button-secondary" href="/pricing">
            View pricing
          </Link>
        </div>
      </section>
    </div>
  )
}
