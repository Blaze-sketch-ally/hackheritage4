import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  updateProfile: vi.fn(),
  createClient: vi.fn(),
}));

vi.mock("@/lib/profile", () => ({ updateProfile: mocks.updateProfile }));
vi.mock("@/lib/supabase/client", () => ({ createClient: mocks.createClient }));

import { IndustryAccountSettingsForm } from "@/components/industry/settings/industry-account-settings-form";
import type { Profile } from "@/types/user";

function profile(overrides: Partial<Profile> = {}): Profile {
  return {
    id: "industry-1",
    email: "founder@acme.test",
    username: "acmefounder",
    role: "INDUSTRY",
    full_name: "Jordan Lee",
    avatar_url: "https://example.com/avatar.png",
    created_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-01T00:00:00Z",
    ...overrides,
  };
}

describe("IndustryAccountSettingsForm", () => {
  afterEach(() => vi.resetAllMocks());

  it("renders the existing profile values", () => {
    render(<IndustryAccountSettingsForm profile={profile()} onSaved={vi.fn()} />);
    expect(screen.getByLabelText("Full Name")).toHaveValue("Jordan Lee");
    expect(screen.getByLabelText("Username")).toHaveValue("acmefounder");
    expect(screen.getByLabelText("Avatar URL")).toHaveValue("https://example.com/avatar.png");
  });

  it("validates full name", async () => {
    const onSaved = vi.fn();
    render(<IndustryAccountSettingsForm profile={profile()} onSaved={onSaved} />);

    await userEvent.clear(screen.getByLabelText("Full Name"));
    await userEvent.click(screen.getByRole("button", { name: "Save Changes" }));

    expect(screen.getByText("Please enter your full name.")).toBeInTheDocument();
    expect(mocks.updateProfile).not.toHaveBeenCalled();
    expect(onSaved).not.toHaveBeenCalled();
  });

  it("validates username format", async () => {
    render(<IndustryAccountSettingsForm profile={profile()} onSaved={vi.fn()} />);

    const username = screen.getByLabelText("Username");
    await userEvent.clear(username);
    await userEvent.type(username, "a!");
    await userEvent.click(screen.getByRole("button", { name: "Save Changes" }));

    expect(
      screen.getByText("3-30 characters: letters, numbers, underscore, dot, or dash."),
    ).toBeInTheDocument();
    expect(mocks.updateProfile).not.toHaveBeenCalled();
  });

  it("validates avatar URL", async () => {
    render(<IndustryAccountSettingsForm profile={profile()} onSaved={vi.fn()} />);

    const avatar = screen.getByLabelText("Avatar URL");
    await userEvent.clear(avatar);
    await userEvent.type(avatar, "not-a-url");
    await userEvent.click(screen.getByRole("button", { name: "Save Changes" }));

    expect(screen.getByText("Please enter a valid URL.")).toBeInTheDocument();
    expect(mocks.updateProfile).not.toHaveBeenCalled();
  });

  it("does not submit an empty or invalid form", async () => {
    render(<IndustryAccountSettingsForm profile={profile()} onSaved={vi.fn()} />);

    await userEvent.clear(screen.getByLabelText("Full Name"));
    await userEvent.clear(screen.getByLabelText("Username"));
    await userEvent.click(screen.getByRole("button", { name: "Save Changes" }));

    expect(mocks.updateProfile).not.toHaveBeenCalled();
  });

  it("submits only full_name/username/avatar_url, normalised, and never email/role", async () => {
    mocks.createClient.mockReturnValue("fake-supabase-client");
    mocks.updateProfile.mockResolvedValueOnce({ data: profile(), error: null });
    const onSaved = vi.fn();

    render(<IndustryAccountSettingsForm profile={profile()} onSaved={onSaved} />);

    const fullName = screen.getByLabelText("Full Name");
    await userEvent.clear(fullName);
    await userEvent.type(fullName, "  Jordan A. Lee  ");
    const username = screen.getByLabelText("Username");
    await userEvent.clear(username);
    await userEvent.type(username, "  acme.founder  ");

    await userEvent.click(screen.getByRole("button", { name: "Save Changes" }));

    await waitFor(() => expect(mocks.updateProfile).toHaveBeenCalledTimes(1));
    const [client, userId, fields] = mocks.updateProfile.mock.calls[0];
    expect(client).toBe("fake-supabase-client");
    expect(userId).toBe("industry-1");
    expect(fields).toEqual({
      full_name: "Jordan A. Lee",
      username: "acme.founder",
      avatar_url: "https://example.com/avatar.png",
    });
    expect(fields).not.toHaveProperty("email");
    expect(fields).not.toHaveProperty("role");
    expect(onSaved).toHaveBeenCalledTimes(1);
  });

  it("clears avatar_url to null when the field is left blank", async () => {
    mocks.createClient.mockReturnValue("fake-supabase-client");
    mocks.updateProfile.mockResolvedValueOnce({ data: profile({ avatar_url: null }), error: null });

    render(<IndustryAccountSettingsForm profile={profile()} onSaved={vi.fn()} />);
    await userEvent.clear(screen.getByLabelText("Avatar URL"));
    await userEvent.click(screen.getByRole("button", { name: "Save Changes" }));

    await waitFor(() => expect(mocks.updateProfile).toHaveBeenCalledTimes(1));
    expect(mocks.updateProfile.mock.calls[0][2].avatar_url).toBeNull();
  });

  it("disables the submit button while saving to prevent duplicate submission", async () => {
    mocks.createClient.mockReturnValue("fake-supabase-client");
    let resolveUpdate: (value: { data: Profile; error: null }) => void = () => {};
    mocks.updateProfile.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveUpdate = resolve;
      }),
    );

    render(<IndustryAccountSettingsForm profile={profile()} onSaved={vi.fn()} />);
    const button = screen.getByRole("button", { name: "Save Changes" });
    await userEvent.click(button);

    expect(screen.getByRole("button", { name: "Saving..." })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Saving..." }));
    expect(mocks.updateProfile).toHaveBeenCalledTimes(1);

    resolveUpdate({ data: profile(), error: null });
    await waitFor(() => expect(screen.getByRole("button", { name: "Save Changes" })).toBeInTheDocument());
  });

  it("shows success feedback after a successful save", async () => {
    mocks.createClient.mockReturnValue("fake-supabase-client");
    mocks.updateProfile.mockResolvedValueOnce({ data: profile(), error: null });

    render(<IndustryAccountSettingsForm profile={profile()} onSaved={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Save Changes" }));

    expect(await screen.findByText("Account settings saved.")).toBeInTheDocument();
  });

  it("shows an error when updateProfile fails", async () => {
    mocks.createClient.mockReturnValue("fake-supabase-client");
    mocks.updateProfile.mockResolvedValueOnce({
      data: null,
      error: { message: "duplicate key value violates unique constraint" },
    });

    render(<IndustryAccountSettingsForm profile={profile()} onSaved={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Save Changes" }));

    expect(await screen.findByText("Something went wrong. Please try again.")).toBeInTheDocument();
  });
});
