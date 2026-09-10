import { FileText, Link2, PlayCircle, Type } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type {
  StudentJobProgramAssignment,
  StudentJobProgramItem,
  StudentJobProgramModule,
  StudentJobProgramSkill,
} from "@/types/job-training";

const ITEM_ICON: Record<string, typeof FileText> = {
  VIDEO: PlayCircle,
  PDF: FileText,
  LINK: Link2,
  TEXT: Type,
};

const ITEM_ACTION_LABEL: Record<string, string> = {
  VIDEO: "Watch video",
  PDF: "Open PDF",
  LINK: "Open link",
};

function ItemRow({ item }: { item: StudentJobProgramItem }) {
  const Icon = ITEM_ICON[item.item_type] ?? FileText;
  const isLinked = item.item_type !== "TEXT" && !!item.content_url;

  return (
    <li className="flex flex-col gap-1">
      <span className="flex items-start gap-2 text-sm">
        <Icon className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
        <span className="min-w-0 break-words">{item.title}</span>
      </span>
      {isLinked ? (
        <a
          href={item.content_url!}
          target="_blank"
          rel="noopener noreferrer"
          className="ml-5 w-fit text-xs text-primary underline-offset-4 hover:underline"
        >
          {ITEM_ACTION_LABEL[item.item_type] ?? "Open resource"} (opens in a new tab)
        </a>
      ) : null}
      {item.item_type === "TEXT" && item.content_text ? (
        <p className="ml-5 max-w-prose text-sm whitespace-pre-wrap text-muted-foreground">
          {item.content_text}
        </p>
      ) : null}
    </li>
  );
}

function AssignmentCard({ assignment }: { assignment: StudentJobProgramAssignment }) {
  return (
    <div className="rounded-lg border border-border/60 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <p className="min-w-0 flex-1 font-medium break-words">{assignment.title}</p>
        <Badge variant="secondary">{assignment.assignment_type}</Badge>
        <Badge variant={assignment.is_required ? "default" : "outline"}>
          {assignment.is_required ? "Required" : "Optional"}
        </Badge>
      </div>

      {assignment.description ? (
        <p className="mt-1.5 max-w-prose text-sm whitespace-pre-wrap text-muted-foreground">
          {assignment.description}
        </p>
      ) : null}
      {assignment.instructions ? (
        <p className="mt-1.5 max-w-prose text-sm whitespace-pre-wrap text-muted-foreground">
          {assignment.instructions}
        </p>
      ) : null}

      <dl className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <div>
          <dt className="inline font-medium">Submission: </dt>
          <dd className="inline">{assignment.submission_kind}</dd>
        </div>
        {assignment.repo_required ? (
          <div>
            <dt className="inline font-medium">Repository: </dt>
            <dd className="inline">required</dd>
          </div>
        ) : null}
        {assignment.live_url_expected ? (
          <div>
            <dt className="inline font-medium">Live URL: </dt>
            <dd className="inline">expected</dd>
          </div>
        ) : null}
        {assignment.due_offset_days != null ? (
          <div>
            <dt className="inline font-medium">Due: </dt>
            <dd className="inline">
              {assignment.due_offset_days} day{assignment.due_offset_days === 1 ? "" : "s"} after
              enrollment
            </dd>
          </div>
        ) : null}
        {assignment.max_score != null ? (
          <div>
            <dt className="inline font-medium">Max score: </dt>
            <dd className="inline">{assignment.max_score}</dd>
          </div>
        ) : null}
      </dl>

      <p className="mt-2 text-xs text-muted-foreground">
        Submissions aren&apos;t open yet — review the requirements so you&apos;re ready.
      </p>
    </div>
  );
}

function ModuleBlock({ module, index }: { module: StudentJobProgramModule; index: number }) {
  return (
    <li className="flex gap-3">
      <span className="font-mono text-xs text-muted-foreground tabular-nums">
        {String(index + 1).padStart(2, "0")}
      </span>
      <div className="min-w-0 flex-1">
        <p className="font-medium break-words">{module.title}</p>
        {module.description ? (
          <p className="text-sm break-words text-muted-foreground">{module.description}</p>
        ) : null}

        {module.items.length > 0 && (
          <ul className="mt-2 flex flex-col gap-2 border-l pl-3">
            {module.items.map((item) => (
              <ItemRow key={item.id} item={item} />
            ))}
          </ul>
        )}

        {module.assignments.length > 0 && (
          <div className="mt-3 flex flex-col gap-2">
            <p className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
              Assignments
            </p>
            {module.assignments.map((a) => (
              <AssignmentCard key={a.id} assignment={a} />
            ))}
          </div>
        )}

        {module.items.length === 0 && module.assignments.length === 0 ? (
          <p className="mt-1 text-sm text-muted-foreground">
            No published content in this module yet.
          </p>
        ) : null}
      </div>
    </li>
  );
}

/** Read-only rendering of the student's PUBLISHED Job Training program.
 * Only published modules / items / assignments reach here -- the backend
 * (public.student_can_access_job_program + the per-table RLS) has already
 * filtered them. Students never author or submit anything here in this
 * phase. */
export function JobTrainingProgramContent({
  modules,
  skills,
}: {
  modules: StudentJobProgramModule[];
  skills: StudentJobProgramSkill[];
}) {
  const required = skills.filter((s) => s.requirement === "REQUIRED");
  const optional = skills.filter((s) => s.requirement === "OPTIONAL");

  return (
    <Card>
      <CardHeader>
        <CardTitle>Program content</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-6">
        {(required.length > 0 || optional.length > 0) && (
          <div className="flex flex-col gap-2">
            <p className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
              Skills you&apos;ll build
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

        {modules.length > 0 ? (
          <div className="flex flex-col gap-4">
            <p className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
              Modules
            </p>
            <ol className="flex flex-col gap-5">
              {modules.map((module, i) => (
                <ModuleBlock key={module.id} module={module} index={i} />
              ))}
            </ol>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            The company hasn&apos;t published any training modules yet. Check back soon.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
