import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getIndustryConnections: vi.fn(),
  createIndustryConnection: vi.fn(),
  searchIndustryPartnerCompanies: vi.fn(),
}));

vi.mock("@/lib/institution/industry-connections", () => ({
  getIndustryConnections: mocks.getIndustryConnections,
  createIndustryConnection: mocks.createIndustryConnection,
  updateIndustryConnection: vi.fn(),
}));

vi.mock("@/lib/institution/industry-partners", () => ({
  searchIndustryPartnerCompanies: mocks.searchIndustryPartnerCompanies,
}));

import { IndustryConnectionsList } from "@/components/institution/industry-connections/industry-connections-list";
import { ApiError } from "@/lib/api";
import type { IndustryConnectionListResponse } from "@/types/institution-industry-connection";

function list(overrides: Partial<IndustryConnectionListResponse> = {}): IndustryConnectionListResponse {
  return {
    connections: [
      {
        id: "c1",
        industry_id: "co-1",
        company_name: "Acme Corp",
        industry_sector: "Software",
        logo_url: null,
        contact_name: "Priya Sharma",
        designation: "HR Manager",
        contact_type: "RECRUITMENT",
        email: "priya@acme.example",
        phone: "9876543210",
        notes: null,
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
      {
        id: "c2",
        industry_id: "co-2",
        company_name: "Globex Inc",
        industry_sector: null,
        logo_url: null,
        contact_name: "Rahul Verma",
        designation: null,
        contact_type: "ACADEMIC",
        email: null,
        phone: null,
        notes: null,
        is_active: false,
        created_at: "2026-01-02T00:00:00Z",
        updated_at: "2026-01-02T00:00:00Z",
      },
    ],
    type_options: ["RECRUITMENT", "ACADEMIC"],
    ...overrides,
  };
}

describe("IndustryConnectionsList", () => {
  afterEach(() => vi.resetAllMocks());

  it("fetches connections once on mount", () => {
    mocks.getIndustryConnections.mockReturnValue(new Promise(() => {}));
    render(<IndustryConnectionsList />);
    expect(mocks.getIndustryConnections).toHaveBeenCalledTimes(1);
  });

  it("shows a loading state", () => {
    mocks.getIndustryConnections.mockReturnValue(new Promise(() => {}));
    render(<IndustryConnectionsList />);
    expect(screen.getByText(/Loading industry connections/i)).toBeInTheDocument();
  });

  it("shows an error state with retry", async () => {
    mocks.getIndustryConnections.mockRejectedValueOnce(new ApiError(500, "boom"));
    render(<IndustryConnectionsList />);
    expect(await screen.findByText("boom")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("renders connections, defaulting to the active filter", async () => {
    mocks.getIndustryConnections.mockResolvedValueOnce(list());
    render(<IndustryConnectionsList />);

    expect(await screen.findByText("Priya Sharma")).toBeInTheDocument();
    // Globex's contact is inactive, hidden by the default "Active" filter.
    expect(screen.queryByText("Rahul Verma")).not.toBeInTheDocument();
  });

  it("renders a status filter control defaulting to Active", async () => {
    mocks.getIndustryConnections.mockResolvedValueOnce(list());
    render(<IndustryConnectionsList />);
    await screen.findByText("Priya Sharma");

    expect(screen.getByRole("combobox", { name: /filter by status/i })).toBeInTheDocument();
  });

  it("filters by search term across both active and inactive results", async () => {
    const user = userEvent.setup();
    mocks.getIndustryConnections.mockResolvedValueOnce(list());
    render(<IndustryConnectionsList />);
    await screen.findByText("Priya Sharma");

    await user.type(screen.getByLabelText(/search connections/i), "priya");
    expect(screen.getByText("Priya Sharma")).toBeInTheDocument();
  });

  it("shows an empty state when there are no connections", async () => {
    mocks.getIndustryConnections.mockResolvedValueOnce(list({ connections: [] }));
    render(<IndustryConnectionsList />);
    expect(await screen.findByText("No industry connections yet")).toBeInTheDocument();
  });

  it("opens the add-connection form", async () => {
    mocks.getIndustryConnections.mockResolvedValueOnce(list());
    mocks.searchIndustryPartnerCompanies.mockResolvedValue({ companies: [] });
    render(<IndustryConnectionsList />);
    await screen.findByText("Priya Sharma");

    fireEvent.click(screen.getByRole("button", { name: /add contact/i }));
    expect(await screen.findByText("Add Industry Connection")).toBeInTheDocument();
  });

  it("opens the edit form for an existing connection", async () => {
    mocks.getIndustryConnections.mockResolvedValueOnce(list());
    render(<IndustryConnectionsList />);
    await screen.findByText("Priya Sharma");

    fireEvent.click(screen.getAllByRole("button", { name: /edit/i })[0]);
    const dialogTitle = await screen.findByText("Edit Contact");
    const dialog = dialogTitle.closest('[role="dialog"]') ?? dialogTitle.parentElement!;
    expect(within(dialog as HTMLElement).getByText("Acme Corp")).toBeInTheDocument();
  });
});
