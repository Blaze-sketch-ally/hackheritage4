import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { ThemeProvider } from "@/components/theme-provider";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/sonner";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#09090b" },
  ],
  width: "device-width",
  initialScale: 1,
};

export const metadata: Metadata = {
  title: {
    default: "AIC Portal — Prove Your Skills, Not Just Claim Them",
    template: "%s | AIC Portal",
  },
  description:
    "Academia-Industry Collaboration Portal: objective skill assessments, explainable job matching, and a recruitment pipeline students and employers can actually trust.",
  applicationName: "AIC Portal",
  authors: [{ name: "AIC Portal Engineering Team" }],
  openGraph: {
    title: "AIC Portal — Objective Skill Verification & Career Matching",
    description:
      "Academia-Industry Collaboration Portal: verifiable skill assessments, transparent job matching, and reliable recruitment pipelines.",
    siteName: "AIC Portal",
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "AIC Portal",
    description:
      "Objective skill assessments, explainable job matching, and recruitment pipelines you can trust.",
  },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >
          <TooltipProvider>{children}</TooltipProvider>
          <Toaster position="bottom-right" richColors closeButton />
        </ThemeProvider>
      </body>
    </html>
  );
}
