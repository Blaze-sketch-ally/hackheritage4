import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ getInternshipProgram: vi.fn() }));
vi.mock("@/lib/industry/internship-program", () => ({
  getInternshipProgram: mocks.getInternshipProgram,
}));

import { InternshipProgramLink } from "@/components/industry/internship-program/internship-program-link";
import { ApiError } from "@/lib/api";
import type { InternshipProgramBundle } from "@/types/internship-program";

function bundle(program: InternshipProgramBundle["program"]): InternshipProgramBundle {
  return {
    internship: { id: "int-1", title: "Intern", status: "PUBLISHED" },
    program,
    modules: [],
    skills: [],
    available_skills: [],
  };
}

describe("InternshipProgramLink", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows 'Set Up Program' when no program exists", async () => {
    mocks.getInternshipProgram.mockResolvedValueOnce(bundle(null));
    render(<InternshipProgramLink internshipId="int-1" />);
    const cta = await screen.findByRole("button", { name: "Set Up Program" });
    expect(cta).toHaveAttribute("href", "/industry/internships/int-1/program");
  });

  it("shows 'Manage Program' and the status when a program exists", async () => {
    mocks.getInternshipProgram.mockResolvedValueOnce(
      bundle({
        id: "p", internship_id: "int-1", title: "P", summary: null, estimated_weeks: null,
        status: "PUBLISHED", published_at: null, created_at: null, updated_at: null,
      }),
    );
    render(<InternshipProgramLink internshipId="int-1" />);
    expect(await screen.findByRole("button", { name: "Manage Program" })).toBeInTheDocument();
    expect(screen.getByText("Published")).toBeInTheDocument();
  });

  it("degrades to a plain link when the lookup fails", async () => {
    mocks.getInternshipProgram.mockRejectedValueOnce(new ApiError(500, "down"));
    render(<InternshipProgramLink internshipId="int-1" />);
    expect(await screen.findByRole("button", { name: "Set Up Program" })).toBeInTheDocument();
  });
});
