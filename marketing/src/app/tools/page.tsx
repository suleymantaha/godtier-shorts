import Link from "next/link"

import { createMetadata } from "@/lib/metadata"
import { tools } from "@/lib/site"

export const metadata = createMetadata({
  title: "Free Tools",
  description:
    "Explore lightweight free tools designed to attract upper-funnel short-form video traffic and route it into the product.",
  path: "/tools",
})

export default function ToolsPage() {
  return (
    <div className="container section-block">
      <div className="section-heading">
        <p className="eyebrow">Free tools</p>
        <h1 className="page-title" style={{ fontFamily: "var(--font-display)" }}>
          Useful small tools that support discovery without replacing the product.
        </h1>
        <p className="lead">
          Free tools should be specific, lightweight, and tightly connected to a
          real workflow inside the app.
        </p>
      </div>
      <div className="grid-2">
        {tools.map((tool) => (
          <article className="section-card" key={tool.href}>
            <h2>{tool.title}</h2>
            <p>{tool.description}</p>
            <Link className="button button-secondary" href={tool.href}>
              Open tool
            </Link>
          </article>
        ))}
      </div>
    </div>
  )
}
