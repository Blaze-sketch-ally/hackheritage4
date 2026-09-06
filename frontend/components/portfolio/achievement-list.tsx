"use client";

import { useEffect, useState } from "react";
import { AlertCircle, Plus, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { AchievementCard } from "@/components/portfolio/achievement-card";
import { AchievementForm } from "@/components/portfolio/achievement-form";
import { ApiError } from "@/lib/api";
import { deleteAchievement, listMyAchievements } from "@/lib/student/portfolio";
import type { Achievement } from "@/types/portfolio";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; achievements: Achievement[] };

/** The student's own editable achievement list -- self-fetching, used by
 * /student/portfolio. Same shape as ProjectList/CertificationList. */
export function AchievementList() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [formMode, setFormMode] = useState<"none" | "create" | string>("none");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const { achievements } = await listMyAchievements();
        if (cancelled) return;
        setState({ status: "ready", achievements });
      } catch (err) {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load your achievements."),
        });
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  function refresh() {
    setFormMode("none");
    setReloadKey((k) => k + 1);
  }

  async function handleDelete(achievementId: string) {
    if (!window.confirm("Delete this achievement? This cannot be undone.")) return;
    try {
      await deleteAchievement(achievementId);
      setReloadKey((k) => k + 1);
    } catch (err) {
      window.alert(err instanceof ApiError ? err.message : "Could not delete this achievement.");
    }
  }

  if (state.status === "loading") {
    return (
      <div className="h-40 animate-pulse rounded-lg bg-muted" aria-busy="true" aria-label="Loading achievements" />
    );
  }

  if (state.status === "error") {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
          <AlertCircle className="size-8 text-destructive" />
          <div>
            <p className="font-medium">Could not load your achievements.</p>
            <p className="text-sm text-muted-foreground">{state.error.message}</p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setState({ status: "loading" });
              setReloadKey((k) => k + 1);
            }}
          >
            <RefreshCw className="size-3.5" /> Try again
          </Button>
        </CardContent>
      </Card>
    );
  }

  const { achievements } = state;
  const editingAchievement =
    formMode !== "none" && formMode !== "create" ? achievements.find((a) => a.id === formMode) : undefined;

  return (
    <div className="space-y-4">
      {formMode === "create" && <AchievementForm onSaved={refresh} onCancel={() => setFormMode("none")} />}
      {editingAchievement && (
        <AchievementForm achievement={editingAchievement} onSaved={refresh} onCancel={() => setFormMode("none")} />
      )}

      {formMode === "none" && (
        <>
          {achievements.length === 0 ? (
            <Card>
              <CardContent className="flex flex-col items-center gap-3 py-10 text-center text-muted-foreground">
                <p>Add awards, recognitions, or milestones worth highlighting.</p>
                <Button size="sm" onClick={() => setFormMode("create")}>
                  <Plus className="size-3.5" /> Add Achievement
                </Button>
              </CardContent>
            </Card>
          ) : (
            <>
              <div className="flex justify-end">
                <Button size="sm" onClick={() => setFormMode("create")}>
                  <Plus className="size-3.5" /> Add Achievement
                </Button>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                {achievements.map((achievement) => (
                  <AchievementCard
                    key={achievement.id}
                    achievement={achievement}
                    onEdit={() => setFormMode(achievement.id)}
                    onDelete={() => handleDelete(achievement.id)}
                  />
                ))}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
