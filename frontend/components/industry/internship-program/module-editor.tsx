"use client";

import { useState } from "react";
import {
  ChevronDown,
  ChevronUp,
  Eye,
  EyeOff,
  FileText,
  Link2,
  Loader2,
  PlayCircle,
  Plus,
  Type,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ModuleItemForm } from "@/components/industry/internship-program/module-item-form";
import { AssignmentForm } from "@/components/industry/internship-program/assignment-form";
import {
  ASSIGNMENT_TYPE_LABEL,
  type AssignmentInput,
  type AssignmentType,
  type ModuleInput,
  type ModuleItemInput,
  type ModuleItemType,
  type ProgramAssignment,
  type ProgramModule,
  type ProgramModuleItem,
  type ProgramSkill,
} from "@/types/internship-program";

const ITEM_ICON: Record<string, typeof FileText> = {
  VIDEO: PlayCircle,
  PDF: FileText,
  LINK: Link2,
  TEXT: Type,
};

/** Every handler resolves to `true` on success -- never throws. */
export interface ModuleHandlers {
  onUpdateModule: (moduleId: string, data: ModuleInput) => Promise<boolean>;
  onMoveModule: (moduleId: string, dir: -1 | 1) => Promise<boolean>;
  onAddItem: (
    moduleId: string,
    data: ModuleItemInput & { item_type: ModuleItemType; title: string },
  ) => Promise<boolean>;
  onUpdateItem: (moduleId: string, itemId: string, data: ModuleItemInput) => Promise<boolean>;
  onMoveItem: (moduleId: string, itemId: string, dir: -1 | 1) => Promise<boolean>;
  onAddAssignment: (
    moduleId: string,
    data: AssignmentInput & { title: string },
  ) => Promise<boolean>;
  onUpdateAssignment: (
    moduleId: string,
    assignmentId: string,
    data: AssignmentInput,
  ) => Promise<boolean>;
  onMoveAssignment: (moduleId: string, assignmentId: string, dir: -1 | 1) => Promise<boolean>;
}

function ItemRow({
  moduleId,
  item,
  index,
  count,
  busy,
  handlers,
}: {
  moduleId: string;
  item: ProgramModuleItem;
  index: number;
  count: number;
  busy: boolean;
  handlers: ModuleHandlers;
}) {
  const [editing, setEditing] = useState(false);
  const Icon = ITEM_ICON[item.item_type] ?? FileText;

  if (editing) {
    return (
      <ModuleItemForm
        item={item}
        busy={busy}
        onSubmit={async (data) => {
          if (await handlers.onUpdateItem(moduleId, item.id, data)) setEditing(false);
        }}
        onCancel={() => setEditing(false)}
      />
    );
  }

  return (
    <div className="flex items-center gap-2 rounded-md border px-2.5 py-1.5 text-sm">
      <Icon className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
      <span className={item.is_published ? "min-w-0 flex-1 truncate" : "min-w-0 flex-1 truncate text-muted-foreground line-through"}>
        {item.title}
      </span>
      {!item.is_published && <Badge variant="outline">Hidden</Badge>}
      <Button
        size="icon-xs"
        variant="ghost"
        aria-label="Move item up"
        disabled={busy || index === 0}
        onClick={() => { void handlers.onMoveItem(moduleId, item.id, -1); }}
      >
        <ChevronUp />
      </Button>
      <Button
        size="icon-xs"
        variant="ghost"
        aria-label="Move item down"
        disabled={busy || index === count - 1}
        onClick={() => { void handlers.onMoveItem(moduleId, item.id, 1); }}
      >
        <ChevronDown />
      </Button>
      <Button
        size="icon-xs"
        variant="ghost"
        aria-label={item.is_published ? "Hide item from students" : "Show item to students"}
        disabled={busy}
        onClick={() => { void handlers.onUpdateItem(moduleId, item.id, { is_published: !item.is_published }); }}
      >
        {item.is_published ? <Eye /> : <EyeOff />}
      </Button>
      <Button size="xs" variant="ghost" disabled={busy} onClick={() => setEditing(true)}>
        Edit
      </Button>
    </div>
  );
}

function AssignmentRow({
  moduleId,
  assignment,
  index,
  count,
  busy,
  programSkills,
  handlers,
}: {
  moduleId: string;
  assignment: ProgramAssignment;
  index: number;
  count: number;
  busy: boolean;
  programSkills: ProgramSkill[];
  handlers: ModuleHandlers;
}) {
  const [editing, setEditing] = useState(false);

  if (editing) {
    return (
      <AssignmentForm
        assignment={assignment}
        programSkills={programSkills}
        busy={busy}
        onSubmit={async (data) => {
          if (await handlers.onUpdateAssignment(moduleId, assignment.id, data)) {
            setEditing(false);
          }
        }}
        onCancel={() => setEditing(false)}
      />
    );
  }

  const typeLabel =
    ASSIGNMENT_TYPE_LABEL[assignment.assignment_type as AssignmentType] ??
    assignment.assignment_type;

  return (
    <div className="flex items-center gap-2 rounded-md border border-primary/20 bg-primary/[0.03] px-2.5 py-1.5 text-sm">
      <Badge variant="outline" className="shrink-0">
        {typeLabel}
      </Badge>
      <span
        className={
          assignment.is_published
            ? "min-w-0 flex-1 truncate"
            : "min-w-0 flex-1 truncate text-muted-foreground line-through"
        }
      >
        {assignment.title}
      </span>
      {!assignment.is_published && <Badge variant="outline">Hidden</Badge>}
      <Button
        size="icon-xs"
        variant="ghost"
        aria-label="Move assignment up"
        disabled={busy || index === 0}
        onClick={() => {
          void handlers.onMoveAssignment(moduleId, assignment.id, -1);
        }}
      >
        <ChevronUp />
      </Button>
      <Button
        size="icon-xs"
        variant="ghost"
        aria-label="Move assignment down"
        disabled={busy || index === count - 1}
        onClick={() => {
          void handlers.onMoveAssignment(moduleId, assignment.id, 1);
        }}
      >
        <ChevronDown />
      </Button>
      <Button
        size="icon-xs"
        variant="ghost"
        aria-label={
          assignment.is_published
            ? "Hide assignment from students"
            : "Show assignment to students"
        }
        disabled={busy}
        onClick={() => {
          void handlers.onUpdateAssignment(moduleId, assignment.id, {
            is_published: !assignment.is_published,
          });
        }}
      >
        {assignment.is_published ? <Eye /> : <EyeOff />}
      </Button>
      <Button size="xs" variant="ghost" disabled={busy} onClick={() => setEditing(true)}>
        Edit
      </Button>
    </div>
  );
}

/** One module: inline-editable metadata, a "visible to students" toggle,
 * move up/down, and its ordered items + assignments (each with the same
 * controls) plus add forms. No delete -- the schema has no DELETE policy;
 * hiding (is_published=false) is the remove-from-students mechanism. */
export function ModuleEditor({
  module,
  index,
  count,
  busy,
  programSkills,
  handlers,
}: {
  module: ProgramModule;
  index: number;
  count: number;
  busy: boolean;
  programSkills: ProgramSkill[];
  handlers: ModuleHandlers;
}) {
  const [editing, setEditing] = useState(false);
  const [addingItem, setAddingItem] = useState(false);
  const [addingAssignment, setAddingAssignment] = useState(false);
  const [title, setTitle] = useState(module.title);
  const [description, setDescription] = useState(module.description ?? "");
  const [savingMeta, setSavingMeta] = useState(false);

  async function saveMeta() {
    setSavingMeta(true);
    const ok = await handlers.onUpdateModule(module.id, {
      title: title.trim(),
      description: description.trim() ? description.trim() : null,
    });
    setSavingMeta(false);
    if (ok) setEditing(false); // else the parent shows the error, form stays open
  }

  return (
    <Card>
      <CardContent className="flex flex-col gap-3 py-4">
        <div className="flex items-start gap-2">
          <span className="mt-1 font-mono text-xs text-muted-foreground tabular-nums">
            {String(index + 1).padStart(2, "0")}
          </span>
          <div className="min-w-0 flex-1">
            {editing ? (
              <div className="flex flex-col gap-2">
                <div className="space-y-1.5">
                  <Label htmlFor={`m-title-${module.id}`}>Module title</Label>
                  <Input
                    id={`m-title-${module.id}`}
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    maxLength={200}
                    disabled={savingMeta || busy}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor={`m-desc-${module.id}`}>Description</Label>
                  <Textarea
                    id={`m-desc-${module.id}`}
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    rows={2}
                    maxLength={4000}
                    disabled={savingMeta || busy}
                  />
                </div>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    onClick={saveMeta}
                    disabled={savingMeta || busy || !title.trim()}
                  >
                    {savingMeta && <Loader2 className="size-3.5 animate-spin" />}
                    Save
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setEditing(false)} disabled={savingMeta}>
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <>
                <div className="flex flex-wrap items-center gap-2">
                  <p className={module.is_published ? "font-medium" : "font-medium text-muted-foreground line-through"}>
                    {module.title}
                  </p>
                  {!module.is_published && <Badge variant="outline">Hidden</Badge>}
                </div>
                {module.description ? (
                  <p className="text-sm text-muted-foreground">{module.description}</p>
                ) : null}
              </>
            )}
          </div>

          {!editing && (
            <div className="flex shrink-0 items-center">
              <Button
                size="icon-xs"
                variant="ghost"
                aria-label="Move module up"
                disabled={busy || index === 0}
                onClick={() => { void handlers.onMoveModule(module.id, -1); }}
              >
                <ChevronUp />
              </Button>
              <Button
                size="icon-xs"
                variant="ghost"
                aria-label="Move module down"
                disabled={busy || index === count - 1}
                onClick={() => { void handlers.onMoveModule(module.id, 1); }}
              >
                <ChevronDown />
              </Button>
              <Button
                size="icon-xs"
                variant="ghost"
                aria-label={module.is_published ? "Hide module from students" : "Show module to students"}
                disabled={busy}
                onClick={() => { void handlers.onUpdateModule(module.id, { is_published: !module.is_published }); }}
              >
                {module.is_published ? <Eye /> : <EyeOff />}
              </Button>
              <Button size="xs" variant="ghost" disabled={busy} onClick={() => setEditing(true)}>
                Edit
              </Button>
            </div>
          )}
        </div>

        <div className="flex flex-col gap-1.5 pl-6">
          {module.items.map((item, i) => (
            <ItemRow
              key={item.id}
              moduleId={module.id}
              item={item}
              index={i}
              count={module.items.length}
              busy={busy}
              handlers={handlers}
            />
          ))}

          {addingItem ? (
            <ModuleItemForm
              busy={busy}
              onSubmit={async (data) => {
                if (await handlers.onAddItem(module.id, data)) setAddingItem(false);
              }}
              onCancel={() => setAddingItem(false)}
            />
          ) : (
            <Button
              size="xs"
              variant="outline"
              className="w-fit"
              disabled={busy}
              onClick={() => setAddingItem(true)}
            >
              <Plus className="size-3" /> Add item
            </Button>
          )}
        </div>

        <div className="flex flex-col gap-1.5 pl-6">
          <p className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
            Assignments
          </p>
          {module.assignments.map((assignment, i) => (
            <AssignmentRow
              key={assignment.id}
              moduleId={module.id}
              assignment={assignment}
              index={i}
              count={module.assignments.length}
              busy={busy}
              programSkills={programSkills}
              handlers={handlers}
            />
          ))}

          {addingAssignment ? (
            <AssignmentForm
              programSkills={programSkills}
              busy={busy}
              onSubmit={async (data) => {
                if (await handlers.onAddAssignment(module.id, data)) {
                  setAddingAssignment(false);
                }
              }}
              onCancel={() => setAddingAssignment(false)}
            />
          ) : (
            <Button
              size="xs"
              variant="outline"
              className="w-fit"
              disabled={busy}
              onClick={() => setAddingAssignment(true)}
            >
              <Plus className="size-3" /> Add assignment
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
