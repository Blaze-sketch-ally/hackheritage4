import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { RecruitmentFunnel } from "@/components/industry/recruitment-funnel";
import type { ApplicationStatus } from "@/types/application";

function summary(counts: Partial<Record<ApplicationStatus, number>> = {}) {
  const base: Record<ApplicationStatus, number> = {
    APPLIED: 0,
    UNDER_REVIEW: 0,
    SHORTLISTED: 0,
    INTERVIEW_SCHEDULED: 0,
    SELECTED: 0,
    REJECTED: 0,
    WITHDRAWN: 0,
  };
  const merged = { ...base, ...counts };
  return { counts: merged, total: Object.values(merged).reduce((a, b) => a + b, 0) };
}

describe("RecruitmentFunnel", () => {
  it("renders a bar per pipeline stage with its count", () => {
    render(<RecruitmentFunnel summary={summary({ APPLIED: 4, UNDER_REVIEW: 2, SELECTED: 1 })} />);

    for (const label of ["Applied", "Under review", "Shortlisted", "Interview scheduled", "Selected"]) {
      expect(screen.getByRole("button", { name: new RegExp(label) })).toBeInTheDocument();
    }
    const applied = screen.getByRole("button", { name: /Applied/ });
    expect(within(applied).getByText("4")).toBeInTheDocument();
    expect(screen.getByText("7 applications")).toBeInTheDocument();
  });

  it("shows exit counts only when non-zero", () => {
    const { rerender } = render(<RecruitmentFunnel summary={summary({ APPLIED: 1 })} />);
    expect(screen.queryByText(/Rejected:/)).not.toBeInTheDocument();

    rerender(<RecruitmentFunnel summary={summary({ APPLIED: 1, REJECTED: 3 })} />);
    expect(screen.getByText(/Rejected:/)).toBeInTheDocument();
    expect(within(screen.getByText(/Rejected:/)).getByText("3")).toBeInTheDocument();
  });

  it("renders a zero-state with every stage at 0", () => {
    render(<RecruitmentFunnel summary={summary()} />);
    expect(screen.getByText("0 applications")).toBeInTheDocument();
    const selected = screen.getByRole("button", { name: /Selected/ });
    expect(within(selected).getByText("0")).toBeInTheDocument();
  });

  it("calls onStageClick when a stage is clicked and disables buttons otherwise", async () => {
    const onStageClick = vi.fn();
    const { rerender } = render(
      <RecruitmentFunnel summary={summary({ APPLIED: 2 })} onStageClick={onStageClick} />,
    );
    await userEvent.click(screen.getByRole("button", { name: /Shortlisted/ }));
    expect(onStageClick).toHaveBeenCalledWith("SHORTLISTED");

    rerender(<RecruitmentFunnel summary={summary({ APPLIED: 2 })} />);
    expect(screen.getByRole("button", { name: /Shortlisted/ })).toBeDisabled();
  });
});
