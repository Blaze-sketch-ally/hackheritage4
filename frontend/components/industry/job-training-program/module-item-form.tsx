"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  JOB_PROGRAM_ITEM_TYPES,
  type JobProgramItemInput,
  type JobProgramItemResponse,
  type JobProgramItemType,
} from "@/types/job-training-program";

const TYPE_LABEL: Record<JobProgramItemType, string> = {
  VIDEO: "Video",
  PDF: "PDF / document",
  LINK: "Link",
  TEXT: "Text",
};

/** Add or edit a module item. VIDEO/PDF/LINK need a URL; TEXT needs body
 * text -- the same rule as the job_program_items CHECK constraint. Mirrors
 * internship-program/module-item-form.tsx. */
export function JobProgramItemForm({
  item,
  busy,
  onSubmit,
  onCancel,
}: {
  item?: JobProgramItemResponse;
  busy: boolean;
  onSubmit: (
    data: JobProgramItemInput & { item_type: JobProgramItemType; title: string },
  ) => Promise<void>;
  onCancel: () => void;
}) {
  const [title, setTitle] = useState(item?.title ?? "");
  const [type, setType] = useState<JobProgramItemType>(
    (item?.item_type as JobProgramItemType) ?? "LINK",
  );
  const [url, setUrl] = useState(item?.content_url ?? "");
  const [text, setText] = useState(item?.content_text ?? "");
  const [saving, setSaving] = useState(false);

  const isText = type === "TEXT";
  const invalid = !title.trim() || (isText ? !text.trim() : !url.trim());

  async function submit() {
    setSaving(true);
    try {
      await onSubmit({
        title: title.trim(),
        item_type: type,
        content_url: isText ? null : url.trim(),
        content_text: isText ? text.trim() : null,
      });
    } catch {
      // The parent surfaces the failure in its top-level error banner; the
      // form stays open so the industry user can retry.
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-dashed p-3">
      <div className="grid gap-3 sm:grid-cols-[1fr_10rem]">
        <div className="space-y-1.5">
          <Label htmlFor="job-item-title">Item title</Label>
          <Input
            id="job-item-title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={200}
            disabled={saving || busy}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="job-item-type">Type</Label>
          <Select
            value={type}
            onValueChange={(v) => setType(v as JobProgramItemType)}
            disabled={saving || busy}
          >
            <SelectTrigger id="job-item-type" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {JOB_PROGRAM_ITEM_TYPES.map((t) => (
                <SelectItem key={t} value={t}>
                  {TYPE_LABEL[t]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {isText ? (
        <div className="space-y-1.5">
          <Label htmlFor="job-item-text">Text</Label>
          <Textarea
            id="job-item-text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={4}
            maxLength={20000}
            disabled={saving || busy}
          />
        </div>
      ) : (
        <div className="space-y-1.5">
          <Label htmlFor="job-item-url">URL</Label>
          <Input
            id="job-item-url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            maxLength={2000}
            placeholder="https://…"
            disabled={saving || busy}
          />
        </div>
      )}

      <div className="flex gap-2">
        <Button size="sm" onClick={submit} disabled={saving || busy || invalid}>
          {saving && <Loader2 className="size-3.5 animate-spin" />}
          {item ? "Save item" : "Add item"}
        </Button>
        <Button size="sm" variant="ghost" onClick={onCancel} disabled={saving}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
