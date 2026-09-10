import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  updatePassword: vi.fn(),
  createClient: vi.fn(),
}));

vi.mock("@/lib/auth", async () => {
  const actual = await vi.importActual<typeof import("@/lib/auth")>("@/lib/auth");
  return { ...actual, updatePassword: mocks.updatePassword };
});
vi.mock("@/lib/supabase/client", () => ({ createClient: mocks.createClient }));

import { ChangePasswordForm } from "@/components/industry/settings/change-password-form";

describe("ChangePasswordForm", () => {
  afterEach(() => vi.resetAllMocks());

  it("renders the new password and confirm password fields", () => {
    render(<ChangePasswordForm />);
    expect(screen.getByLabelText("New Password")).toBeInTheDocument();
    expect(screen.getByLabelText("Confirm New Password")).toBeInTheDocument();
  });

  it("requires both fields before submitting", async () => {
    render(<ChangePasswordForm />);
    await userEvent.click(screen.getByRole("button", { name: "Change Password" }));

    expect(screen.getByText("Password does not meet the requirements below.")).toBeInTheDocument();
    expect(mocks.updatePassword).not.toHaveBeenCalled();
  });

  it("rejects a password that fails the existing strength rules", async () => {
    render(<ChangePasswordForm />);
    await userEvent.type(screen.getByLabelText("New Password"), "weak");
    await userEvent.type(screen.getByLabelText("Confirm New Password"), "weak");
    await userEvent.click(screen.getByRole("button", { name: "Change Password" }));

    expect(screen.getByText("Password does not meet the requirements below.")).toBeInTheDocument();
    expect(mocks.updatePassword).not.toHaveBeenCalled();
  });

  it("rejects a mismatched confirmation", async () => {
    render(<ChangePasswordForm />);
    await userEvent.type(screen.getByLabelText("New Password"), "StrongPass1");
    await userEvent.type(screen.getByLabelText("Confirm New Password"), "StrongPass2");
    await userEvent.click(screen.getByRole("button", { name: "Change Password" }));

    expect(screen.getByText("Passwords do not match.")).toBeInTheDocument();
    expect(mocks.updatePassword).not.toHaveBeenCalled();
  });

  it("calls updatePassword with a valid, matching, strong password", async () => {
    mocks.createClient.mockReturnValue("fake-supabase-client");
    mocks.updatePassword.mockResolvedValueOnce({ error: null });

    render(<ChangePasswordForm />);
    await userEvent.type(screen.getByLabelText("New Password"), "StrongPass1");
    await userEvent.type(screen.getByLabelText("Confirm New Password"), "StrongPass1");
    await userEvent.click(screen.getByRole("button", { name: "Change Password" }));

    await waitFor(() =>
      expect(mocks.updatePassword).toHaveBeenCalledWith("fake-supabase-client", "StrongPass1"),
    );
  });

  it("shows success feedback and clears the password fields after a successful update", async () => {
    mocks.createClient.mockReturnValue("fake-supabase-client");
    mocks.updatePassword.mockResolvedValueOnce({ error: null });

    render(<ChangePasswordForm />);
    const newPassword = screen.getByLabelText("New Password");
    const confirmPassword = screen.getByLabelText("Confirm New Password");
    await userEvent.type(newPassword, "StrongPass1");
    await userEvent.type(confirmPassword, "StrongPass1");
    await userEvent.click(screen.getByRole("button", { name: "Change Password" }));

    expect(await screen.findByText("Password updated successfully.")).toBeInTheDocument();
    expect(newPassword).toHaveValue("");
    expect(confirmPassword).toHaveValue("");
  });

  it("prevents duplicate submission while the request is pending", async () => {
    mocks.createClient.mockReturnValue("fake-supabase-client");
    let resolveUpdate: (value: { error: null }) => void = () => {};
    mocks.updatePassword.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveUpdate = resolve;
      }),
    );

    render(<ChangePasswordForm />);
    await userEvent.type(screen.getByLabelText("New Password"), "StrongPass1");
    await userEvent.type(screen.getByLabelText("Confirm New Password"), "StrongPass1");
    const button = screen.getByRole("button", { name: "Change Password" });
    await userEvent.click(button);

    expect(screen.getByRole("button", { name: "Updating..." })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Updating..." }));
    expect(mocks.updatePassword).toHaveBeenCalledTimes(1);

    resolveUpdate({ error: null });
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Change Password" })).toBeInTheDocument(),
    );
  });

  it("shows an error when updatePassword fails", async () => {
    mocks.createClient.mockReturnValue("fake-supabase-client");
    mocks.updatePassword.mockResolvedValueOnce({ error: { message: "same password" } });

    render(<ChangePasswordForm />);
    await userEvent.type(screen.getByLabelText("New Password"), "StrongPass1");
    await userEvent.type(screen.getByLabelText("Confirm New Password"), "StrongPass1");
    await userEvent.click(screen.getByRole("button", { name: "Change Password" }));

    expect(
      await screen.findByText("New password must be different from your current password."),
    ).toBeInTheDocument();
  });

  it("never renders the raw password value as text anywhere on the page", async () => {
    render(<ChangePasswordForm />);
    await userEvent.type(screen.getByLabelText("New Password"), "StrongPass1");
    await userEvent.type(screen.getByLabelText("Confirm New Password"), "StrongPass1");

    // The field is masked (type="password") until the user explicitly
    // toggles visibility -- by default the raw value is never exposed as
    // plain rendered text.
    expect(screen.getByLabelText("New Password")).toHaveAttribute("type", "password");
    expect(screen.getByLabelText("Confirm New Password")).toHaveAttribute("type", "password");
  });
});
