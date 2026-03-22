import type { Metadata } from "next"

import { siteConfig } from "@/lib/site"

type CreateMetadataOptions = {
  title: string
  description: string
  path: string
}

export function createMetadata({
  title,
  description,
  path,
}: CreateMetadataOptions): Metadata {
  const url = new URL(path, `${siteConfig.siteUrl}/`).toString()

  return {
    title,
    description,
    alternates: {
      canonical: path,
    },
    openGraph: {
      title,
      description,
      url,
      siteName: siteConfig.name,
      type: "website",
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
    },
  }
}
