"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { ApiError, api } from "@/lib/api";

export const ASSESSMENT_CAPABILITIES = [
  "assessment_author",
  "assessment_reviewer",
  "assessment_evaluator",
  "assessment_moderator",
  "assessment_lead",
] as const;

export type AssessmentCapability = (typeof ASSESSMENT_CAPABILITIES)[number];

export interface MyFacultyCapabilities {
  role: "FACULTY";
  capabilities: AssessmentCapability[];
}

export function getMyFacultyCapabilities(): Promise<MyFacultyCapabilities> {
  return api.get("/api/v1/faculty/me/assessment-capabilities");
}

export function hasAssessmentCapability(
  capabilities: readonly AssessmentCapability[],
  capability: AssessmentCapability,
): boolean {
  return capabilities.includes(capability);
}

export type CapabilityState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; capabilities: AssessmentCapability[] };

/** Centralised UI-only capability lookup. The backend remains authoritative. */
export function useFacultyCapabilities(): CapabilityState {
  const [state, setState] = useState<CapabilityState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    void getMyFacultyCapabilities()
      .then((response) => {
        if (!cancelled) setState({ status: "ready", capabilities: response.capabilities });
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({
            status: "error",
            error: error instanceof ApiError ? error : new ApiError(0, "Could not load Faculty capabilities."),
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}

/** Phase 1 (Faculty Dashboard Architecture): the two capability
 * combinations the Faculty navigation/dashboards actually branch on.
 * Named here, once, rather than re-deriving `hasAssessmentCapability`
 * calls at every call site -- still just a read of the same single
 * `capabilities` array, never a second permission system. Reviewer-only
 * (no author) still gets Question Studio: the review/approve-reject UI
 * that already exists there is real, working reviewer functionality,
 * not something invented for this phase. Moderator/lead grant neither --
 * both remain fully dormant, exactly as the backend/RLS already treat
 * them. */
export function hasQuestionStudioAccess(capabilities: readonly AssessmentCapability[]): boolean {
  return (
    hasAssessmentCapability(capabilities, "assessment_author") ||
    hasAssessmentCapability(capabilities, "assessment_reviewer")
  );
}

export function hasEvaluationWorkspaceAccess(capabilities: readonly AssessmentCapability[]): boolean {
  return hasAssessmentCapability(capabilities, "assessment_evaluator");
}

/** Single shared fetch of the caller's capabilities for the whole Faculty
 * section of the app (sidebar + whichever dashboard is on screen), so
 * navigating between Faculty Connect / Question Studio / Evaluation
 * Workspace never re-requests GET /faculty/me/assessment-capabilities --
 * see FacultyShell, which is the one place this Provider is mounted. */
const FacultyCapabilitiesContext = createContext<CapabilityState | null>(null);

export function FacultyCapabilitiesProvider({ children }: { children: React.ReactNode }) {
  const state = useFacultyCapabilities();
  return <FacultyCapabilitiesContext.Provider value={state}>{children}</FacultyCapabilitiesContext.Provider>;
}

export function useFacultyCapabilitiesContext(): CapabilityState {
  const state = useContext(FacultyCapabilitiesContext);
  if (state === null) {
    throw new Error("useFacultyCapabilitiesContext must be used within a FacultyCapabilitiesProvider");
  }
  return state;
}
