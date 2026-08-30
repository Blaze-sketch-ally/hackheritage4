import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const getSession = vi.fn();

// lib/api.ts imports the browser Supabase client factory -- mock it so
// tests control the session without touching real Supabase/network.
vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: { getSession },
  }),
}));

import { apiFetch, ApiError, getAccessToken } from "@/lib/api";

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("getAccessToken", () => {
  afterEach(() => vi.clearAllMocks());

  it("returns the access token from the current Supabase session", async () => {
    getSession.mockResolvedValue({ data: { session: { access_token: "real-token-abc" } } });
    await expect(getAccessToken()).resolves.toBe("real-token-abc");
  });

  it("returns null when there is no session", async () => {
    getSession.mockResolvedValue({ data: { session: null } });
    await expect(getAccessToken()).resolves.toBeNull();
  });
});

describe("apiFetch", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("attaches Authorization: Bearer <token> for an authenticated session", async () => {
    getSession.mockResolvedValue({ data: { session: { access_token: "session-token-xyz" } } });
    fetchMock.mockResolvedValue(jsonResponse(200, { ok: true }));

    await apiFetch("/api/v1/assessments");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, init] = fetchMock.mock.calls[0];
    const headers = new Headers(init.headers);
    expect(headers.get("Authorization")).toBe("Bearer session-token-xyz");
  });

  it("never calls fetch and throws a 401 ApiError when there is no session", async () => {
    getSession.mockResolvedValue({ data: { session: null } });

    await expect(apiFetch("/api/v1/assessments")).rejects.toMatchObject({
      name: "ApiError",
      status: 401,
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("never logs the access token anywhere", async () => {
    const logSpy = vi.spyOn(console, "log").mockImplementation(() => {});
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});

    getSession.mockResolvedValue({ data: { session: { access_token: "must-not-appear-in-logs" } } });
    fetchMock.mockResolvedValue(jsonResponse(200, { ok: true }));

    await apiFetch("/api/v1/assessments");

    for (const spy of [logSpy, errorSpy, warnSpy]) {
      for (const call of spy.mock.calls) {
        expect(call.join(" ")).not.toContain("must-not-appear-in-logs");
      }
    }
    logSpy.mockRestore();
    errorSpy.mockRestore();
    warnSpy.mockRestore();
  });

  it("turns a non-2xx FastAPI response into an ApiError using the response's detail message", async () => {
    getSession.mockResolvedValue({ data: { session: { access_token: "t" } } });
    fetchMock.mockResolvedValue(jsonResponse(409, { detail: "This attempt has already been submitted." }));

    await expect(apiFetch("/api/v1/attempts/abc/submit", { method: "POST" })).rejects.toMatchObject({
      name: "ApiError",
      status: 409,
      message: "This attempt has already been submitted.",
    });
  });

  it("falls back to a generic message when the error response has no JSON detail", async () => {
    getSession.mockResolvedValue({ data: { session: { access_token: "t" } } });
    fetchMock.mockImplementation(
      async () => new Response("<html>gateway error</html>", { status: 502 }),
    );

    const rejection = (await apiFetch("/api/v1/assessments").catch((e) => e)) as ApiError;
    expect(rejection.name).toBe("ApiError");
    expect(rejection.status).toBe(502);
    expect(rejection.message).not.toContain("<html>");
  });

  it("parses a successful JSON response", async () => {
    getSession.mockResolvedValue({ data: { session: { access_token: "t" } } });
    fetchMock.mockResolvedValue(jsonResponse(200, { assessments: [{ id: "1" }] }));

    await expect(apiFetch("/api/v1/assessments")).resolves.toEqual({ assessments: [{ id: "1" }] });
  });

  it("sends a JSON body with Content-Type application/json when a body is provided", async () => {
    getSession.mockResolvedValue({ data: { session: { access_token: "t" } } });
    fetchMock.mockResolvedValue(jsonResponse(200, { id: "answer-1" }));

    await apiFetch("/api/v1/attempts/abc/answers", {
      method: "POST",
      body: { question_id: "q1", selected_option_ids: ["opt1"] },
    });

    const [, init] = fetchMock.mock.calls[0];
    const headers = new Headers(init.headers);
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(init.body).toBe(JSON.stringify({ question_id: "q1", selected_option_ids: ["opt1"] }));
  });

  it("omits Content-Type when no body is provided (e.g. submit/score have no body)", async () => {
    getSession.mockResolvedValue({ data: { session: { access_token: "t" } } });
    fetchMock.mockResolvedValue(jsonResponse(200, { status: "COMPLETED" }));

    await apiFetch("/api/v1/attempts/abc/submit", { method: "POST" });

    const [, init] = fetchMock.mock.calls[0];
    const headers = new Headers(init.headers);
    expect(headers.get("Content-Type")).toBeNull();
    expect(init.body).toBeUndefined();
  });

  it("turns a network failure into a status-0 ApiError, not an uncaught exception", async () => {
    getSession.mockResolvedValue({ data: { session: { access_token: "t" } } });
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(apiFetch("/api/v1/assessments")).rejects.toMatchObject({
      name: "ApiError",
      status: 0,
    });
  });
});
