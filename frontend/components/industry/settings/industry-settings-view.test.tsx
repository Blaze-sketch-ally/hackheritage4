import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  fetchProfile: vi.fn(),
  createClient: vi.fn(),
  getUser: vi.fn(),
}));

vi.mock("@/lib/profile", () => ({ fetchProfile: mocks.fetchProfile }));
vi.mock("@/lib/supabase/client", () => ({
  createClient: mocks.createClient,
}));

import { IndustrySettingsView } from "@/components/industry/settings/industry-settings-view";
import type { Profile } from "@/types/user";

function profile(overrides: Partial<Profile> = {}): Profile {
  return {
    id: "industry-1",
    email: "founder@acme.test",
    username: "acmefounder",
    role: "INDUSTRY",
    full_name: "Jordan Lee",
    avatar_url: null,
    created_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-01T00:00:00Z",
    ...overrides,
  };
}

function mockSupabase(user: { id: string } | null) {
  mocks.createClient.mockReturnValue({
    auth: { getUser: mocks.getUser.mockResolvedValue({ data: { user } }) },
  });
}

describe("IndustrySettingsView", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows a loading state", () => {
    mockSupabase({ id: "industry-1" });
    mocks.fetchProfile.mockReturnValue(new Promise(() => {}));
    render(<IndustrySettingsView />);
    expect(screen.getByText(/Loading your account/i)).toBeInTheDocument();
  });

  it("shows an error state when the session is missing", async () => {
    mockSupabase(null);
    render(<IndustrySettingsView />);
    expect(
      await screen.findByText("Your session has expired. Please sign in again."),
    ).toBeInTheDocument();
  });

  it("shows an error state with retry when the profile fails to load", async () => {
    mockSupabase({ id: "industry-1" });
    mocks.fetchProfile.mockRejectedValueOnce(new Error("network error"));
    render(<IndustrySettingsView />);
    expect(await screen.findByText(/Could not load your account/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("renders the Account and Security sections once the profile loads", async () => {
    mockSupabase({ id: "industry-1" });
    mocks.fetchProfile.mockResolvedValueOnce(profile());

    render(<IndustrySettingsView />);

    expect(await screen.findByText("Account")).toBeInTheDocument();
    expect(screen.getByText("Security")).toBeInTheDocument();
    expect(screen.getByLabelText("Full Name")).toHaveValue("Jordan Lee");
    expect(screen.getByLabelText("New Password")).toBeInTheDocument();
  });

  it("renders a Manage Company Profile link pointing to /industry/profile", async () => {
    mockSupabase({ id: "industry-1" });
    mocks.fetchProfile.mockResolvedValueOnce(profile());

    render(<IndustrySettingsView />);
    await screen.findByText("Account");

    expect(screen.getByRole("button", { name: /manage company profile/i })).toHaveAttribute(
      "href",
      "/industry/profile",
    );
  });

  it("shows the Manage Company Profile link even while the account section is loading", () => {
    mockSupabase({ id: "industry-1" });
    mocks.fetchProfile.mockReturnValue(new Promise(() => {}));
    render(<IndustrySettingsView />);
    expect(screen.getByRole("button", { name: /manage company profile/i })).toBeInTheDocument();
  });
});
