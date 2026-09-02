"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { FormError } from "@/components/auth/form-error";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { isValidUrl } from "@/lib/validations";
import type { CertificationInput, StudentCertification } from "@/types/student-portfolio";

const EMPTY: CertificationInput = {
  name: "",
  issuing_organization: "",
  issue_date: "",
  expiry_date: "",
  credential_id: "",
  credential_url: "",
};

function toInput(c: StudentCertification): CertificationInput {
  return {
    name: c.name,
    issuing_organization: c.issuing_organization ?? "",
    issue_date: c.issue_date ?? "",
    expiry_date: c.expiry_date ?? "",
    credential_id: c.credential_id ?? "",
    credential_url: c.credential_url ?? "",
  };
}

export function normalizeCertificationInput(form: CertificationInput): CertificationInput {
  return {
    name: form.name.trim(),
    issuing_organization: form.issuing_organization?.trim() || null,
    issue_date: form.issue_date || null,
    expiry_date: form.expiry_date || null,
    credential_id: form.credential_id?.trim() || null,
    credential_url: form.credential_url?.trim() || null,
  };
}

export function CertificationFormDialog({
  open,
  onOpenChange,
  certification,
  submitting,
  error,
  onSubmit,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  certification: StudentCertification | null;
  submitting: boolean;
  error: string | null;
  onSubmit: (input: CertificationInput) => void;
}) {
  const [form, setForm] = useState<CertificationInput>(EMPTY);
  const [localError, setLocalError] = useState<string | null>(null);

  const [wasOpen, setWasOpen] = useState(open);
  if (open !== wasOpen) {
    setWasOpen(open);
    if (open) {
      setForm(certification ? toInput(certification) : EMPTY);
      setLocalError(null);
    }
  }

  function set<K extends keyof CertificationInput>(key: K, value: CertificationInput[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function handleSubmit() {
    setLocalError(null);
    if (!form.name.trim()) {
      setLocalError("Give your certification a name.");
      return;
    }
    if (form.credential_url && form.credential_url.trim() && !isValidUrl(form.credential_url)) {
      setLocalError("Credential URL must be a valid http(s) URL.");
      return;
    }
    if (form.issue_date && form.expiry_date && form.expiry_date < form.issue_date) {
      setLocalError("Expiry date can't be before the issue date.");
      return;
    }
    onSubmit(normalizeCertificationInput(form));
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{certification ? "Edit certification" : "Add a certification"}</DialogTitle>
          <DialogDescription>
            A credential you earned. Portfolio evidence only — it doesn&apos;t verify a skill.
          </DialogDescription>
        </DialogHeader>

        <FormError message={localError ?? error} />

        <div className="max-h-[60vh] space-y-4 overflow-y-auto pr-1">
          <div className="space-y-1.5">
            <Label htmlFor="cert-name">Name *</Label>
            <Input
              id="cert-name"
              value={form.name}
              onChange={(e) => set("name", e.target.value)}
              placeholder="e.g. AWS Certified Cloud Practitioner"
              maxLength={200}
              disabled={submitting}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="cert-org">Issuing organization</Label>
            <Input
              id="cert-org"
              value={form.issuing_organization ?? ""}
              onChange={(e) => set("issuing_organization", e.target.value)}
              placeholder="e.g. Amazon Web Services"
              maxLength={200}
              disabled={submitting}
            />
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="cert-issue">Issue date</Label>
              <Input
                id="cert-issue"
                type="date"
                value={form.issue_date ?? ""}
                onChange={(e) => set("issue_date", e.target.value)}
                disabled={submitting}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="cert-expiry">Expiry date</Label>
              <Input
                id="cert-expiry"
                type="date"
                value={form.expiry_date ?? ""}
                onChange={(e) => set("expiry_date", e.target.value)}
                disabled={submitting}
              />
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="cert-id">Credential ID</Label>
              <Input
                id="cert-id"
                value={form.credential_id ?? ""}
                onChange={(e) => set("credential_id", e.target.value)}
                maxLength={200}
                disabled={submitting}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="cert-url">Credential URL</Label>
              <Input
                id="cert-url"
                value={form.credential_url ?? ""}
                onChange={(e) => set("credential_url", e.target.value)}
                placeholder="https://..."
                inputMode="url"
                disabled={submitting}
              />
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={submitting}>
            {submitting ? "Saving..." : certification ? "Save changes" : "Add certification"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
