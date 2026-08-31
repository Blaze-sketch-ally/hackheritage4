import { Code2, ExternalLink, Pencil, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import type { Project } from "@/types/portfolio";

/** Read-only by default -- the industry applicant view renders this
 * exact component with no `onEdit`/`onDelete` at all, so there is only
 * ever one project-card implementation, never a second "view-only"
 * copy. The owning student's own portfolio pages are what pass the
 * edit/delete actions in. */
export function ProjectCard({
  project,
  onEdit,
  onDelete,
}: {
  project: Project;
  onEdit?: () => void;
  onDelete?: () => void;
}) {
  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between gap-2 space-y-0">
        <h3 className="font-medium">{project.title}</h3>
        {(onEdit || onDelete) && (
          <div className="flex shrink-0 gap-1">
            {onEdit && (
              <Button variant="ghost" size="icon-sm" onClick={onEdit} aria-label="Edit project">
                <Pencil className="size-3.5" />
              </Button>
            )}
            {onDelete && (
              <Button variant="ghost" size="icon-sm" onClick={onDelete} aria-label="Delete project">
                <Trash2 className="size-3.5" />
              </Button>
            )}
          </div>
        )}
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground">{project.description}</p>
        {project.technologies.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {project.technologies.map((tech) => (
              <Badge key={tech} variant="secondary">
                {tech}
              </Badge>
            ))}
          </div>
        )}
        {(project.github_url || project.project_url) && (
          <div className="flex flex-wrap gap-3 text-sm">
            {project.github_url && (
              <a
                href={project.github_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-muted-foreground hover:text-foreground hover:underline"
              >
                <Code2 className="size-3.5" /> GitHub
              </a>
            )}
            {project.project_url && (
              <a
                href={project.project_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-muted-foreground hover:text-foreground hover:underline"
              >
                <ExternalLink className="size-3.5" /> Live project
              </a>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
