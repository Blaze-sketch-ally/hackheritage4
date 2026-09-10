"use client";

import Link from "next/link";
import { Building2, GraduationCap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { CollaborationActions } from "@/components/industry/collaborations/collaboration-actions";
import { CollaborationStatusBadge } from "@/components/industry/collaborations/collaboration-status-badge";
import { RECIPIENT_TYPE_LABELS, type IndustryCollaboration } from "@/types/industry-collaboration";

export function CollaborationCard({
  collaboration,
  pending,
  onSend,
  onActivate,
  onComplete,
  onCancel,
}: {
  collaboration: IndustryCollaboration;
  pending: boolean;
  onSend: () => void;
  onActivate: () => void;
  onComplete: () => void;
  onCancel: () => void;
}) {
  const detailHref = `/industry/collaborations/${collaboration.id}`;
  const canEdit = collaboration.status === "DRAFT";
  const RecipientIcon = collaboration.recipient_type === "FACULTY" ? GraduationCap : Building2;

  return (
    <Card>
      <CardContent className="space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 space-y-1">
            <Link href={detailHref} className="block truncate font-medium hover:underline">
              {collaboration.title}
            </Link>
            <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <RecipientIcon className="size-3.5" aria-hidden="true" />
              <span className="truncate">
                To{" "}
                {collaboration.recipient_name ??
                  RECIPIENT_TYPE_LABELS[collaboration.recipient_type]}
              </span>
              <Badge variant="ghost" className="shrink-0 text-[10px]">
                {collaboration.recipient_type}
              </Badge>
            </p>
          </div>
          <CollaborationStatusBadge status={collaboration.status} />
        </div>

        <div className="flex flex-wrap items-center gap-2 pt-1">
          <Button size="sm" variant="outline" render={<Link href={detailHref} />}>
            View
          </Button>
          {canEdit ? (
            <Button size="sm" variant="outline" render={<Link href={`${detailHref}?edit=1`} />}>
              Edit
            </Button>
          ) : null}
          <CollaborationActions
            status={collaboration.status}
            pending={pending}
            onSend={onSend}
            onActivate={onActivate}
            onComplete={onComplete}
            onCancel={onCancel}
          />
        </div>
      </CardContent>
    </Card>
  );
}
