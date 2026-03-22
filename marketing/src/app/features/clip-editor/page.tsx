import Link from "next/link"

import { createMetadata } from "@/lib/metadata"
import { siteConfig } from "@/lib/site"

export const metadata = createMetadata({
  title: "Clip Editor for Shorts",
  description:
    "Explore the God-Tier Shorts clip editor for framing, overlays, and final short-form refinements after auto generation.",
  path: "/features/clip-editor",
})

export default function ClipEditorPage() {
  return (
    <div className="container section-block">
      <div className="section-heading">
        <p className="eyebrow">Feature</p>
        <h1 className="page-title" style={{ fontFamily: "var(--font-display)" }}>
          The clip editor is where automated output becomes publishable output.
        </h1>
        <p className="lead">
          Buyers looking for a clip editor are usually telling us they expect a
          second pass. This page should reassure them that the workflow supports
          that reality.
        </p>
      </div>
      <div className="grid-2">
        <article className="section-card">
          <h2>Framing and polish</h2>
          <p>
            Handle the last visual decisions that separate passable clips from
            clips that actually look intentional on mobile.
          </p>
        </article>
        <article className="section-card">
          <h2>Connected corrections</h2>
          <p>
            Clip editing works best when subtitle and transcript corrections can
            still happen nearby in the same workflow.
          </p>
        </article>
        <article className="section-card">
          <h2>Operator-first value</h2>
          <p>
            This page captures teams that do not want a black-box "done for you"
            promise and instead want a better production surface.
          </p>
        </article>
        <article className="section-card">
          <h2>Commercial bridge</h2>
          <p>
            The CTA should move people from "I need editing control" into the
            real product interface, not into another generic landing page.
          </p>
        </article>
      </div>
      <section className="cta-shell">
        <div>
          <p className="eyebrow">Action</p>
          <h2 style={{ margin: 0, fontFamily: "var(--font-display)" }}>
            Show them the editing promise, then hand them the app.
          </h2>
        </div>
        <div className="hero-actions">
          <a className="button" href={siteConfig.appUrl}>
            Launch app
          </a>
          <Link className="button button-secondary" href="/use-cases/podcast-to-clips">
            Podcast use case
          </Link>
        </div>
      </section>
    </div>
  )
}
