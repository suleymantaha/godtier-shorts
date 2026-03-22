import Link from "next/link"

import { createMetadata } from "@/lib/metadata"
import { useCases } from "@/lib/site"

export const metadata = createMetadata({
  title: "Short-Form Video Use Cases",
  description:
    "Explore the primary God-Tier Shorts use cases for YouTube creators, podcast teams, and operators building repeatable short-form workflows.",
  path: "/use-cases",
})

export default function UseCasesPage() {
  return (
    <div className="container section-block">
      <div className="section-heading">
        <p className="eyebrow">Use cases</p>
        <h1 className="page-title" style={{ fontFamily: "var(--font-display)" }}>
          Landing pages built around real search intent, not vague personas.
        </h1>
        <p className="lead">
          The strongest SEO use-case pages connect a specific workflow problem to
          a visible operational promise and a clear path into the product.
        </p>
      </div>
      <div className="grid-3">
        {useCases.map((item) => (
          <article className="section-card" key={item.href}>
            <h2>{item.title}</h2>
            <p>{item.description}</p>
            <Link className="button button-secondary" href={item.href}>
              View page
            </Link>
          </article>
        ))}
      </div>
    </div>
  )
}
