import Link from "next/link"

import { createMetadata } from "@/lib/metadata"
import { siteConfig } from "@/lib/site"

const rows = [
  {
    label: "Best-fit buyer",
    ours: "Teams that want subtitle polish inside a broader repurposing workflow",
    theirs: "Teams starting from a subtitle-first editing use case",
  },
  {
    label: "Correction path",
    ours: "Transcript fixes and reburn logic are part of the pitch",
    theirs: "Subtitle output may be the main focus of evaluation",
  },
  {
    label: "Workflow story",
    ours: "Short-form ops from detection through final clip polish",
    theirs: "Strong appeal to buyers comparing caption polish directly",
  },
]

export const metadata = createMetadata({
  title: "Submagic Alternative",
  description:
    "Compare God-Tier Shorts with Submagic for buyers who care about subtitle quality, transcript correction, and broader short-form workflow control.",
  path: "/compare/submagic-alternative",
})

export default function SubmagicAlternativePage() {
  return (
    <div className="container section-block">
      <div className="section-heading">
        <p className="eyebrow">Comparison</p>
        <h1 className="page-title" style={{ fontFamily: "var(--font-display)" }}>
          A subtitle-polish alternative that still leads into a full workflow.
        </h1>
        <p className="lead">
          This page should capture buyers who are clearly subtitle-sensitive but
          still need clip selection, transcript fixes, and final production
          control around that subtitle layer.
        </p>
      </div>
      <div className="table-shell">
        <table>
          <thead>
            <tr>
              <th>Area</th>
              <th>God-Tier Shorts</th>
              <th>Submagic</th>
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
          <p className="eyebrow">Next step</p>
          <h2 style={{ margin: 0, fontFamily: "var(--font-display)" }}>
            Use comparison intent to move subtitle-conscious buyers into the app.
          </h2>
        </div>
        <div className="hero-actions">
          <a className="button" href={siteConfig.appUrl}>
            Open app
          </a>
          <Link className="button button-secondary" href="/features/kinetic-subtitles">
            View subtitle feature
          </Link>
        </div>
      </section>
    </div>
  )
}
