import Link from "next/link"

import { createMetadata } from "@/lib/metadata"
import { featureHighlights, siteConfig, workflowSteps } from "@/lib/site"

export const metadata = createMetadata({
  title: "AI Shorts Generator",
  description:
    "Turn long-form video into polished shorts with AI-assisted clip detection, kinetic subtitles, transcript editing, and operator-grade review control.",
  path: "/",
})

const proofPanels = [
  {
    alt: "Pipeline overview visual showing ingest, scoring, and review flow.",
    caption: "Pipeline review: ingest, detect, and operator handoff",
    src: "/proof-pipeline.svg",
    title: "Pipeline visibility",
  },
  {
    alt: "Subtitle editing visual showing styled kinetic subtitle output.",
    caption: "Subtitle proof: animated text with readable pacing",
    src: "/proof-subtitles.svg",
    title: "Subtitle quality",
  },
  {
    alt: "Clip editing visual showing timeline and post-generation refinement controls.",
    caption: "Editor proof: final polish after auto generation",
    src: "/proof-editor.svg",
    title: "Clip refinement",
  },
] as const

const faqs = [
  {
    answer:
      "No. The existing Vite product UI stays separate, and the marketing site exists to capture search traffic and route qualified visitors into the app.",
    question: "Will the current product UI disappear if we use this marketing site?",
  },
  {
    answer:
      "Teams turning long-form YouTube videos, podcasts, interviews, and client content into shorts while still needing subtitle, transcript, and clip-level corrections.",
    question: "Who is God-Tier Shorts best for?",
  },
  {
    answer:
      "The workflow is stronger than a one-click export because it includes review, transcript fixes, subtitle adjustments, and a final editing pass when the first result is not enough.",
    question: "How is this different from generic AI shorts tools?",
  },
  {
    answer:
      "Yes. The transcript editor and reburn flow are central because subtitle trust depends on having a correction path after the first pass.",
    question: "Can we correct transcript and subtitle mistakes after generation?",
  },
]

export default function HomePage() {
  const schema = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "SoftwareApplication",
        applicationCategory: "MultimediaApplication",
        description: metadata.description,
        name: siteConfig.name,
        operatingSystem: "Web",
        screenshot: proofPanels.map((item) => `${siteConfig.siteUrl}${item.src}`),
        url: siteConfig.siteUrl,
      },
      {
        "@type": "FAQPage",
        mainEntity: faqs.map((item) => ({
          "@type": "Question",
          acceptedAnswer: {
            "@type": "Answer",
            text: item.answer,
          },
          name: item.question,
        })),
      },
    ],
  }

  return (
    <div className="container">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
      />
      <section className="hero">
        <div>
          <p className="eyebrow">AI video repurposing with editorial control</p>
          <h1 style={{ fontFamily: "var(--font-display)" }}>
            Turn one long-form video into publish-ready shorts without giving up editorial control.
          </h1>
          <p className="lead">
            God-Tier Shorts helps creators, podcast teams, and agencies move
            from long-form source to polished vertical clips with AI-assisted
            detection, kinetic subtitles, transcript correction, and a final
            editing pass when the first result is not enough.
          </p>
          <div className="hero-actions">
            <Link className="button" href={siteConfig.appUrl}>
              Start in the app
            </Link>
            <Link className="button button-secondary" href="/features">
              See the workflow
            </Link>
          </div>
          <div className="chip-row">
            <span className="chip">YouTube to Shorts</span>
            <span className="chip">Podcast to Clips</span>
            <span className="chip">Kinetic Subtitles</span>
            <span className="chip">Transcript Fixes</span>
          </div>
        </div>
        <div className="stat-stack">
          <div className="stat-card section-card">
            <span className="stat-value">1 system</span>
            <p>
              Move from ingest to final export inside one connected workflow
              instead of stitching together separate tools.
            </p>
          </div>
          <div className="stat-card section-card">
            <span className="stat-value">Fast first pass</span>
            <p>
              Use AI to surface clip candidates quickly, then let an operator
              decide what actually deserves to ship.
            </p>
          </div>
          <div className="stat-card section-card">
            <span className="stat-value">Correction path</span>
            <p>
              Transcript, subtitle, and clip-level fixes are built into the
              story, not left for messy cleanup after export.
            </p>
          </div>
        </div>
      </section>

      <section className="section-block">
        <div className="section-heading">
          <p className="eyebrow">Visual proof</p>
          <h2 style={{ fontFamily: "var(--font-display)" }}>
            What serious buyers can verify before they click.
          </h2>
          <p>
            These proof panels make the product feel concrete: pipeline review,
            subtitle quality, and the editing layer that sits after automation.
          </p>
        </div>
        <div className="proof-grid">
          {proofPanels.map((panel) => (
            <article className="proof-card" key={panel.src}>
              <div className="proof-media">
                <img alt={panel.alt} className="proof-image" src={panel.src} />
              </div>
              <div className="proof-copy">
                <p className="eyebrow">{panel.title}</p>
                <p>{panel.caption}</p>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="section-block">
        <div className="section-heading">
          <p className="eyebrow">Why teams buy</p>
          <h2 style={{ fontFamily: "var(--font-display)" }}>
            Speed matters. So does trusting the output.
          </h2>
          <p>
            The difference is not just automatic clipping. It is getting to
            strong candidates faster while keeping subtitle polish, transcript
            quality, and final clip judgment inside the workflow.
          </p>
        </div>
        <div className="grid-2">
          {featureHighlights.map((feature) => (
            <article className="section-card" key={feature.href}>
              <h3>{feature.title}</h3>
              <p>{feature.description}</p>
              <Link className="button button-secondary" href={feature.href}>
                View feature
              </Link>
            </article>
          ))}
        </div>
      </section>

      <section className="section-block">
        <div className="section-heading">
          <p className="eyebrow">Workflow</p>
          <h2 style={{ fontFamily: "var(--font-display)" }}>
            What the operator actually does.
          </h2>
          <p>
            Buyers do not need another abstract AI promise. They need to see a
            believable path from raw source material to publish-ready shorts.
          </p>
        </div>
        <div className="grid-2">
          {workflowSteps.map((step) => (
            <article className="section-card" key={step}>
              <p>{step}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="section-block">
        <div className="section-heading">
          <p className="eyebrow">FAQ</p>
          <h2 style={{ fontFamily: "var(--font-display)" }}>
            Questions serious buyers ask before they start a trial.
          </h2>
          <p>
            The objections are usually about control, correction paths, and
            workflow fit. Answering them clearly improves both trust and intent.
          </p>
        </div>
        <div className="faq-grid">
          {faqs.map((item) => (
            <article className="section-card" key={item.question}>
              <h3>{item.question}</h3>
              <p>{item.answer}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="cta-shell">
        <div>
          <p className="eyebrow">Start here</p>
          <h2 style={{ margin: 0, fontFamily: "var(--font-display)" }}>
            If the workflow matters more than one-click hype, start with the product.
          </h2>
        </div>
        <div className="hero-actions">
          <Link className="button" href="/use-cases/youtube-to-shorts">
            See YouTube workflow
          </Link>
          <Link className="button button-secondary" href="/docs/youtube-shorts-workflow">
            Read workflow docs
          </Link>
          <Link className="button button-secondary" href="/tools/youtube-shorts-hook-ideas">
            Try free tool
          </Link>
        </div>
      </section>
    </div>
  )
}
