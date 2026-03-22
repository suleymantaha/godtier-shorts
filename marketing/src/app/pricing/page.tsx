import Link from "next/link"

import { createMetadata } from "@/lib/metadata"
import { siteConfig } from "@/lib/site"

const pricingCards = [
  {
    title: "Creator",
    note: "For solo operators and small teams turning long-form inventory into a steady short-form pipeline.",
    items: ["Single-operator workflow", "Fast clip review loop", "Core subtitle and transcript flow"],
  },
  {
    title: "Studio",
    note: "For teams that need repeatable output, stronger review paths, and cleaner production handoffs.",
    items: ["Shared workflow", "Transcript correction and reburn", "Deeper operational control"],
  },
  {
    title: "Agency",
    note: "For multi-client teams that need throughput without forcing every clip into the same pattern.",
    items: ["Multi-client motion", "Workflow tuning", "Rollout and support options"],
  },
]

export const metadata = createMetadata({
  title: "AI Shorts Generator Pricing",
  description:
    "Review pricing structure ideas for creator, studio, and agency workflows built on God-Tier Shorts.",
  path: "/pricing",
})

export default function PricingPage() {
  return (
    <div className="container section-block">
      <div className="section-heading">
        <p className="eyebrow">Pricing</p>
        <h1 className="page-title" style={{ fontFamily: "var(--font-display)" }}>
          Pricing built around workflow depth, team size, and clip volume.
        </h1>
        <p className="lead">
          Buyers rarely pay for exports alone. They pay for a faster path to
          publish-ready shorts, a cleaner review loop, and fewer correction
          headaches once the first AI pass is done.
        </p>
      </div>
      <div className="grid-3">
        {pricingCards.map((card) => (
          <article className="section-card" key={card.title}>
            <h2>{card.title}</h2>
            <p>{card.note}</p>
            <ul className="checklist">
              {card.items.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </article>
        ))}
      </div>
      <section className="cta-shell">
        <div>
          <p className="eyebrow">Rollout path</p>
          <h2 style={{ margin: 0, fontFamily: "var(--font-display)" }}>
            Choose the workflow shape that fits now, then scale the process later.
          </h2>
        </div>
        <div className="hero-actions">
          <a className="button" href={siteConfig.appUrl}>
            Open app
          </a>
          <Link className="button button-secondary" href="/compare/opus-clip-alternative">
            See comparisons
          </Link>
        </div>
      </section>
    </div>
  )
}
