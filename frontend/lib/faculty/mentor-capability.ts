"use client";

import { useEffect, useState } from "react";
import { ApiError, api } from "@/lib/api";

/**
 * Mirrors lib/faculty/capabilities.ts's own shape, but for the separate
 * faculty_mentor trust axis (Phase F4.2) -- a single boolean, not a list
 * of capability names.
 */
export interface MyMentorCapability {
  role: "FACULTY";
  can_mentor: boolean;
}

export function getMyMentorCapability(): Promise<MyMentorCapability> {
  return api.get("/api/v1/faculty/me/mentor-capability");
}

type MentorCapabilityState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; canMentor: boolean };

/** Centralised UI-only capability lookup. The backend remains authoritative. */
export function useMentorCapability(): MentorCapabilityState {
  const [state, setState] = useState<MentorCapabilityState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    void getMyMentorCapability()
      .then((response) => {
        if (!cancelled) setState({ status: "ready", canMentor: response.can_mentor });
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({
            status: "error",
            error: error instanceof ApiError ? error : new ApiError(0, "Could not load the mentor capability."),
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}
