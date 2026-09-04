import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getWorkspaceCompletion: vi.fn(),
  verifyWorkspaceCompletion: vi.fn(),
}));

vi.mock("@/lib/industry/internship-workspaces", () => mocks);

import { WorkspaceCompletionPanel } from "@/components/industry/internship-program/workspace-completion-panel";
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

describe("WorkspaceCompletionPanel", () => {
  afterEach(() => vi.resetAllMocks());

  it("hides the verify action while requirements are outstanding", async () => {
    mocks.getWorkspaceCompletion.mockResolvedValueOnce(summary());
    render(<WorkspaceCompletionPanel workspaceId="ws-1" studentName="Asha Rao" />);

    expect(await screen.findByText("Requirements: 1 / 2")).toBeInTheDocument();
    expect(screen.getByText("Deployment Assignment")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /verify internship completion/i }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Verification not yet available")).toBeInTheDocument();
  });

  it("shows the verify button once requirements are met", async () => {
    mocks.getWorkspaceCompletion.mockResolvedValueOnce(
      summary({ completed_count: 2, requirements_met: true, outstanding: [] }),
    );
    render(<WorkspaceCompletionPanel workspaceId="ws-1" studentName="Asha Rao" />);

    expect(
      await screen.findByRole("button", { name: /verify internship completion/i }),
    ).toBeInTheDocument();
  });

  it("verifies completion via confirm and shows the issued certificate", async () => {
    const user = userEvent.setup();
    mocks.getWorkspaceCompletion.mockResolvedValueOnce(
      summary({ completed_count: 2, requirements_met: true, outstanding: [] }),
    );
    mocks.verifyWorkspaceCompletion.mockResolvedValueOnce(
      summary({
        completed_count: 2,
        requirements_met: true,
        outstanding: [],
        industry_verified: true,
        result: "PASS",
        certificate: {
          certificate_number: "AIC-INT-2026-AAAAAAAAAAAAA",
          student_name: "Asha Rao",
          company_name: "TechNova",
          internship_title: "ML Intern",
          issued_at: "2026-09-10T00:00:00Z",
          skills: [],
          revoked: false,
        },
      }),
    );

    render(<WorkspaceCompletionPanel workspaceId="ws-1" studentName="Asha Rao" />);
    await user.click(await screen.findByRole("button", { name: /verify internship completion/i }));
    await user.click(screen.getByRole("button", { name: /^verify$/i }));

    await waitFor(() => expect(mocks.verifyWorkspaceCompletion).toHaveBeenCalledWith("ws-1"));
    expect(await screen.findByText("Internship completed")).toBeInTheDocument();
    expect(screen.getByText("AIC-INT-2026-AAAAAAAAAAAAA")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /verify internship completion/i }),
    ).not.toBeInTheDocument();
  });

  it("hides the verify action entirely once already verified (no duplicate action)", async () => {
    mocks.getWorkspaceCompletion.mockResolvedValueOnce(
      summary({
        completed_count: 2,
        requirements_met: true,
        outstanding: [],
        industry_verified: true,
        result: "PASS",
        certificate: {
          certificate_number: "AIC-INT-2026-AAAAAAAAAAAAA",
          student_name: "Asha Rao",
          company_name: "TechNova",
          internship_title: "ML Intern",
          issued_at: "2026-09-10T00:00:00Z",
          skills: [],
          revoked: false,
        },
      }),
    );
    render(<WorkspaceCompletionPanel workspaceId="ws-1" studentName="Asha Rao" />);

    expect(await screen.findByText("Internship completed")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /verify internship completion/i }),
    ).not.toBeInTheDocument();
  });

  it("shows a server error and keeps the button when verification fails", async () => {
    const user = userEvent.setup();
    mocks.getWorkspaceCompletion.mockResolvedValueOnce(
      summary({ completed_count: 2, requirements_met: true, outstanding: [] }),
    );
    mocks.verifyWorkspaceCompletion.mockRejectedValueOnce(
      new ApiError(409, "Cannot complete this internship yet. Outstanding: Deploy."),
    );

    render(<WorkspaceCompletionPanel workspaceId="ws-1" studentName="Asha Rao" />);
    await user.click(await screen.findByRole("button", { name: /verify internship completion/i }));
    await user.click(screen.getByRole("button", { name: /^verify$/i }));

    expect(
      await screen.findByText("Cannot complete this internship yet. Outstanding: Deploy."),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /verify internship completion/i }),
    ).toBeInTheDocument();
  });

  it("shows a loading state then an error on failure to load", async () => {
    mocks.getWorkspaceCompletion.mockRejectedValueOnce(new ApiError(500, "server sad"));
    render(<WorkspaceCompletionPanel workspaceId="ws-1" studentName="Asha Rao" />);
    expect(await screen.findByText("server sad")).toBeInTheDocument();
  });
});
