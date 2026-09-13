import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  refresh: vi.fn(),
  createClient: vi.fn(),
  listNotifications: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push, refresh: mocks.refresh }),
}));
vi.mock("@/lib/supabase/client", () => ({ createClient: mocks.createClient }));
vi.mock("@/lib/industry/notifications", () => ({
  listNotifications: mocks.listNotifications,
}));

import { IndustryHeader } from "@/components/industry/industry-header";
import type { Profile } from "@/types/user";

function profile(overrides: Partial<Profile> = {}): Profile {
  return {
    id: "industry-user-1",
    email: "recruiter@technova.example",
    username: "technova",
    role: "INDUSTRY",
    full_name: "Tara Recruiter",
    avatar_url: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("IndustryHeader", () => {
  beforeEach(() => {
    mocks.listNotifications.mockResolvedValue({ notifications: [], unread_count: 0 });
  });

  it("renders the profile dropdown trigger", () => {
    render(<IndustryHeader profile={profile()} onMenuClick={vi.fn()} />);
    expect(screen.getByText("Tara Recruiter")).toBeInTheDocument();
  });

  it("renders a working notification bell linking to /industry/notifications", () => {
    render(<IndustryHeader profile={profile()} onMenuClick={vi.fn()} />);
    expect(screen.getByRole("button", { name: /notification/i })).toHaveAttribute(
      "href",
      "/industry/notifications",
    );
  });

  it("does not render a disabled global search input", () => {
    const { container } = render(
      <IndustryHeader profile={profile()} onMenuClick={vi.fn()} />,
    );
    expect(screen.queryByRole("searchbox")).not.toBeInTheDocument();
    expect(container.querySelector("input")).toBeNull();
  });
});
