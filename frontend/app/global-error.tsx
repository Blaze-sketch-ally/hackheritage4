"use client";

import { useEffect } from "react";

// Catches errors thrown by the root layout itself (app/layout.tsx) -- a
// plain app/error.tsx can't catch those, since it renders *inside* the
// root layout. Must render its own <html>/<body> since this replaces the
// entire root layout when it fires. Kept deliberately dependency-free
// (no shared UI components, no Tailwind-dependent classes beyond basics)
// so it still renders even if the failure is in app-wide setup.
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <html lang="en">
      <body>
        <div
          style={{
            display: "flex",
            minHeight: "100vh",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: "0.75rem",
            padding: "2rem",
            textAlign: "center",
            fontFamily: "system-ui, sans-serif",
          }}
        >
          <h1 style={{ fontSize: "1.125rem", fontWeight: 600 }}>Something went wrong</h1>
          <p style={{ color: "#666", fontSize: "0.875rem", maxWidth: "28rem" }}>
            The application failed to load. Please try again.
          </p>
          <button
            onClick={reset}
            style={{
              marginTop: "0.25rem",
              padding: "0.5rem 1rem",
              borderRadius: "0.375rem",
              border: "1px solid #ccc",
              background: "#fff",
              cursor: "pointer",
              fontSize: "0.875rem",
            }}
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
