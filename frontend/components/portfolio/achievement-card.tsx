import { ExternalLink, Pencil, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import type { Achievement } from "@/types/portfolio";

/** Read-only by default -- same shape/rule as ProjectCard/CertificationCard:
 * the industry applicant view renders this exact component with no
 * `onEdit`/`onDelete`, never a second view-only copy. */
export function AchievementCard({
  achievement,
  onEdit,
  onDelete,
}: {
  achievement: Achievement;
  onEdit?: () => void;
  onDelete?: () => void;
}) {
  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between gap-2 space-y-0">
        <div>
          <h3 className="font-medium">{achievement.title}</h3>
          {achievement.issuing_organization && (
            <p className="text-sm text-muted-foreground">{achievement.issuing_organization}</p>
          )}
        </div>
        {(onEdit || onDelete) && (
          <div className="flex shrink-0 gap-1">
            {onEdit && (
              <Button variant="ghost" size="icon-sm" onClick={onEdit} aria-label="Edit achievement">
                <Pencil className="size-3.5" />
              </Button>
            )}
            {onDelete && (
              <Button variant="ghost" size="icon-sm" onClick={onDelete} aria-label="Delete achievement">
                <Trash2 className="size-3.5" />
              </Button>
            )}
          </div>
        )}
      </CardHeader>
      <CardContent className="space-y-2">
        {achievement.description && <p className="text-sm">{achievement.description}</p>}
        {achievement.achievement_date && (
          <p className="text-sm text-muted-foreground">
            {new Date(achievement.achievement_date).toLocaleDateString(undefined, { year: "numeric", month: "long" })}
          </p>
        )}
        {achievement.url && (
          <a
            href={achievement.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground hover:underline"
          >
            <ExternalLink className="size-3.5" /> View
          </a>
        )}
      </CardContent>
    </Card>
  );
}
