import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "AIC Portal — Academia-Industry Collaboration",
    short_name: "AIC Portal",
    description:
      "Objective skill assessments, explainable career matching, and verifiable recruitment pipelines for students, faculty, industry, and institutions.",
    start_url: "/",
    display: "standalone",
    background_color: "#ffffff",
    theme_color: "#4f46e5",
    icons: [
      {
        src: "/favicon.ico",
        sizes: "any",
        type: "image/x-icon",
      },
    ],
  };
}
