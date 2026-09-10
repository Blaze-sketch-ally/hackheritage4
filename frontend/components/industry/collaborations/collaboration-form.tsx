"use client";

import { useId, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { FieldError } from "@/components/auth/field-error";
import { FormError } from "@/components/auth/form-error";
import { ApiError } from "@/lib/api";
import { resolveRecipient } from "@/lib/industry/collaborations";
import {
  RECIPIENT_TYPE_LABELS,
  type CollaborationCreate,
  type IndustryCollaboration,
  type RecipientResolution,
} from "@/types/industry-collaboration";

interface FieldErrors {
  title?: string;
  description?: string;
  recipient?: string;
}

const textareaClass =
  "w-full rounded-lg border border-input bg-transparent px-2.5 py-2 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50 dark:bg-input/30";

export function CollaborationForm({
  mode,
  initial,
  submitting,
  error,
  onSubmit,
  onCancel,
}: {
  mode: "create" | "edit";
  initial?: IndustryCollaboration;
  submitting: boolean;
  error: string | null;
  onSubmit: (data: CollaborationCreate) => void;
  onCancel: () => void;
}) {
  const [title, setTitle] = useState(initial?.title ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [identifier, setIdentifier] = useState("");
  const [resolved, setResolved] = useState<RecipientResolution | null>(null);
  const [resolving, setResolving] = useState(false);
  const [resolveError, setResolveError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});

  const ids = { title: useId(), description: useId(), identifier: useId() };

  async function handleResolve() {
    if (!identifier.trim() || resolving) return;
    setResolving(true);
    setResolveError(null);
    setResolved(null);
    try {
      const result = await resolveRecipient(identifier.trim());
      setResolved(result);
    } catch (err) {
      setResolveError(
        err instanceof ApiError && err.status === 404
          ? "No Faculty or Institution account found with that username."
          : err instanceof ApiError
            ? err.message
            : "Could not look up that recipient. Please try again.",
      );
    } finally {
      setResolving(false);
    }
  }

  function validate(): boolean {
    const errors: FieldErrors = {};
    if (!title.trim()) errors.title = "A title is required.";
    if (title.trim().length > 200) errors.title = "Keep the title under 200 characters.";
    if (!description.trim()) errors.description = "A description is required.";
    if (mode === "create" && !resolved) {
      errors.recipient = "Look up and select a recipient before saving.";
    }
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (submitting || !validate()) return;

    const recipientId = mode === "create" ? (resolved as RecipientResolution).id : (initial as IndustryCollaboration).recipient_id;

    const data: CollaborationCreate = {
      title: title.trim(),
      description: description.trim(),
      recipient_id: recipientId,
    };
    onSubmit(data);
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-6">
      <FormError message={error} />

      {mode === "create" ? (
        <Card>
          <CardHeader>
            <CardTitle>Recipient</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor={ids.identifier}>Faculty or Institution username</Label>
              <div className="flex gap-2">
                <Input
                  id={ids.identifier}
                  value={identifier}
                  onChange={(e) => {
                    setIdentifier(e.target.value);
                    setResolved(null);
                  }}
                  placeholder="e.g. drrao"
                  disabled={submitting}
                  aria-invalid={!!fieldErrors.recipient}
                />
                <Button
                  type="button"
                  variant="outline"
                  className="shrink-0"
                  onClick={handleResolve}
                  disabled={resolving || submitting || !identifier.trim()}
                >
                  {resolving ? "Looking up..." : "Find"}
                </Button>
              </div>
              <FieldError
                id={`${ids.identifier}-error`}
                message={resolveError ?? fieldErrors.recipient}
              />
            </div>
            {resolved ? (
              <div className="flex items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm">
                <span className="font-medium">{resolved.full_name ?? "(no name set)"}</span>
                <Badge variant="ghost">{RECIPIENT_TYPE_LABELS[resolved.role]}</Badge>
              </div>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Proposal Details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor={ids.title}>Title</Label>
            <Input
              id={ids.title}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              maxLength={200}
              placeholder="e.g. Joint Research Proposal"
              disabled={submitting}
              aria-invalid={!!fieldErrors.title}
            />
            <FieldError id={`${ids.title}-error`} message={fieldErrors.title} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={ids.description}>Description</Label>
            <textarea
              id={ids.description}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={6}
              maxLength={10000}
              placeholder="What you're proposing, goals, scope..."
              disabled={submitting}
              className={textareaClass}
              aria-invalid={!!fieldErrors.description}
            />
            <FieldError id={`${ids.description}-error`} message={fieldErrors.description} />
          </div>
        </CardContent>
      </Card>

      <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
        <Button
          type="button"
          variant="outline"
          className="sm:w-auto"
          onClick={onCancel}
          disabled={submitting}
        >
          Cancel
        </Button>
        <Button type="submit" className="sm:w-auto" disabled={submitting}>
          {submitting ? "Saving..." : mode === "create" ? "Save Draft" : "Save Changes"}
        </Button>
      </div>
    </form>
  );
}
