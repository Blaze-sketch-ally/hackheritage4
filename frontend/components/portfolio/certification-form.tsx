"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";
import { createCertification, updateCertification } from "@/lib/student/portfolio";
import type { Certification } from "@/types/portfolio";

/** Handles both create and edit -- one form, same convention as
 * ProjectForm/OpportunityForm. Inline, not a modal (see ProjectForm's
 * own docstring for why). */
export function CertificationForm({
  certification,
  onSaved,
  onCancel,
}: {
  certification?: Certification;
  onSaved: () => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(certification?.name ?? "");
  const [issuer, setIssuer] = useState(certification?.issuer ?? "");
  const [issueDate, setIssueDate] = useState(certification?.issue_date ?? "");
  const [credentialUrl, setCredentialUrl] = useState(certification?.credential_url ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      if (certification) {
        await updateCertification(certification.id, {
          name,
          issuer,
          issue_date: issueDate || null,
          credential_url: credentialUrl || null,
        });
      } else {
        await createCertification({
          name,
          issuer,
          issue_date: issueDate || null,
          credential_url: credentialUrl || null,
        });
      }
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save this certification.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{certification ? "Edit Certification" : "Add Certification"}</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="cert-name">Certification name</Label>
            <Input id="cert-name" value={name} onChange={(e) => setName(e.target.value)} required />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="cert-issuer">Issuer</Label>
            <Input id="cert-issuer" value={issuer} onChange={(e) => setIssuer(e.target.value)} required />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="cert-date">Issue date</Label>
              <Input id="cert-date" type="date" value={issueDate} onChange={(e) => setIssueDate(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="cert-url">Credential URL</Label>
              <Input
                id="cert-url"
                type="url"
                value={credentialUrl}
                onChange={(e) => setCredentialUrl(e.target.value)}
                placeholder="https://credential.example.com/..."
              />
            </div>
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="flex gap-2">
            <Button type="submit" disabled={saving}>
              {saving ? "Saving..." : "Save"}
            </Button>
            <Button type="button" variant="outline" onClick={onCancel} disabled={saving}>
              Cancel
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
