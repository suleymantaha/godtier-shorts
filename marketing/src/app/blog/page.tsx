import Link from "next/link"

import { createMetadata } from "@/lib/metadata"
import { blogPosts } from "@/lib/site"

export const metadata = createMetadata({
  title: "Blog",
  description:
    "Educational content for video repurposing, short-form workflows, and subtitle quality that leads readers into the product.",
  path: "/blog",
})

export default function BlogPage() {
  return (
    <div className="container section-block">
      <div className="section-heading">
        <p className="eyebrow">Blog</p>
        <h1 className="page-title" style={{ fontFamily: "var(--font-display)" }}>
          Educational content that should feed product intent, not drift away from it.
        </h1>
        <p className="lead">
          The best early blog posts answer practical workflow questions and then
          point readers into a feature, use-case, or product CTA.
        </p>
      </div>
      <div className="grid-2">
        {blogPosts.map((post) => (
          <article className="section-card" key={post.href}>
            <h2>{post.title}</h2>
            <p>{post.description}</p>
            <Link className="button button-secondary" href={post.href}>
              Read post
            </Link>
          </article>
        ))}
      </div>
    </div>
  )
}
