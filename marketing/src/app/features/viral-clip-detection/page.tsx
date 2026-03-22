import Link from "next/link"

import { createMetadata } from "@/lib/metadata"

export const metadata = createMetadata({
  title: "Viral Clip Detection",
  description:
    "See how God-Tier Shorts approaches viral clip detection for operators who want candidate scoring without generic short-form output.",
  path: "/features/viral-clip-detection",
})

export default function ViralClipDetectionPage() {
  return (
    <div className="container section-block">
      <div className="section-heading">
        <p className="eyebrow">Feature</p>
        <h1 className="page-title" style={{ fontFamily: "var(--font-display)" }}>
          Viral clip detection should narrow the search, not replace judgment.
        </h1>
        <p className="lead">
          Buyers searching this feature usually want a system that finds the
          promising moments faster without flattening every output into the same
          formula.
        </p>
      </div>
      <div className="grid-2">
        <article className="section-card">
          <h2>Candidate scoring</h2>
          <p>
            Surface the moments most likely to deserve a short-form edit so the
            team spends time where it matters most.
          </p>
        </article>
        <article className="section-card">
          <h2>Operator override</h2>
          <p>
            The workflow stays usable because editors can still reject, adjust,
            and refine what the detection layer surfaces.
          </p>
        </article>
        <article className="section-card">
          <h2>Built for repurposing</h2>
          <p>
            Detection only matters if it connects to transcript correction,
            subtitle design, and final clip polish.
          </p>
        </article>
        <article className="section-card">
          <h2>Commercial fit</h2>
          <p>
            This page helps capture buyers comparing "AI finds moments for me"
            tools but who still want a production-grade workflow.
          </p>
        </article>
      </div>
      <section className="cta-shell">
        <div>
          <p className="eyebrow">Next</p>
          <h2 style={{ margin: 0, fontFamily: "var(--font-display)" }}>
            Detection is most persuasive when the edit path is visible too.
          </h2>
        </div>
        <div className="hero-actions">
          <Link className="button" href="/features/transcript-editor">
            See transcript editor
          </Link>
          <Link className="button button-secondary" href="/compare/opus-clip-alternative">
            Compare alternatives
          </Link>
        </div>
      </section>
    </div>
  )
}
