import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  updateProfile: vi.fn(),
  upsertStudentProfile: vi.fn(),
  updatePassword: vi.fn(),
  signOut: vi.fn(),
  push: vi.fn(),
  refresh: vi.fn(),
}));

vi.mock("@/lib/profile", () => ({ updateProfile: mocks.updateProfile }));
vi.mock("@/lib/student/profile", async () => {
  const actual = await vi.importActual<typeof import("@/lib/student/profile")>("@/lib/student/profile");
  return { ...actual, upsertStudentProfile: mocks.upsertStudentProfile };
});
vi.mock("@/lib/auth", async () => {
  const actual = await vi.importActual<typeof import("@/lib/auth")>("@/lib/auth");
  return { ...actual, updatePassword: mocks.updatePassword };
});
vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({ auth: { signOut: mocks.signOut } }),
}));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push, refresh: mocks.refresh }),
}));

import { SettingsView } from "@/components/student/settings/settings-view";
import type { Profile } from "@/types/user";
import type { StudentProfile } from "@/lib/student/profile";

function profile(overrides: Partial<Profile> = {}): Profile {
  return {
    id: "student-1",
    email: "demo@student.test",
    username: "demostudent",
    role: "STUDENT",
    full_name: "Demo Student",
    avatar_url: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function studentProfile(overrides: Partial<StudentProfile> = {}): StudentProfile {
  return {
    id: "student-1",
    phone: "+91 99999 11111",
    date_of_birth: "2004-05-01",
    gender: "Male",
    location: "Pune",
    institution_name: "AIC College",
    department: "CSE",
    degree: "B.Tech",
    graduation_year: 2027,
    cgpa: 8.5,
    percentage: null,
    career_goals: "Backend engineer",
    preferred_roles: ["Backend Developer"],
    preferred_locations: ["Remote"],
    interests: ["Databases"],
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function renderView(p = profile(), sp = studentProfile(), email = "demo@student.test", verified = true) {
  return render(
    <SettingsView profile={p} studentProfile={sp} email={email} emailVerified={verified} />,
  );
}

describe("SettingsView", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows the real account info: email + verification, role, username", () => {
    renderView();
    expect(screen.getByText("demo@student.test")).toBeInTheDocument();
    expect(screen.getByText("Verified")).toBeInTheDocument();
    expect(screen.getByText("Student")).toBeInTheDocument();
    expect(screen.getByLabelText("Username")).toHaveValue("demostudent");
  });

  it("has NO control to change the account role", () => {
    renderView();
    // "Role" is shown as a static badge, never an editable field
    expect(screen.queryByRole("textbox", { name: "Role" })).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: "Role" })).not.toBeInTheDocument();
    expect(screen.queryByRole("radio", { name: /industry|faculty|institution|admin/i })).not.toBeInTheDocument();
    expect(screen.getByText(/role is fixed once set/i)).toBeInTheDocument();
  });

  it("updates the username via the canonical profile path, sending no ownership/role field", async () => {
    mocks.updateProfile.mockResolvedValue({ data: {}, error: null });
    renderView();
    const input = screen.getByLabelText("Username");
    await userEvent.clear(input);
    await userEvent.type(input, "new_handle");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(mocks.updateProfile).toHaveBeenCalledTimes(1));
    const [, id, fields] = mocks.updateProfile.mock.calls[0];
    expect(id).toBe("student-1");
    expect(fields).toEqual({ full_name: "Demo Student", username: "new_handle", avatar_url: null });
    expect(fields).not.toHaveProperty("role");
    expect(fields).not.toHaveProperty("id");
    expect(fields).not.toHaveProperty("created_at");
    expect(await screen.findByText("Username updated.")).toBeInTheDocument();
  });

  it("rejects an invalid username without calling the API", async () => {
    renderView();
    const input = screen.getByLabelText("Username");
    await userEvent.clear(input);
    await userEvent.type(input, "no");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText(/3.30 characters/i)).toBeInTheDocument();
    expect(mocks.updateProfile).not.toHaveBeenCalled();
  });

  it("saves career preferences through upsertStudentProfile with the full field set", async () => {
    mocks.upsertStudentProfile.mockResolvedValue({ data: {}, error: null });
    renderView();
    await userEvent.click(screen.getByRole("button", { name: "Save preferences" }));

    await waitFor(() => expect(mocks.upsertStudentProfile).toHaveBeenCalledTimes(1));
    const [, id, fields] = mocks.upsertStudentProfile.mock.calls[0];
    expect(id).toBe("student-1");
    // unrelated columns are preserved (not blanked)
    expect(fields.institution_name).toBe("AIC College");
    expect(fields.cgpa).toBe(8.5);
    expect(fields.career_goals).toBe("Backend engineer");
    expect(fields).not.toHaveProperty("id");
    expect(fields).not.toHaveProperty("role");
    expect(await screen.findByText("Career preferences saved.")).toBeInTheDocument();
  });

  it("changes the password via the established updatePassword flow", async () => {
    mocks.updatePassword.mockResolvedValue({ error: null });
    renderView();
    await userEvent.type(screen.getByLabelText("New password"), "Str0ngPass1");
    await userEvent.type(screen.getByLabelText("Confirm new password"), "Str0ngPass1");
    await userEvent.click(screen.getByRole("button", { name: "Update password" }));
    await waitFor(() => expect(mocks.updatePassword).toHaveBeenCalledWith(expect.anything(), "Str0ngPass1"));
    expect(await screen.findByText("Password updated.")).toBeInTheDocument();
  });

  it("blocks a weak password and never calls updatePassword", async () => {
    renderView();
    await userEvent.type(screen.getByLabelText("New password"), "weak");
    await userEvent.type(screen.getByLabelText("Confirm new password"), "weak");
    await userEvent.click(screen.getByRole("button", { name: "Update password" }));
    expect(mocks.updatePassword).not.toHaveBeenCalled();
  });

  it("shows honest 'Not available yet' for unbuilt settings", () => {
    renderView();
    expect(screen.getAllByText("Not available yet").length).toBeGreaterThanOrEqual(3);
    expect(screen.getByText("Email notification preferences")).toBeInTheDocument();
    expect(screen.getByText("Delete account")).toBeInTheDocument();
  });

  it("signs out through the existing supabase flow and redirects to /login", async () => {
    mocks.signOut.mockResolvedValue({});
    renderView();
    await userEvent.click(screen.getByRole("button", { name: /sign out/i }));
    await waitFor(() => expect(mocks.signOut).toHaveBeenCalled());
    expect(mocks.push).toHaveBeenCalledWith("/login");
  });

  it("links to the full profile page and forgot-password flow (no new auth architecture)", () => {
    const { container } = renderView();
    expect(container.querySelector('a[href="/student/profile"]')).not.toBeNull();
    expect(container.querySelector('a[href="/forgot-password"]')).not.toBeNull();
  });

  it("shows 'Not verified' when the email is unconfirmed", () => {
    renderView(profile(), studentProfile(), "demo@student.test", false);
    expect(screen.getByText("Not verified")).toBeInTheDocument();
  });
});
