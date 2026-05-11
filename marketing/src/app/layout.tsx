import type { Metadata, Viewport } from "next"
import type { ReactNode } from "react"

import { ClerkProvider } from "@clerk/nextjs"

import { SiteFooter } from "@/components/site-footer"
import { SiteHeader } from "@/components/site-header"
import { siteConfig } from "@/lib/site"

import "./globals.css"

export const metadata: Metadata = {
  metadataBase: new URL(`${siteConfig.siteUrl}/`),
  title: {
    default: `${siteConfig.name} | AI Video Repurposing`,
    template: `%s | ${siteConfig.name}`,
  },
  description: siteConfig.description,
  applicationName: siteConfig.name,
  alternates: {
    canonical: "/",
  },
  icons: {
    icon: "/mark.svg",
  },
  openGraph: {
    siteName: siteConfig.name,
    type: "website",
    title: `${siteConfig.name} | AI Video Repurposing`,
    description: siteConfig.description,
    url: siteConfig.siteUrl,
  },
  twitter: {
    card: "summary_large_image",
    title: `${siteConfig.name} | AI Video Repurposing`,
    description: siteConfig.description,
  },
}

export const viewport: Viewport = {
  themeColor: "#061117",
}

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <ClerkProvider>
          <div className="site-shell">
            <SiteHeader />
            <main className="site-main">{children}</main>
            <SiteFooter />
          </div>
        </ClerkProvider>
      </body>
    </html>
  )
}
