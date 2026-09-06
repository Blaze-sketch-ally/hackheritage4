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
  MODULE_ITEM_TYPES,
  type ModuleItemInput,
  type ModuleItemType,
  type ProgramModuleItem,
} from "@/types/internship-program";

const TYPE_LABEL: Record<ModuleItemType, string> = {
  VIDEO: "Video",
  PDF: "PDF / document",
  LINK: "Link",
  TEXT: "Text",
};

/** Add or edit a module item. VIDEO/PDF/LINK need a URL; TEXT needs body
 * text -- the same rule as the module_items CHECK constraint. */
export function ModuleItemForm({
  item,
  busy,
  onSubmit,
  onCancel,
}: {
  item?: ProgramModuleItem;
  busy: boolean;
  onSubmit: (data: ModuleItemInput & { item_type: ModuleItemType; title: string }) => Promise<void>;
  onCancel: () => void;
}) {
  const [title, setTitle] = useState(item?.title ?? "");
  const [type, setType] = useState<ModuleItemType>(
    (item?.item_type as ModuleItemType) ?? "LINK",
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
          <Label htmlFor="item-title">Item title</Label>
          <Input
            id="item-title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={200}
            disabled={saving || busy}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="item-type">Type</Label>
          <Select
            value={type}
            onValueChange={(v) => setType(v as ModuleItemType)}
            disabled={saving || busy}
          >
            <SelectTrigger id="item-type" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {MODULE_ITEM_TYPES.map((t) => (
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
          <Label htmlFor="item-text">Text</Label>
          <Textarea
            id="item-text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={4}
            maxLength={20000}
            disabled={saving || busy}
          />
        </div>
      ) : (
        <div className="space-y-1.5">
          <Label htmlFor="item-url">URL</Label>
          <Input
            id="item-url"
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
