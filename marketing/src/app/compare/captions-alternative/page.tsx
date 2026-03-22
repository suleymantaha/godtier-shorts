import Link from "next/link"

import { createMetadata } from "@/lib/metadata"
import { siteConfig } from "@/lib/site"

const rows = [
  {
    label: "Core pitch",
    ours: "AI repurposing workflow with correction and clip polish paths",
    theirs: "All-in-one caption and creator workflow appeal",
  },
  {
    label: "Who tends to prefer it",
    ours: "Operators optimizing for workflow control and flexible edits",
    theirs: "Creators comparing broad caption-app convenience",
  },
  {
    label: "Where we differentiate",
    ours: "Transcript, subtitle, and clip correction living in the same production story",
    theirs: "May appeal when ease and app familiarity matter most",
  },
]

export const metadata = createMetadata({
  title: "Captions Alternative",
  description:
    "Compare God-Tier Shorts against Captions for teams weighing convenience against deeper short-form editing and correction workflows.",
  path: "/compare/captions-alternative",
})

export default function CaptionsAlternativePage() {
  return (
    <div className="container section-block">
      <div className="section-heading">
        <p className="eyebrow">Comparison</p>
        <h1 className="page-title" style={{ fontFamily: "var(--font-display)" }}>
          An alternative for teams that need more than a caption app.
        </h1>
        <p className="lead">
          Captions-intent buyers are often evaluating convenience against
          control. This page should help them understand where a fuller
          repurposing workflow changes the decision.
        </p>
      </div>
      <div className="table-shell">
        <table>
          <thead>
            <tr>
              <th>Area</th>
              <th>God-Tier Shorts</th>
              <th>Captions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.label}>
                <td>{row.label}</td>
                <td>{row.ours}</td>
                <td>{row.theirs}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <section className="cta-shell">
        <div>
          <p className="eyebrow">Decision</p>
          <h2 style={{ margin: 0, fontFamily: "var(--font-display)" }}>
            Show the trade-off clearly, then route serious evaluators to the product.
          </h2>
        </div>
        <div className="hero-actions">
          <a className="button" href={siteConfig.appUrl}>
            Launch app
          </a>
          <Link className="button button-secondary" href="/features/clip-editor">
            See clip editor
          </Link>
        </div>
      </section>
    </div>
  )
}
