import Link from "next/link"

import { createMetadata } from "@/lib/metadata"
import { siteConfig } from "@/lib/site"

const ideas = [
  "Use motion to reinforce emphasis, not to compete with the spoken moment.",
  "Keep subtitle edits connected to a transcript correction path whenever possible.",
  "Design for mobile readability before styling for novelty.",
  "Treat timing and line breaks as part of the visual system, not just accessibility plumbing.",
]

export const metadata = createMetadata({
  title: "How to Add Kinetic Subtitles to Video",
  description:
    "A practical guide to adding kinetic subtitles to short-form video without sacrificing readability, timing, or edit control.",
  path: "/blog/how-to-add-kinetic-subtitles-to-video",
})

export default function KineticSubtitlesGuidePage() {
  return (
    <div className="container section-block">
      <div className="section-heading">
        <p className="eyebrow">Guide</p>
        <h1 className="page-title" style={{ fontFamily: "var(--font-display)" }}>
          How to add kinetic subtitles without making the video harder to watch.
        </h1>
        <p className="lead">
          Searchers here want subtitle polish, but the useful angle is balancing
          motion, readability, and the ability to fix mistakes after the first pass.
        </p>
      </div>
      <div className="grid-2">
        {ideas.map((idea, index) => (
          <article className="section-card" key={idea}>
            <h2>Principle {index + 1}</h2>
            <p>{idea}</p>
          </article>
        ))}
      </div>
      <section className="cta-shell">
        <div>
          <p className="eyebrow">Bridge</p>
          <h2 style={{ margin: 0, fontFamily: "var(--font-display)" }}>
            Move from subtitle theory into a production workflow.
          </h2>
        </div>
        <div className="hero-actions">
          <Link className="button" href="/features/kinetic-subtitles">
            View subtitle feature
          </Link>
          <a className="button button-secondary" href={siteConfig.appUrl}>
            Open app
          </a>
        </div>
      </section>
    </div>
  )
}
