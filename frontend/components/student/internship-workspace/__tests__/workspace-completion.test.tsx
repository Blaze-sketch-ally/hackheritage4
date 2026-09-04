import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  getMyWorkspaceCompletion: vi.fn(),
}));

vi.mock("@/lib/student/internship-workspace", () => mocks);

import { WorkspaceCompletion } from "@/components/student/internship-workspace/workspace-completion";
import { ApiError } from "@/lib/api";
import type { CompletionSummary } from "@/types/internship-completion";

function summary(over: Partial<CompletionSummary> = {}): CompletionSummary {
  return {
    workspace_id: "ws-1",
    required_count: 2,
    completed_count: 1,
    requirements_met: false,
    outstanding: [{ kind: "ASSIGNMENT", id: "a2", title: "Deployment Assignment" }],
    industry_verified: false,
    result: null,
    verified_at: null,
    certificate: null,
    ...over,
  };
}

describe("WorkspaceCompletion", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows incomplete requirements and tells the student what's left", async () => {
    mocks.getMyWorkspaceCompletion.mockResolvedValueOnce(summary());
    render(<WorkspaceCompletion workspaceId="ws-1" />);

    expect(await screen.findByText("Requirements: 1 / 2 complete")).toBeInTheDocument();
    expect(screen.getByText("Deployment Assignment")).toBeInTheDocument();
    expect(screen.getByText("Complete the remaining requirements.")).toBeInTheDocument();
    expect(screen.getByText("Pending")).toBeInTheDocument();
  });

  it("shows requirements met, awaiting industry verification", async () => {
    mocks.getMyWorkspaceCompletion.mockResolvedValueOnce(
      summary({ completed_count: 2, requirements_met: true, outstanding: [] }),
    );
    render(<WorkspaceCompletion workspaceId="ws-1" />);

    expect(await screen.findByText("Requirements: 2 / 2 complete")).toBeInTheDocument();
    expect(screen.getByText("Met")).toBeInTheDocument();
    expect(
      screen.getByText("Internship completion pending industry verification."),
    ).toBeInTheDocument();
  });

  it("shows the PASS state with the certificate", async () => {
    mocks.getMyWorkspaceCompletion.mockResolvedValueOnce(
      summary({
        completed_count: 2,
        requirements_met: true,
        outstanding: [],
        industry_verified: true,
        result: "PASS",
        verified_at: "2026-09-10T00:00:00Z",
        certificate: {
          certificate_number: "AIC-INT-2026-AAAAAAAAAAAAA",
          student_name: "Asha Rao",
          company_name: "TechNova",
          internship_title: "ML Engineering Intern",
          issued_at: "2026-09-10T00:00:00Z",
          skills: [{ skill_id: "sk-py", skill_name: "Python" }],
          revoked: false,
        },
      }),
    );
    render(<WorkspaceCompletion workspaceId="ws-1" />);

    expect(await screen.findByText("Internship completed")).toBeInTheDocument();
    expect(screen.getByText("AIC-INT-2026-AAAAAAAAAAAAA")).toBeInTheDocument();
    expect(screen.getByText("TechNova")).toBeInTheDocument();
    expect(screen.getByText("Python")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /verify this certificate/i })).toHaveAttribute(
      "href",
      "/certificates/verify/AIC-INT-2026-AAAAAAAAAAAAA",
    );
    // no "pending verification" text once verified
    expect(
      screen.queryByText("Internship completion pending industry verification."),
    ).not.toBeInTheDocument();
  });

  it("shows a loading state then an error on failure", async () => {
    mocks.getMyWorkspaceCompletion.mockRejectedValueOnce(new ApiError(500, "server sad"));
    render(<WorkspaceCompletion workspaceId="ws-1" />);
    expect(screen.getByLabelText("Loading completion status")).toBeInTheDocument();
    expect(await screen.findByText("server sad")).toBeInTheDocument();
  });
});
