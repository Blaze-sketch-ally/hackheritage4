import { createClient } from "@/lib/supabase/client";

/**
 * The frontend -> FastAPI authentication bridge.
 *
 * Every request carries the current Supabase session's access token as
 * `Authorization: Bearer <token>` -- FastAPI (app.core.dependencies) is
 * the one place that validates it and enforces authorization; RLS is
 * still the real access-control boundary once that token reaches
 * Supabase from build_user_client(). This module never bypasses that:
 * it holds only the browser anon key (via lib/supabase/client.ts's
 * createBrowserClient), never SUPABASE_SERVICE_ROLE_KEY, which does not
 * and must not exist in any NEXT_PUBLIC_* variable or client-side file.
 *
 * Browser-only: getAccessToken() reads the session from the browser
 * Supabase client, so this module must only be imported from Client
 * Components (files with "use client"), never Server Components/Route
 * Handlers -- use lib/supabase/server.ts's client for those instead.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Thrown for every non-2xx FastAPI response and for "no session at all".
 * `status` lets callers branch on specific backend semantics (e.g. 409 on
 * an already-in-progress attempt) without parsing message text. `message`
 * is always safe to show a user -- FastAPI's own error responses in this
 * project are already generic, user-facing strings (see every route in
 * backend/app/api/), never raw database/stack-trace detail. */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/** The current Supabase session's access token, or null if signed out.
 * Never logged, never returned in an error message -- only ever placed
 * directly into the Authorization header. */
export async function getAccessToken(): Promise<string | null> {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  return session?.access_token ?? null;
}

type RequestOptions = Omit<RequestInit, "body"> & {
  body?: unknown;
};

async function readErrorMessage(response: Response): Promise<string> {
  try {
    const data: unknown = await response.json();
    if (data && typeof data === "object" && "detail" in data && typeof data.detail === "string") {
      return data.detail;
    }
  } catch {
    // Response body wasn't JSON (or was empty) -- fall through to the
    // generic message below rather than surfacing raw response text.
  }
  return `Something went wrong (${response.status}). Please try again.`;
}

/** The one function every FastAPI call in this app goes through. Attaches
 * the bearer token, sets Content-Type only when a body is actually sent,
 * parses JSON responses, and turns any non-2xx response into a typed,
 * user-safe ApiError -- callers never see a raw fetch Response or a raw
 * backend error string. */
export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, headers, ...rest } = options;

  const token = await getAccessToken();
  if (!token) {
    throw new ApiError(401, "You must be signed in to do this.");
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...rest,
      headers: {
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
        Authorization: `Bearer ${token}`,
        ...headers,
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    // Network failure (backend unreachable, offline, CORS, etc.) -- never
    // a status code, so there's nothing to branch on beyond "failed".
    throw new ApiError(0, "Could not reach the server. Check your connection and try again.");
  }

  if (!response.ok) {
    throw new ApiError(response.status, await readErrorMessage(response));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export const api = {
  get: <T>(path: string, options?: RequestOptions) => apiFetch<T>(path, { ...options, method: "GET" }),
  post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    apiFetch<T>(path, { ...options, method: "POST", body }),
  put: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    apiFetch<T>(path, { ...options, method: "PUT", body }),
  patch: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    apiFetch<T>(path, { ...options, method: "PATCH", body }),
  delete: <T>(path: string, options?: RequestOptions) =>
    apiFetch<T>(path, { ...options, method: "DELETE" }),
};
