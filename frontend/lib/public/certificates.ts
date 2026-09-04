import { ApiError } from "@/lib/api";
import type { PublicCertificate } from "@/types/internship-completion";

/**
 * The ONE genuinely public FastAPI call in this app
 * (backend/app/api/certificates.py, GET /api/v1/certificates/verify/{number}).
 * No authentication -- deliberately does NOT go through lib/api.ts's
 * apiFetch(), which requires a signed-in session and would 401 a visitor
 * before the request ever reaches the backend. This is the one exception;
 * every other API call in the app goes through lib/api.ts.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function readErrorMessage(response: Response): Promise<string> {
  try {
    const data: unknown = await response.json();
    if (data && typeof data === "object" && "detail" in data && typeof data.detail === "string") {
      return data.detail;
    }
  } catch {
    // Response body wasn't JSON -- fall through to the generic message.
  }
  return `Something went wrong (${response.status}). Please try again.`;
}

/** Look up a certificate by its public number. Throws ApiError(422) for a
 * malformed number, ApiError(404) for one that doesn't resolve. */
export async function verifyCertificate(certificateNumber: string): Promise<PublicCertificate> {
  let response: Response;
  try {
    response = await fetch(
      `${API_BASE_URL}/api/v1/certificates/verify/${encodeURIComponent(certificateNumber)}`,
    );
  } catch {
    throw new ApiError(0, "Could not reach the server. Check your connection and try again.");
  }
  if (!response.ok) {
    throw new ApiError(response.status, await readErrorMessage(response));
  }
  return (await response.json()) as PublicCertificate;
}
