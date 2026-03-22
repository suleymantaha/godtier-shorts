import type { MetadataRoute } from "next"

import { siteConfig } from "@/lib/site"

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: siteConfig.name,
    short_name: siteConfig.shortName,
    description: siteConfig.description,
    start_url: "/",
    display: "standalone",
    background_color: "#061117",
    theme_color: "#061117",
    icons: [
      {
        src: "/mark.svg",
        sizes: "any",
        type: "image/svg+xml",
      },
    ],
  }
}
