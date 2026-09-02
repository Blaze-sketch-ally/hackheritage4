"use client";

import { useEffect, useState } from "react";
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

type CapabilityState =
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
