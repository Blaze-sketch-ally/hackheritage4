import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getMyInternshipWorkspace: vi.fn(),
  acceptMyInternshipWorkspace: vi.fn(),
  declineMyInternshipWorkspace: vi.fn(),
  setMyInternshipWorkspaceSkills: vi.fn(),
  listMyWorkspaceAssignments: vi.fn(),
  getMyWorkspaceAssignment: vi.fn(),
  submitMyWorkspaceAssignment: vi.fn(),
  getMyWorkspaceCompletion: vi.fn(),
  getMyWorkspaceStipend: vi.fn(),
}));

vi.mock("@/lib/student/internship-workspace", () => mocks);

import { InternshipWorkspaceView } from "@/components/student/internship-workspace/internship-workspace-view";
import { ApiError } from "@/lib/api";
import type { InternshipWorkspaceDetail } from "@/types/internship-workspace";

function detail(overrides: Partial<InternshipWorkspaceDetail> = {}): InternshipWorkspaceDetail {
  return {
    id: "ws-1",
    application_id: "app-1",
    internship_id: "int-1",
    student_id: "student-1",
    industry_id: "industry-1",
    work_mode: "REMOTE",
    workspace_status: "PENDING_ACCEPTANCE",
    accepted_at: null,
    started_at: null,
    completed_at: null,
    declined_at: null,
    decline_reason: null,
    rescinded_at: null,
    rescind_reason: null,
    created_at: "2026-09-04T00:00:00Z",
    updated_at: "2026-09-04T00:00:00Z",
    internship: {
      id: "int-1",
      title: "ML Engineering Intern",
      description: "Build recommender systems.",
      work_mode: "REMOTE",
      status: "PUBLISHED",
    },
    program: {
      id: "prog-1",
      title: "TechNova ML Program",
      summary: "Six weeks of practical ML.",
      status: "PUBLISHED",
      modules: [
        {
          id: "m1",
          title: "Python Foundations",
          description: null,
          order_index: 0,
          items: [
            { id: "i1", title: "Intro video", item_type: "VIDEO", content_url: "https://x/v", content_text: null, order_index: 0 },
          ],
        },
      ],
      skills: [
        { skill_id: "s-req", skill_name: "Python", requirement: "REQUIRED" },
        { skill_id: "s-opt", skill_name: "SQL", requirement: "OPTIONAL" },
        { skill_id: "s-opt2", skill_name: "TensorFlow", requirement: "OPTIONAL" },
      ],
    },
    selected_skill_ids: [],
    ...overrides,
  };
}

describe("InternshipWorkspaceView", () => {
  afterEach(() => vi.resetAllMocks());

  // The assignments + completion + stipend sections (rendered for
  // ACCEPTED / IN_PROGRESS / COMPLETED workspaces) fetch on mount --
  // default them so the existing assertions are unaffected.
  beforeEach(() => {
    mocks.listMyWorkspaceAssignments.mockResolvedValue({ assignments: [] });
    mocks.getMyWorkspaceCompletion.mockResolvedValue({
      workspace_id: "ws-1",
      required_count: 0,
      completed_count: 0,
      requirements_met: true,
      outstanding: [],
      industry_verified: false,
      result: null,
      verified_at: null,
      certificate: null,
    });
    mocks.getMyWorkspaceStipend.mockResolvedValue({ workspace_id: "ws-1", stipend: null });
  });

  it("shows a loading state then the workspace", async () => {
    mocks.getMyInternshipWorkspace.mockResolvedValueOnce(detail());
    render(<InternshipWorkspaceView workspaceId="ws-1" />);
    expect(screen.getByLabelText("Loading internship workspace")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "ML Engineering Intern" })).toBeInTheDocument();
    expect(screen.getByText("TechNova ML Program")).toBeInTheDocument();
    expect(screen.getByText("Python Foundations")).toBeInTheDocument();
  });

  it("shows a not-found message for a 404", async () => {
    mocks.getMyInternshipWorkspace.mockRejectedValueOnce(new ApiError(404, "gone"));
    render(<InternshipWorkspaceView workspaceId="ws-x" />);
    expect(await screen.findByText("Internship workspace not found.")).toBeInTheDocument();
  });

  it("shows Accept / Decline for a PENDING_ACCEPTANCE workspace", async () => {
    mocks.getMyInternshipWorkspace.mockResolvedValueOnce(detail());
    render(<InternshipWorkspaceView workspaceId="ws-1" />);
    expect(await screen.findByRole("button", { name: /accept internship/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^decline$/i })).toBeInTheDocument();
    // no skill picker before acceptance
    expect(screen.queryByText("Training skills")).not.toBeInTheDocument();
  });

  it("accepts: confirm -> calls the API -> reloads as ACCEPTED", async () => {
    const user = userEvent.setup();
    mocks.getMyInternshipWorkspace
      .mockResolvedValueOnce(detail())
      .mockResolvedValueOnce(detail({ workspace_status: "ACCEPTED" }));
    mocks.acceptMyInternshipWorkspace.mockResolvedValueOnce(detail({ workspace_status: "ACCEPTED" }));

    render(<InternshipWorkspaceView workspaceId="ws-1" />);
    await user.click(await screen.findByRole("button", { name: /accept internship/i }));
    await user.click(screen.getByRole("button", { name: /yes, accept/i }));

    await waitFor(() => expect(mocks.acceptMyInternshipWorkspace).toHaveBeenCalledWith("ws-1"));
    expect(await screen.findByText(/internship active/i)).toBeInTheDocument();
    expect(screen.getByText("Training skills")).toBeInTheDocument();
  });

  it("declines: confirm -> calls the API -> reloads as DECLINED", async () => {
    const user = userEvent.setup();
    mocks.getMyInternshipWorkspace
      .mockResolvedValueOnce(detail())
      .mockResolvedValueOnce(detail({ workspace_status: "DECLINED" }));
    mocks.declineMyInternshipWorkspace.mockResolvedValueOnce(detail({ workspace_status: "DECLINED" }));

    render(<InternshipWorkspaceView workspaceId="ws-1" />);
    await user.click(await screen.findByRole("button", { name: /^decline$/i }));
    await user.click(screen.getByRole("button", { name: /yes, decline/i }));

    await waitFor(() => expect(mocks.declineMyInternshipWorkspace).toHaveBeenCalled());
    expect(await screen.findByText(/you declined this internship offer/i)).toBeInTheDocument();
  });

  it("shows an error when accept fails and stays on PENDING", async () => {
    const user = userEvent.setup();
    mocks.getMyInternshipWorkspace.mockResolvedValue(detail());
    mocks.acceptMyInternshipWorkspace.mockRejectedValueOnce(new ApiError(409, "no longer pending"));

    render(<InternshipWorkspaceView workspaceId="ws-1" />);
    await user.click(await screen.findByRole("button", { name: /accept internship/i }));
    await user.click(screen.getByRole("button", { name: /yes, accept/i }));

    expect(await screen.findByText("no longer pending")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /accept internship/i })).toBeInTheDocument();
  });

  it("renders the skill picker with required + optional skills for an ACCEPTED workspace", async () => {
    mocks.getMyInternshipWorkspace.mockResolvedValueOnce(
      detail({ workspace_status: "ACCEPTED", selected_skill_ids: ["s-opt"] }),
    );
    render(<InternshipWorkspaceView workspaceId="ws-1" />);

    expect(await screen.findByText("Training skills")).toBeInTheDocument();
    // required skill is shown (as a non-interactive chip -- there is no
    // button for it), optional skills are toggle buttons.
    expect(screen.getAllByText("Python").length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: "Python" })).not.toBeInTheDocument();
    const sql = screen.getByRole("button", { name: "SQL" });
    expect(sql).toHaveAttribute("aria-pressed", "true"); // pre-selected
    expect(screen.getByRole("button", { name: "TensorFlow" })).toHaveAttribute("aria-pressed", "false");
  });

  it("saves training skills and shows a saved state", async () => {
    const user = userEvent.setup();
    mocks.getMyInternshipWorkspace.mockResolvedValueOnce(detail({ workspace_status: "ACCEPTED" }));
    mocks.setMyInternshipWorkspaceSkills.mockResolvedValueOnce(
      detail({ workspace_status: "ACCEPTED", selected_skill_ids: ["s-opt"] }),
    );

    render(<InternshipWorkspaceView workspaceId="ws-1" />);
    await user.click(await screen.findByRole("button", { name: "SQL" }));
    await user.click(screen.getByRole("button", { name: /save training skills/i }));

    await waitFor(() =>
      expect(mocks.setMyInternshipWorkspaceSkills).toHaveBeenCalledWith("ws-1", ["s-opt"]),
    );
    expect(await screen.findByText("Saved")).toBeInTheDocument();
  });

  it("shows an error when saving training skills fails", async () => {
    const user = userEvent.setup();
    mocks.getMyInternshipWorkspace.mockResolvedValueOnce(detail({ workspace_status: "ACCEPTED" }));
    mocks.setMyInternshipWorkspaceSkills.mockRejectedValueOnce(new ApiError(422, "not an optional skill"));

    render(<InternshipWorkspaceView workspaceId="ws-1" />);
    await user.click(await screen.findByRole("button", { name: "TensorFlow" }));
    await user.click(screen.getByRole("button", { name: /save training skills/i }));

    expect(await screen.findByText("not an optional skill")).toBeInTheDocument();
  });

  it("shows the rescinded message and no accept/decline for a RESCINDED workspace", async () => {
    mocks.getMyInternshipWorkspace.mockResolvedValueOnce(detail({ workspace_status: "RESCINDED" }));
    render(<InternshipWorkspaceView workspaceId="ws-1" />);
    expect(
      await screen.findByText("This internship workspace is no longer active."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /accept internship/i })).not.toBeInTheDocument();
  });
});
