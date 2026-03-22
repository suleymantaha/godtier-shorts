import Link from "next/link"

import { createMetadata } from "@/lib/metadata"
import { siteConfig } from "@/lib/site"

export const metadata = createMetadata({
  title: "Video Repurposing for Agencies",
  description:
    "See how God-Tier Shorts can support agency workflows that need repeatable short-form output without giving up editorial control.",
  path: "/use-cases/for-agencies",
})

export default function AgenciesUseCasePage() {
  return (
    <div className="container section-block">
      <div className="section-heading">
        <p className="eyebrow">Use case</p>
        <h1 className="page-title" style={{ fontFamily: "var(--font-display)" }}>
          A short-form workflow for agencies that need repeatability without sameness.
        </h1>
        <p className="lead">
          Agency buyers care about throughput, client variance, and whether the
          process still leaves room for operator judgment when automation is not enough.
        </p>
      </div>
      <div className="grid-3">
        <article className="section-card">
          <h2>Repeatable ops</h2>
          <p>
            Build a workflow that can be repeated across accounts without forcing
            identical creative outcomes.
          </p>
        </article>
        <article className="section-card">
          <h2>Correction paths</h2>
          <p>
            Agencies need a safe way to fix transcript, subtitle, and clip issues
            before assets reach a client.
          </p>
        </article>
        <article className="section-card">
          <h2>Commercial fit</h2>
          <p>
            This page captures teams searching for scalable short-form production
            without a full surrender to one-click black boxes.
          </p>
        </article>
      </div>
      <section className="cta-shell">
        <div>
          <p className="eyebrow">CTA</p>
          <h2 style={{ margin: 0, fontFamily: "var(--font-display)" }}>
            Agency intent should flow to a demo or straight into the app.
          </h2>
        </div>
        <div className="hero-actions">
          <a className="button" href={siteConfig.appUrl}>
            Launch app
          </a>
          <Link className="button button-secondary" href="/pricing">
            View pricing
          </Link>
        </div>
      </section>
    </div>
  )
}
