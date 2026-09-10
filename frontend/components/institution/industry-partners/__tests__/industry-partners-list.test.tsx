import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getIndustryPartners: vi.fn(),
  getIndustryPartnerMetrics: vi.fn(),
  createIndustryPartnerRelationship: vi.fn(),
  searchIndustryPartnerCompanies: vi.fn(),
}));

vi.mock("@/lib/institution/industry-partners", () => ({
  getIndustryPartners: mocks.getIndustryPartners,
  getIndustryPartnerMetrics: mocks.getIndustryPartnerMetrics,
  createIndustryPartnerRelationship: mocks.createIndustryPartnerRelationship,
  updateIndustryPartnerRelationship: vi.fn(),
  searchIndustryPartnerCompanies: mocks.searchIndustryPartnerCompanies,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

import { IndustryPartnersList } from "@/components/institution/industry-partners/industry-partners-list";
import { ApiError } from "@/lib/api";
import type { IndustryPartnerListResponse, IndustryPartnerMetrics } from "@/types/institution-industry";

function list(overrides: Partial<IndustryPartnerListResponse> = {}): IndustryPartnerListResponse {
  return {
    partners: [
      {
        id: "co-1",
        company_name: "Acme Corp",
        industry_sector: "Software",
        logo_url: null,
        website_url: null,
        headquarters_location: "Bangalore",
        relationship_id: "rel-1",
        relationship_type: "RECRUITMENT",
        relationship_status: "ACTIVE",
        has_explicit_relationship: true,
        jobs_opportunities: 3,
        jobs_selected_students: 5,
        internship_opportunities: 1,
        internship_selected: 2,
        placement_drives_count: 2,
        students_selected: 5,
        last_activity_at: "2026-02-01T00:00:00Z",
      },
      {
        id: "co-2",
        company_name: "Globex Inc",
        industry_sector: "Manufacturing",
        logo_url: null,
        website_url: null,
        headquarters_location: null,
        relationship_id: null,
        relationship_type: null,
        relationship_status: null,
        has_explicit_relationship: false,
        jobs_opportunities: 0,
        jobs_selected_students: 0,
        internship_opportunities: 0,
        internship_selected: 0,
        placement_drives_count: 0,
        students_selected: 0,
        last_activity_at: null,
      },
    ],
    type_options: ["RECRUITMENT", "TRAINING"],
    status_options: ["PROSPECT", "ACTIVE", "INACTIVE"],
    ...overrides,
  };
}

function metrics(overrides: Partial<IndustryPartnerMetrics> = {}) {
  return {
    metrics: {
      total_partners: 2,
      active_partners: 1,
      recruiting_partners: 1,
      internship_partners: 1,
      placement_drives_total: 2,
      students_selected_total: 5,
      internship_students_total: 2,
      ...overrides,
    },
    tenancy_note: "Tenancy note",
  };
}

describe("IndustryPartnersList", () => {
  afterEach(() => vi.resetAllMocks());

  it("fetches partners and metrics once on mount", () => {
    mocks.getIndustryPartners.mockReturnValue(new Promise(() => {}));
    mocks.getIndustryPartnerMetrics.mockReturnValue(new Promise(() => {}));
    render(<IndustryPartnersList />);
    expect(mocks.getIndustryPartners).toHaveBeenCalledTimes(1);
    expect(mocks.getIndustryPartnerMetrics).toHaveBeenCalledTimes(1);
  });

  it("shows a loading state", () => {
    mocks.getIndustryPartners.mockReturnValue(new Promise(() => {}));
    mocks.getIndustryPartnerMetrics.mockReturnValue(new Promise(() => {}));
    render(<IndustryPartnersList />);
    expect(screen.getByText(/Loading industry partners/i)).toBeInTheDocument();
  });

  it("shows an error state with retry", async () => {
    mocks.getIndustryPartners.mockRejectedValueOnce(new ApiError(500, "boom"));
    mocks.getIndustryPartnerMetrics.mockResolvedValueOnce(metrics());
    render(<IndustryPartnersList />);
    expect(await screen.findByText("boom")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("renders KPIs and the partner table", async () => {
    mocks.getIndustryPartners.mockResolvedValueOnce(list());
    mocks.getIndustryPartnerMetrics.mockResolvedValueOnce(metrics());
    render(<IndustryPartnersList />);

    expect(await screen.findByText("Acme Corp")).toBeInTheDocument();
    expect(screen.getByText("Globex Inc")).toBeInTheDocument();
    expect(screen.getByText("Total Partners")).toBeInTheDocument();
    expect(screen.getByText("Not tracked")).toBeInTheDocument();
    expect(screen.getByText("No recorded activity")).toBeInTheDocument();
  });

  it("filters by search term", async () => {
    const user = userEvent.setup();
    mocks.getIndustryPartners.mockResolvedValueOnce(list());
    mocks.getIndustryPartnerMetrics.mockResolvedValueOnce(metrics());
    render(<IndustryPartnersList />);
    await screen.findByText("Acme Corp");

    await user.type(screen.getByLabelText(/search companies/i), "globex");
    expect(screen.queryByText("Acme Corp")).not.toBeInTheDocument();
    expect(screen.getByText("Globex Inc")).toBeInTheDocument();
  });

  it("shows an empty state when there are no partners", async () => {
    mocks.getIndustryPartners.mockResolvedValueOnce(list({ partners: [] }));
    mocks.getIndustryPartnerMetrics.mockResolvedValueOnce(metrics({ total_partners: 0, active_partners: 0, recruiting_partners: 0, internship_partners: 0 }));
    render(<IndustryPartnersList />);
    expect(await screen.findByText("No industry partners yet")).toBeInTheDocument();
  });

  it("opens the add-partner form", async () => {
    const user = userEvent.setup();
    mocks.getIndustryPartners.mockResolvedValueOnce(list());
    mocks.getIndustryPartnerMetrics.mockResolvedValueOnce(metrics());
    mocks.searchIndustryPartnerCompanies.mockResolvedValue({ companies: [] });
    render(<IndustryPartnersList />);
    await screen.findByText("Acme Corp");

    await user.click(screen.getByRole("button", { name: /add partner/i }));
    expect(await screen.findByText("Add Industry Partner")).toBeInTheDocument();
  });
});
