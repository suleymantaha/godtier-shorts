import Link from "next/link"

import { createMetadata } from "@/lib/metadata"
import { siteConfig } from "@/lib/site"

export const metadata = createMetadata({
  title: "Opus Clip Alternative",
  description:
    "Compare God-Tier Shorts against Opus Clip for teams that care about transcript correction, subtitle polish, and workflow control.",
  path: "/compare/opus-clip-alternative",
})

const rows = [
  {
    label: "Operator control after auto-detection",
    ours: "Built around review, transcript fixes, and reburn paths",
    theirs: "May fit teams that prefer a lighter-touch automated flow",
  },
  {
    label: "Subtitle workflow",
    ours: "Kinetic subtitle styling with an editor-led correction loop",
    theirs: "Depends on plan and preferred subtitle depth",
  },
  {
    label: "Best fit",
    ours: "Teams that want more control over output quality",
    theirs: "Teams optimizing for simple, fast automation",
  },
]

export default function OpusClipAlternativePage() {
  return (
    <div className="container section-block">
      <div className="section-heading">
        <p className="eyebrow">Comparison</p>
        <h1 className="page-title" style={{ fontFamily: "var(--font-display)" }}>
          A stronger fit for teams that want more than one-click shorts.
        </h1>
        <p className="lead">
          Opus Clip can appeal when speed and automation are the whole story.
          God-Tier Shorts is aimed at teams that still care about review,
          transcript fixes, subtitle polish, and the final editing mile.
        </p>
      </div>

      <div className="table-shell">
        <table>
          <thead>
            <tr>
              <th>Area</th>
              <th>God-Tier Shorts</th>
              <th>Opus Clip</th>
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
          <p className="eyebrow">Decision point</p>
          <h2 style={{ margin: 0, fontFamily: "var(--font-display)" }}>
            If control matters more than pure automation, go one step deeper.
          </h2>
        </div>
        <div className="hero-actions">
          <a className="button" href={siteConfig.appUrl}>
            Open app
          </a>
          <Link className="button button-secondary" href="/features/transcript-editor">
            See transcript editor
          </Link>
        </div>
      </section>
    </div>
  )
}
