import Link from "next/link"

import { comparisons } from "@/lib/site"
import { createMetadata } from "@/lib/metadata"

export const metadata = createMetadata({
  title: "Compare Alternatives",
  description:
    "Browse comparison pages designed to capture high-intent buyers evaluating God-Tier Shorts against adjacent short-form tools.",
  path: "/compare",
})

export default function CompareHubPage() {
  return (
    <div className="container section-block">
      <div className="section-heading">
        <p className="eyebrow">Comparison hub</p>
        <h1 className="page-title" style={{ fontFamily: "var(--font-display)" }}>
          Comparison pages for buyers already close to a decision.
        </h1>
        <p className="lead">
          These pages should stay balanced, specific, and useful. The goal is to
          qualify intent and move serious operators into the product flow.
        </p>
      </div>
      <div className="grid-3">
        {comparisons.map((item) => (
          <article className="section-card" key={item.href}>
            <h2>{item.title}</h2>
            <p>{item.description}</p>
            <Link className="button button-secondary" href={item.href}>
              View comparison
            </Link>
          </article>
        ))}
      </div>
    </div>
  )
}
