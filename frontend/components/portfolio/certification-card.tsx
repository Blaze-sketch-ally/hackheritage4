import { ExternalLink, Pencil, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import type { Certification } from "@/types/portfolio";

/** Read-only by default -- same shape/rule as ProjectCard: the industry
 * applicant view renders this exact component with no
 * `onEdit`/`onDelete`, never a second view-only copy. */
export function CertificationCard({
  certification,
  onEdit,
  onDelete,
}: {
  certification: Certification;
  onEdit?: () => void;
  onDelete?: () => void;
}) {
  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between gap-2 space-y-0">
        <div>
          <h3 className="font-medium">{certification.name}</h3>
          <p className="text-sm text-muted-foreground">{certification.issuer}</p>
        </div>
        {(onEdit || onDelete) && (
          <div className="flex shrink-0 gap-1">
            {onEdit && (
              <Button variant="ghost" size="icon-sm" onClick={onEdit} aria-label="Edit certification">
                <Pencil className="size-3.5" />
              </Button>
            )}
            {onDelete && (
              <Button variant="ghost" size="icon-sm" onClick={onDelete} aria-label="Delete certification">
                <Trash2 className="size-3.5" />
              </Button>
            )}
          </div>
        )}
      </CardHeader>
      <CardContent className="space-y-2">
        {certification.issue_date && (
          <p className="text-sm text-muted-foreground">
            Issued {new Date(certification.issue_date).toLocaleDateString(undefined, { year: "numeric", month: "long" })}
          </p>
        )}
        {certification.credential_url && (
          <a
            href={certification.credential_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground hover:underline"
          >
            <ExternalLink className="size-3.5" /> View credential
          </a>
        )}
      </CardContent>
    </Card>
  );
}
