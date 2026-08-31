import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { getIndustryProfile, updateIndustryProfile } = vi.hoisted(() => ({
  getIndustryProfile: vi.fn(),
  updateIndustryProfile: vi.fn(),
}));

vi.mock("@/lib/industry/profile", () => ({ getIndustryProfile, updateIndustryProfile }));

import { IndustryProfileView } from "@/components/industry/profile/industry-profile-view";
import { ApiError } from "@/lib/api";
import type { IndustryProfile } from "@/types/industry";

function profile(overrides: Partial<IndustryProfile> = {}): IndustryProfile {
  return {
    id: "industry-1",
    company_name: "Acme Robotics",
    industry_sector: "Manufacturing",
    company_size: "51-200",
    website_url: "https://acme.example",
    company_description: "We build robots.",
    headquarters_location: "Pune, India",
    founded_year: 2015,
    contact_phone: "+91 20 1234 5678",
    linkedin_url: "https://linkedin.com/company/acme",
    logo_url: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-02-01T00:00:00Z",
    ...overrides,
  };
}

const emptyProfile = (): IndustryProfile => ({
  id: "industry-1",
  company_name: null,
  industry_sector: null,
  company_size: null,
  website_url: null,
  company_description: null,
  headquarters_location: null,
  founded_year: null,
  contact_phone: null,
  linkedin_url: null,
  logo_url: null,
  created_at: null,
  updated_at: null,
});

describe("IndustryProfileView", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows the heading and a loading state while fetching", () => {
    getIndustryProfile.mockReturnValue(new Promise(() => {}));

    render(<IndustryProfileView />);

    expect(screen.getByRole("heading", { name: "Company Profile" })).toBeInTheDocument();
    expect(screen.getByText(/Loading your company profile/i)).toBeInTheDocument();
  });

  it("shows an API error state with a retry action", async () => {
    getIndustryProfile.mockRejectedValue(new ApiError(500, "Backend unavailable right now."));

    render(<IndustryProfileView />);

    expect(await screen.findByText("Backend unavailable right now.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("shows a session-expired message for a 401 with no retry", async () => {
    getIndustryProfile.mockRejectedValue(new ApiError(401, "You must be signed in to do this."));

    render(<IndustryProfileView />);

    expect(await screen.findByText(/session has expired/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /try again/i })).not.toBeInTheDocument();
  });

  it("renders the saved company profile in read view", async () => {
    getIndustryProfile.mockResolvedValue(profile());

    render(<IndustryProfileView />);

    expect(await screen.findByRole("heading", { name: "Acme Robotics" })).toBeInTheDocument();
    expect(screen.getByText("Manufacturing")).toBeInTheDocument();
    expect(screen.getByText("51–200 employees")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Edit Profile" })).toBeInTheDocument();
  });

  it("renders a clean empty state when no profile row exists yet", async () => {
    getIndustryProfile.mockResolvedValue(emptyProfile());

    render(<IndustryProfileView />);

    expect(await screen.findByRole("heading", { name: "Your company" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add company details" })).toBeInTheDocument();
    expect(screen.getAllByText("Not added yet").length).toBeGreaterThan(0);
  });

  it("opens the edit form pre-filled with the current values", async () => {
    getIndustryProfile.mockResolvedValue(profile());

    render(<IndustryProfileView />);
    await userEvent.click(await screen.findByRole("button", { name: "Edit Profile" }));

    expect(screen.getByLabelText("Company Name")).toHaveValue("Acme Robotics");
    expect(screen.getByLabelText("Headquarters")).toHaveValue("Pune, India");
  });

  it("blocks save and shows a field error for an invalid phone number", async () => {
    getIndustryProfile.mockResolvedValue(profile());

    render(<IndustryProfileView />);
    await userEvent.click(await screen.findByRole("button", { name: "Edit Profile" }));

    const phone = screen.getByLabelText("Phone");
    await userEvent.clear(phone);
    await userEvent.type(phone, "not a phone!!");
    await userEvent.click(screen.getByRole("button", { name: "Save Changes" }));

    expect(
      await screen.findByText(/digits, spaces, \+, -, or parentheses/i),
    ).toBeInTheDocument();
    expect(updateIndustryProfile).not.toHaveBeenCalled();
  });

  it("saves normalised fields and returns to the read view on success", async () => {
    getIndustryProfile.mockResolvedValue(profile());
    updateIndustryProfile.mockResolvedValue(
      profile({ company_name: "Acme Robotics Ltd", updated_at: "2026-03-01T00:00:00Z" }),
    );

    render(<IndustryProfileView />);
    await userEvent.click(await screen.findByRole("button", { name: "Edit Profile" }));

    const name = screen.getByLabelText("Company Name");
    await userEvent.clear(name);
    await userEvent.type(name, "  Acme Robotics Ltd  ");
    await userEvent.click(screen.getByRole("button", { name: "Save Changes" }));

    await waitFor(() => expect(updateIndustryProfile).toHaveBeenCalledTimes(1));
    const sent = updateIndustryProfile.mock.calls[0][0];
    expect(sent.company_name).toBe("Acme Robotics Ltd");
    expect(sent.industry_sector).toBe("Manufacturing");

    expect(await screen.findByText("Company profile saved.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Acme Robotics Ltd" })).toBeInTheDocument();
  });
});
