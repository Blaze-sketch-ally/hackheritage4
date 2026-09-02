import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { getFacultyProfile, updateFacultyProfile } = vi.hoisted(() => ({
  getFacultyProfile: vi.fn(),
  updateFacultyProfile: vi.fn(),
}));

vi.mock("@/lib/faculty/profile", () => ({
  getFacultyProfile,
  updateFacultyProfile,
}));

import { FacultyProfileView } from "@/components/faculty/faculty-profile-view";
import { ApiError } from "@/lib/api";

function profile(overrides = {}) {
  return {
    id: "faculty-1",
    designation: null,
    department: null,
    institution_name: null,
    phone: null,
    bio: null,
    expertise_areas: [],
    years_of_experience: null,
    created_at: null,
    updated_at: null,
    completeness: 0,
    ...overrides,
  };
}

describe("FacultyProfileView", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows an empty-state form (0% complete) for a brand-new profile", async () => {
    getFacultyProfile.mockResolvedValue(profile());
    render(<FacultyProfileView />);

    expect(await screen.findByLabelText(/designation/i)).toHaveValue("");
    expect(screen.getByText("0%")).toBeInTheDocument();
  });

  it("populates the form from an existing profile", async () => {
    getFacultyProfile.mockResolvedValue(
      profile({
        designation: "Professor",
        department: "CSE",
        expertise_areas: ["Databases", "Distributed Systems"],
        completeness: 0.57,
      }),
    );
    render(<FacultyProfileView />);

    expect(await screen.findByLabelText(/designation/i)).toHaveValue("Professor");
    expect(screen.getByLabelText(/department/i)).toHaveValue("CSE");
    expect(screen.getByLabelText(/areas of expertise/i)).toHaveValue("Databases, Distributed Systems");
    expect(screen.getByText("57%")).toBeInTheDocument();
  });

  it("saves the form and reflects the updated completeness", async () => {
    getFacultyProfile.mockResolvedValue(profile());
    updateFacultyProfile.mockResolvedValue(profile({ designation: "Professor", completeness: 0.14 }));

    render(<FacultyProfileView />);
    await screen.findByLabelText(/designation/i);

    await userEvent.type(screen.getByLabelText(/designation/i), "Professor");
    await userEvent.click(screen.getByRole("button", { name: /save profile/i }));

    await waitFor(() =>
      expect(updateFacultyProfile).toHaveBeenCalledWith(
        expect.objectContaining({ designation: "Professor" }),
      ),
    );
    expect(await screen.findByText(/profile saved/i)).toBeInTheDocument();
    expect(screen.getByText("14%")).toBeInTheDocument();
  });

  it("splits the expertise areas field into a trimmed array on save", async () => {
    getFacultyProfile.mockResolvedValue(profile());
    updateFacultyProfile.mockResolvedValue(profile());

    render(<FacultyProfileView />);
    await screen.findByLabelText(/areas of expertise/i);

    await userEvent.type(screen.getByLabelText(/areas of expertise/i), "Databases,  AI ,Security");
    await userEvent.click(screen.getByRole("button", { name: /save profile/i }));

    await waitFor(() =>
      expect(updateFacultyProfile).toHaveBeenCalledWith(
        expect.objectContaining({ expertise_areas: ["Databases", "AI", "Security"] }),
      ),
    );
  });

  it("shows a retryable error state on load failure", async () => {
    getFacultyProfile.mockRejectedValueOnce(new ApiError(500, "Could not load your profile."));
    getFacultyProfile.mockResolvedValueOnce(profile());

    render(<FacultyProfileView />);
    expect(await screen.findByText("Could not load your profile.")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(await screen.findByLabelText(/designation/i)).toBeInTheDocument();
  });

  it("shows a save error without discarding the form", async () => {
    getFacultyProfile.mockResolvedValue(profile());
    updateFacultyProfile.mockRejectedValue(new ApiError(422, "Enter a valid phone number."));

    render(<FacultyProfileView />);
    await screen.findByLabelText(/designation/i);
    await userEvent.click(screen.getByRole("button", { name: /save profile/i }));

    expect(await screen.findByText("Enter a valid phone number.")).toBeInTheDocument();
  });
});
