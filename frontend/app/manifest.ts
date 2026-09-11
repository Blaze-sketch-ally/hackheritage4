import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "SkillBridge — Academia-Industry Collaboration",
    short_name: "SkillBridge",
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
      {
        src: "/branding/skillbridge-emblem-192.png",
        sizes: "192x192",
        type: "image/png",
      },
      {
        src: "/branding/skillbridge-emblem-512.png",
        sizes: "512x512",
        type: "image/png",
      },
    ],
  };
}
