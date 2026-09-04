import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({ getApplicationMatch: vi.fn() }));
vi.mock("@/lib/industry/applications", () => ({ getApplicationMatch: mocks.getApplicationMatch }));

import { CandidateCard } from "@/components/industry/candidate-card";
import type { Application } from "@/types/application";

function application(overrides: Partial<Application> = {}): Application {
  return {
    id: "app-1",
    student_id: "11112222-3333-4444-5555-666677778888",
    industry_id: "industry-1",
    opportunity_type: "JOB",
    internship_id: null,
    job_id: "job-1",
    status: "SHORTLISTED",
    cover_note: "Strong portfolio.",
    match_score: null,
    applied_at: "2026-09-01T00:00:00Z",
    created_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-01T00:00:00Z",
    opportunity: { id: "job-1", title: "Backend Engineer", status: "PUBLISHED" },
    ...overrides,
  };
}

describe("CandidateCard", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows a compact match badge when a stored match_score is present", () => {
    render(
      <CandidateCard application={application({ match_score: 87 })} pending={false} onPick={vi.fn()} />,
    );
    expect(screen.getByText("Match 87%")).toBeInTheDocument();
  });

  it("shows 'Not scored yet' when match_score is null", () => {
    render(<CandidateCard application={application()} pending={false} onPick={vi.fn()} />);
    expect(screen.getByText("Not scored yet")).toBeInTheDocument();
  });

  it("never calls the match endpoint on render", () => {
    render(
      <CandidateCard application={application({ match_score: null })} pending={false} onPick={vi.fn()} />,
    );
    expect(mocks.getApplicationMatch).not.toHaveBeenCalled();
  });

  it("shows the applicant reference, opportunity, status and a link to detail", () => {
    render(<CandidateCard application={application()} pending={false} onPick={vi.fn()} />);

    expect(screen.getByText(/Applicant 11112222/)).toBeInTheDocument();
    expect(screen.getByText(/Job · Backend Engineer/)).toBeInTheDocument();
    expect(screen.getByText("Shortlisted")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "View" })).toHaveAttribute(
      "href",
      "/industry/applicants/app-1",
    );
  });

  it("offers the valid next-status actions and fires onPick", async () => {
    const onPick = vi.fn();
    render(<CandidateCard application={application()} pending={false} onPick={onPick} />);

    await userEvent.click(screen.getByRole("button", { name: "Schedule interview" }));
    expect(onPick).toHaveBeenCalledWith("INTERVIEW_SCHEDULED");
  });

  it("hides status actions when showActions is false", () => {
    render(
      <CandidateCard application={application()} pending={false} onPick={vi.fn()} showActions={false} />,
    );
    expect(screen.queryByRole("button", { name: "Schedule interview" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "View" })).toBeInTheDocument();
  });

  it("does not render fabricated student data — only the applicant reference", () => {
    render(<CandidateCard application={application()} pending={false} onPick={vi.fn()} />);
    expect(screen.queryByText(/@/)).not.toBeInTheDocument();
  });

  it("shows the applicant's real name when the backend resolved one", () => {
    render(
      <CandidateCard
        application={application({ student_name: "Arunangshu Pal" })}
        pending={false}
        onPick={vi.fn()}
      />,
    );
    expect(screen.getByText("Arunangshu Pal")).toBeInTheDocument();
    expect(screen.getByText("AP")).toBeInTheDocument();
    expect(screen.queryByText(/Applicant 11112222/)).not.toBeInTheDocument();
  });
});
