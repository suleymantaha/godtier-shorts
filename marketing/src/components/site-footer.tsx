import Link from "next/link"

import { siteConfig } from "@/lib/site"

const footerLinks = [
  { href: "/features", label: "Features" },
  { href: "/use-cases", label: "Use Cases" },
  { href: "/pricing", label: "Pricing" },
  { href: "/blog", label: "Blog" },
  { href: "/docs/youtube-shorts-workflow", label: "Docs" },
  { href: "/compare/opus-clip-alternative", label: "Compare" },
]

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="container footer-grid">
        <div>
          <p className="eyebrow">God-Tier Shorts</p>
          <p className="footer-copy">
            Public marketing surface for SEO, product positioning, and demand
            capture. The product UI stays in a separate app.
          </p>
        </div>
        <div className="footer-links">
          {footerLinks.map((item) => (
            <Link key={item.href} href={item.href}>
              {item.label}
            </Link>
          ))}
        </div>
        <div className="footer-links">
          <a href={siteConfig.appUrl}>Launch product app</a>
          <a href="mailto:hello@godtiershorts.com">Contact sales</a>
        </div>
      </div>
    </footer>
  )
}
