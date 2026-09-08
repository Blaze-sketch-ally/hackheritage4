import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { getInstitutionProfile, updateInstitutionProfile } = vi.hoisted(() => ({
  getInstitutionProfile: vi.fn(),
  updateInstitutionProfile: vi.fn(),
}));

vi.mock("@/lib/institution/profile", () => ({ getInstitutionProfile, updateInstitutionProfile }));

import { InstitutionProfileView } from "@/components/institution/profile/institution-profile-view";
import { ApiError } from "@/lib/api";
import type { InstitutionProfile } from "@/types/institution";

function profile(overrides: Partial<InstitutionProfile> = {}): InstitutionProfile {
  return {
    id: "institution-1",
    institution_name: "State College of Engineering",
    institution_type: "Government",
    location: "Pune, India",
    website_url: "https://sce.example",
    contact_phone: "+91 20 1234 5678",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-02-01T00:00:00Z",
    ...overrides,
  };
}

const emptyProfile = (): InstitutionProfile => ({
  id: "institution-1",
  institution_name: null,
  institution_type: null,
  location: null,
  website_url: null,
  contact_phone: null,
  created_at: null,
  updated_at: null,
});

describe("InstitutionProfileView", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows the heading and a loading state while fetching", () => {
    getInstitutionProfile.mockReturnValue(new Promise(() => {}));

    render(<InstitutionProfileView />);

    expect(screen.getByRole("heading", { name: "Institution Profile" })).toBeInTheDocument();
    expect(screen.getByText(/Loading your institution profile/i)).toBeInTheDocument();
  });

  it("shows an API error state with a retry action", async () => {
    getInstitutionProfile.mockRejectedValue(new ApiError(500, "Backend unavailable right now."));

    render(<InstitutionProfileView />);

    expect(await screen.findByText("Backend unavailable right now.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("shows a session-expired message for a 401 with no retry", async () => {
    getInstitutionProfile.mockRejectedValue(new ApiError(401, "You must be signed in to do this."));

    render(<InstitutionProfileView />);

    expect(await screen.findByText(/session has expired/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /try again/i })).not.toBeInTheDocument();
  });

  it("renders the saved institution profile in read view", async () => {
    getInstitutionProfile.mockResolvedValue(profile());

    render(<InstitutionProfileView />);

    expect(
      await screen.findByRole("heading", { name: "State College of Engineering" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Government")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Edit Profile" })).toBeInTheDocument();
  });

  it("renders a clean empty state when no profile row exists yet", async () => {
    getInstitutionProfile.mockResolvedValue(emptyProfile());

    render(<InstitutionProfileView />);

    expect(await screen.findByRole("heading", { name: "Your institution" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add institution details" })).toBeInTheDocument();
    expect(screen.getAllByText("Not added yet").length).toBeGreaterThan(0);
  });

  it("opens the edit form pre-filled with the current values", async () => {
    getInstitutionProfile.mockResolvedValue(profile());

    render(<InstitutionProfileView />);
    await userEvent.click(await screen.findByRole("button", { name: "Edit Profile" }));

    expect(screen.getByLabelText("Institution Name")).toHaveValue("State College of Engineering");
    expect(screen.getByLabelText("Location")).toHaveValue("Pune, India");
  });

  it("blocks save and shows a field error for an invalid phone number", async () => {
    getInstitutionProfile.mockResolvedValue(profile());

    render(<InstitutionProfileView />);
    await userEvent.click(await screen.findByRole("button", { name: "Edit Profile" }));

    const phone = screen.getByLabelText("Contact Phone");
    await userEvent.clear(phone);
    await userEvent.type(phone, "not a phone!!");
    await userEvent.click(screen.getByRole("button", { name: "Save Changes" }));

    expect(
      await screen.findByText(/digits, spaces, \+, -, or parentheses/i),
    ).toBeInTheDocument();
    expect(updateInstitutionProfile).not.toHaveBeenCalled();
  });

  it("saves normalised fields and returns to the read view on success", async () => {
    getInstitutionProfile.mockResolvedValue(profile());
    updateInstitutionProfile.mockResolvedValue(
      profile({ institution_name: "State College of Engineering (Autonomous)" }),
    );

    render(<InstitutionProfileView />);
    await userEvent.click(await screen.findByRole("button", { name: "Edit Profile" }));

    const name = screen.getByLabelText("Institution Name");
    await userEvent.clear(name);
    await userEvent.type(name, "  State College of Engineering (Autonomous)  ");
    await userEvent.click(screen.getByRole("button", { name: "Save Changes" }));

    await waitFor(() => expect(updateInstitutionProfile).toHaveBeenCalledTimes(1));
    const sent = updateInstitutionProfile.mock.calls[0][0];
    expect(sent.institution_name).toBe("State College of Engineering (Autonomous)");
    expect(sent.institution_type).toBe("Government");

    expect(await screen.findByText("Institution profile saved.")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "State College of Engineering (Autonomous)" }),
    ).toBeInTheDocument();
  });
});
