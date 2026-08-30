import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { AssessmentProgress } from "@/components/assessment/assessment-progress";

describe("AssessmentProgress", () => {
  it("shows the current question number, total, and answered count", () => {
    render(<AssessmentProgress current={2} total={5} answeredCount={1} />);
    expect(screen.getByText("Question 2 of 5")).toBeInTheDocument();
    expect(screen.getByText("1 of 5 answered")).toBeInTheDocument();
  });

  it("shows 0 of N answered before anything is saved", () => {
    render(<AssessmentProgress current={1} total={5} answeredCount={0} />);
    expect(screen.getByText("0 of 5 answered")).toBeInTheDocument();
  });
});
