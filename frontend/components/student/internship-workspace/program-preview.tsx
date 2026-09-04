import { FileText, Link2, PlayCircle, Type } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type {
  WorkspaceProgramModuleItem,
  WorkspaceProgramPreview,
} from "@/types/internship-workspace";

const ITEM_ICON: Record<string, typeof FileText> = {
  VIDEO: PlayCircle,
  PDF: FileText,
  LINK: Link2,
  TEXT: Type,
};

function ItemRow({ item }: { item: WorkspaceProgramModuleItem }) {
  const Icon = ITEM_ICON[item.item_type] ?? FileText;
  const label = (
    <span className="flex items-center gap-2 text-sm">
      <Icon className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
      {item.title}
    </span>
  );
  return (
    <li>
      {item.item_type !== "TEXT" && item.content_url ? (
        <a
          href={item.content_url}
          target="_blank"
          rel="noopener noreferrer"
          className="hover:underline"
        >
          {label}
        </a>
      ) : (
        label
      )}
    </li>
  );
}

/** Read-only preview of the industry's PUBLISHED internship program.
 * Students never author any of this. Null program (industry hasn't
 * published a curriculum yet) is handled by the caller. */
export function ProgramPreview({ program }: { program: WorkspaceProgramPreview }) {
  const required = program.skills.filter((s) => s.requirement === "REQUIRED");
  const optional = program.skills.filter((s) => s.requirement === "OPTIONAL");

  return (
    <Card>
      <CardHeader>
        <CardTitle>{program.title}</CardTitle>
        {program.summary ? (
          <p className="text-sm text-muted-foreground">{program.summary}</p>
        ) : null}
      </CardHeader>
      <CardContent className="flex flex-col gap-6">
        {(required.length > 0 || optional.length > 0) && (
          <div className="flex flex-col gap-2">
            <p className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
              Skills
            </p>
            {required.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-xs text-muted-foreground">Required:</span>
                {required.map((s) => (
                  <Badge key={s.skill_id} variant="secondary">
                    {s.skill_name}
                  </Badge>
                ))}
              </div>
            )}
            {optional.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-xs text-muted-foreground">Optional:</span>
                {optional.map((s) => (
                  <Badge key={s.skill_id} variant="outline">
                    {s.skill_name}
                  </Badge>
                ))}
              </div>
            )}
          </div>
        )}

        {program.modules.length > 0 ? (
          <div className="flex flex-col gap-4">
            <p className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
              Modules
            </p>
            <ol className="flex flex-col gap-4">
              {program.modules.map((module, i) => (
                <li key={module.id} className="flex gap-3">
                  <span className="font-mono text-xs text-muted-foreground tabular-nums">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">{module.title}</p>
                    {module.description ? (
                      <p className="text-sm text-muted-foreground">{module.description}</p>
                    ) : null}
                    {module.items.length > 0 && (
                      <ul className="mt-1.5 flex flex-col gap-1 border-l pl-3">
                        {module.items.map((item) => (
                          <ItemRow key={item.id} item={item} />
                        ))}
                      </ul>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            The training modules for this internship haven&apos;t been published yet.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
