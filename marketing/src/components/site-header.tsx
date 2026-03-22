import Link from "next/link"

import { navigation, siteConfig } from "@/lib/site"

export function SiteHeader() {
  return (
    <header className="site-header">
      <div className="container header-inner">
        <Link className="brand" href="/">
          <span className="brand-mark" aria-hidden="true">
            GT
          </span>
          <span>
            <strong>{siteConfig.name}</strong>
            <span className="brand-subtitle">Marketing site</span>
          </span>
        </Link>
        <nav aria-label="Primary navigation" className="nav">
          {navigation.map((item) => (
            <Link key={item.href} href={item.href}>
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="header-actions">
          <Link className="button button-secondary" href={siteConfig.appUrl}>
            Open app
          </Link>
        </div>
      </div>
    </header>
  )
}
