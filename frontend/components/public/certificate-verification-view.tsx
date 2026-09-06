"use client";

import { useEffect, useState } from "react";
import { BadgeCheck, ShieldAlert, ShieldX } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { ApiError } from "@/lib/api";
import { verifyCertificate } from "@/lib/public/certificates";
import type { PublicCertificate } from "@/types/internship-completion";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; certificate: PublicCertificate };

function fmt(value: string | null): string {
  if (!value) return "—";
  const d = new Date(value);
  return Number.isNaN(d.getTime())
    ? value
    : d.toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" });
}

/** Public, unauthenticated verification of an AIC internship certificate.
 * Calls ONLY GET /api/v1/certificates/verify/{number} -- backed by
 * public.verify_internship_certificate, which exposes exactly these
 * fields and nothing private. */
export function CertificateVerificationView({ certificateNumber }: { certificateNumber: string }) {
  const [state, setState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    verifyCertificate(certificateNumber)
      .then((certificate) => {
        if (!cancelled) setState({ status: "ready", certificate });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not verify this certificate."),
        });
      });
    return () => {
      cancelled = true;
    };
  }, [certificateNumber]);

  if (state.status === "loading") {
    return (
      <div aria-busy="true" aria-label="Verifying certificate">
        <Card className="animate-pulse">
          <CardContent className="space-y-2 py-8">
            <div className="mx-auto h-5 w-2/3 rounded bg-muted" />
            <div className="mx-auto h-3 w-1/2 rounded bg-muted" />
          </CardContent>
        </Card>
      </div>
    );
  }

  if (state.status === "error") {
    const notFound = state.error.status === 404;
    const malformed = state.error.status === 422;
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
          <ShieldX className="size-10 text-destructive" />
          <div>
            <p className="font-medium">
              {malformed
                ? "That doesn't look like a valid certificate number."
                : notFound
                  ? "No certificate matches this number."
                  : "Could not verify this certificate."}
            </p>
            <p className="text-sm text-muted-foreground">{state.error.message}</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  const cert = state.certificate;
  const valid = cert.status === "VALID";

  return (
    <Card>
      <CardContent className="flex flex-col items-center gap-4 py-10 text-center">
        {valid ? (
          <BadgeCheck className="size-10 text-emerald-600" />
        ) : (
          <ShieldAlert className="size-10 text-destructive" />
        )}
        <Badge
          variant={valid ? undefined : "destructive"}
          className={valid ? "bg-emerald-600 text-white hover:bg-emerald-600" : undefined}
        >
          {valid ? "Valid certificate" : "Revoked certificate"}
        </Badge>
        <div>
          <p className="text-lg font-semibold">{cert.student_name ?? "—"}</p>
          <p className="text-sm text-muted-foreground">
            completed an internship at {cert.company_name ?? "—"}
          </p>
          {cert.title ? <p className="text-sm text-muted-foreground">{cert.title}</p> : null}
        </div>
        <div className="flex flex-col gap-1 text-sm">
          <p>
            <span className="text-muted-foreground">Certificate number: </span>
            <span className="font-mono">{cert.certificate_number}</span>
          </p>
          <p>
            <span className="text-muted-foreground">Issued: </span>
            {fmt(cert.issued_at)}
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
