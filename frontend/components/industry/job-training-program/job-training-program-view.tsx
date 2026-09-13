"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, ArrowLeft, Loader2, Plus, RefreshCw, Rocket } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ConfirmationDialog } from "@/components/common/confirmation-dialog";
import { FormError } from "@/components/auth/form-error";
import {
  JobModuleEditor,
  type JobModuleHandlers,
} from "@/components/industry/job-training-program/module-editor";
import { JobProgramInfoForm } from "@/components/industry/job-training-program/program-info-form";
import { JobProgramSkillsEditor } from "@/components/industry/job-training-program/program-skills-editor";
import { JobProgramStatusBadge } from "@/components/industry/job-training-program/program-status-badge";
import { ApiError } from "@/lib/api";
import {
  createJobProgramItem,
  createJobProgramAssignment,
  createJobProgramModule,
  createJobTrainingProgram,
  getJobTrainingProgram,
  publishJobTrainingProgram,
  reorderJobProgramItems,
  reorderJobProgramAssignments,
  reorderJobProgramModules,
  setJobTrainingProgramSkills,
  updateJobProgramItem,
  updateJobProgramAssignment,
  updateJobProgramModule,
  updateJobTrainingProgram,
} from "@/lib/industry/job-training";
import type { JobProgramBundle } from "@/types/job-training-program";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; bundle: JobProgramBundle };

export function JobTrainingProgramView({ jobId }: { jobId: string }) {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [busy, setBusy] = useState(false);
  const [mutError, setMutError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [addingModule, setAddingModule] = useState(false);
  const [moduleTitle, setModuleTitle] = useState("");
  const [confirmPublish, setConfirmPublish] = useState(false);

  const reload = useCallback(() => {
    setState({ status: "loading" });
    setReloadKey((k) => k + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const bundle = await getJobTrainingProgram(jobId);
        if (!cancelled) setState({ status: "ready", bundle });
      } catch (err) {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load this program."),
        });
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [jobId, reloadKey]);

  /** Run a mutation, replace the bundle with the server's fresh copy, and
   * surface any failure once at the top of the page. Resolves to `true` on
   * success so a child can react -- it never throws, so fire-and-forget
   * callers are safe. */
  const mutate = useCallback(
    async (run: () => Promise<JobProgramBundle>): Promise<boolean> => {
      setBusy(true);
      setMutError(null);
      try {
        const bundle = await run();
        setState({ status: "ready", bundle });
        return true;
      } catch (err) {
        setMutError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
        return false;
      } finally {
        setBusy(false);
      }
    },
    [],
  );

  async function handleCreate() {
    setCreating(true);
    await mutate(() => createJobTrainingProgram(jobId, { title: newTitle.trim() }));
    setCreating(false);
  }

  if (state.status === "loading") {
    return (
      <div className="space-y-4" aria-busy="true" aria-label="Loading program">
        <Card className="animate-pulse">
          <CardContent className="space-y-2 py-6">
            <div className="h-5 w-1/2 rounded bg-muted" />
            <div className="h-3 w-full rounded bg-muted" />
          </CardContent>
        </Card>
      </div>
    );
  }

  if (state.status === "error") {
    const notFound = state.error.status === 404;
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
          <AlertCircle className="size-8 text-destructive" />
          <div>
            <p className="font-medium">
              {notFound ? "This job doesn't exist or isn't yours." : "Could not load this program."}
            </p>
            <p className="text-sm text-muted-foreground">{state.error.message}</p>
          </div>
          {notFound ? (
            <Button variant="outline" size="sm" render={<Link href="/industry/jobs" />}>
              Back to jobs
            </Button>
          ) : (
            <Button variant="outline" size="sm" onClick={reload}>
              <RefreshCw className="size-3.5" /> Try again
            </Button>
          )}
        </CardContent>
      </Card>
    );
  }

  const { job, program, modules, skills, available_skills } = state.bundle;

  const moduleHandlers: JobModuleHandlers = {
    onUpdateModule: (moduleId, data) =>
      mutate(() => updateJobProgramModule(jobId, moduleId, data)),
    onMoveModule: (moduleId, dir) => {
      const ids = modules.map((m) => m.id);
      const i = ids.indexOf(moduleId);
      const j = i + dir;
      if (j < 0 || j >= ids.length) return Promise.resolve(false);
      [ids[i], ids[j]] = [ids[j], ids[i]];
      return mutate(() => reorderJobProgramModules(jobId, ids));
    },
    onAddItem: (moduleId, data) => mutate(() => createJobProgramItem(jobId, moduleId, data)),
    onUpdateItem: (moduleId, itemId, data) =>
      mutate(() => updateJobProgramItem(jobId, moduleId, itemId, data)),
    onMoveItem: (moduleId, itemId, dir) => {
      const mod = modules.find((m) => m.id === moduleId);
      if (!mod) return Promise.resolve(false);
      const ids = mod.items.map((it) => it.id);
      const i = ids.indexOf(itemId);
      const j = i + dir;
      if (j < 0 || j >= ids.length) return Promise.resolve(false);
      [ids[i], ids[j]] = [ids[j], ids[i]];
      return mutate(() => reorderJobProgramItems(jobId, moduleId, ids));
    },
    onAddAssignment: (moduleId, data) =>
      mutate(() => createJobProgramAssignment(jobId, moduleId, data)),
    onUpdateAssignment: (moduleId, assignmentId, data) =>
      mutate(() => updateJobProgramAssignment(jobId, moduleId, assignmentId, data)),
    onMoveAssignment: (moduleId, assignmentId, dir) => {
      const mod = modules.find((m) => m.id === moduleId);
      if (!mod) return Promise.resolve(false);
      const ids = mod.assignments.map((a) => a.id);
      const i = ids.indexOf(assignmentId);
      const j = i + dir;
      if (j < 0 || j >= ids.length) return Promise.resolve(false);
      [ids[i], ids[j]] = [ids[j], ids[i]];
      return mutate(() => reorderJobProgramAssignments(jobId, moduleId, ids));
    },
  };

  return (
    <div className="flex flex-col gap-6">
      <Link
        href={`/industry/jobs/${jobId}`}
        className="flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-3.5" /> Back to job
      </Link>

      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-xl font-semibold">Job Training Program</h1>
        {program && <JobProgramStatusBadge status={program.status} />}
      </div>
      <p className="-mt-4 text-sm text-muted-foreground">{job.title}</p>

      <FormError message={mutError} />

      {!program ? (
        <Card>
          <CardContent className="flex flex-col gap-3 py-6">
            <p className="font-medium">No program yet</p>
            <p className="text-sm text-muted-foreground">
              Create the training program a selected candidate will work through once you assign
              it to them.
            </p>
            <div className="flex flex-wrap items-end gap-2">
              <div className="w-full max-w-sm space-y-1.5">
                <label htmlFor="new-job-program-title" className="text-sm font-medium">
                  Program name
                </label>
                <Input
                  id="new-job-program-title"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  maxLength={200}
                  placeholder="e.g. Site Reliability Engineering Onboarding"
                  disabled={creating}
                />
              </div>
              <Button onClick={handleCreate} disabled={creating || !newTitle.trim()}>
                {creating && <Loader2 className="size-3.5 animate-spin" />}
                Create Program
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2">
            {program.status === "DRAFT" ? (
              <Button onClick={() => setConfirmPublish(true)} disabled={busy}>
                <Rocket className="size-3.5" /> Publish Program
              </Button>
            ) : (
              <p className="text-sm text-emerald-600">
                Published — you can now assign it to a selected candidate.
              </p>
            )}
          </div>

          <JobProgramInfoForm
            program={program}
            busy={busy}
            onSave={(data) => mutate(() => updateJobTrainingProgram(jobId, data))}
          />

          <section className="flex flex-col gap-3">
            <h2 className="text-sm font-semibold tracking-wider text-muted-foreground uppercase">
              Modules
            </h2>
            {modules.length === 0 && !addingModule ? (
              <p className="text-sm text-muted-foreground">No modules yet.</p>
            ) : null}
            {modules.map((m, i) => (
              <JobModuleEditor
                key={m.id}
                module={m}
                index={i}
                count={modules.length}
                busy={busy}
                programSkills={skills}
                handlers={moduleHandlers}
              />
            ))}
            {addingModule ? (
              <Card>
                <CardContent className="flex flex-col gap-2 py-4">
                  <label htmlFor="new-job-module-title" className="text-sm font-medium">
                    Module title
                  </label>
                  <Input
                    id="new-job-module-title"
                    value={moduleTitle}
                    onChange={(e) => setModuleTitle(e.target.value)}
                    maxLength={200}
                    disabled={busy}
                  />
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      disabled={busy || !moduleTitle.trim()}
                      onClick={async () => {
                        const ok = await mutate(() =>
                          createJobProgramModule(jobId, { title: moduleTitle.trim() }),
                        );
                        if (ok) {
                          setModuleTitle("");
                          setAddingModule(false);
                        }
                      }}
                    >
                      Add module
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setAddingModule(false)}>
                      Cancel
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ) : (
              <Button
                variant="outline"
                size="sm"
                className="w-fit"
                disabled={busy}
                onClick={() => setAddingModule(true)}
              >
                <Plus className="size-3.5" /> Add Module
              </Button>
            )}
          </section>

          <JobProgramSkillsEditor
            skills={skills}
            availableSkills={available_skills}
            busy={busy}
            onSave={(next) => mutate(() => setJobTrainingProgramSkills(jobId, next))}
          />
        </>
      )}

      <ConfirmationDialog
        open={confirmPublish}
        onOpenChange={setConfirmPublish}
        title="Publish this program?"
        description="A selected candidate you assign it to will see the program. You can keep editing it afterwards."
        confirmLabel="Publish"
        onConfirm={() => {
          setConfirmPublish(false);
          void mutate(() => publishJobTrainingProgram(jobId));
        }}
      />
    </div>
  );
}
