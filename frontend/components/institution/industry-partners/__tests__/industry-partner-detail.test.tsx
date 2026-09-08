import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  getIndustryPartner: vi.fn(),
  searchIndustryPartnerCompanies: vi.fn(),
}));

vi.mock("@/lib/institution/industry-partners", () => ({
  getIndustryPartner: mocks.getIndustryPartner,
  createIndustryPartnerRelationship: vi.fn(),
  updateIndustryPartnerRelationship: vi.fn(),
  searchIndustryPartnerCompanies: mocks.searchIndustryPartnerCompanies,
}));

import { IndustryPartnerDetail } from "@/components/institution/industry-partners/industry-partner-detail";
import { ApiError } from "@/lib/api";
import type { IndustryPartnerDetail as IndustryPartnerDetailData } from "@/types/institution-industry";

function detail(overrides: Partial<IndustryPartnerDetailData> = {}): IndustryPartnerDetailData {
  return {
    id: "co-1",
    company_name: "Acme Corp",
    industry_sector: "Software",
    company_size: "201-500",
    website_url: "https://acme.example",
    headquarters_location: "Bangalore",
    company_description: "We build things.",
    logo_url: null,
    linkedin_url: null,
    relationship_id: "rel-1",
    relationship_type: "RECRUITMENT",
    relationship_status: "ACTIVE",
    notes: "Strong recruiter, visits every year.",
    has_explicit_relationship: true,
    jobs: { opportunities: 3, applicants: 10, selected_students: 4, titles: ["Software Engineer"] },
    internships: { opportunities: 1, applicants: 5, selected: 2, completed: 1, titles: ["Backend Intern"] },
    placement_drives: {
      count: 1,
      unique_students_selected: 4,
      drives: [
        { id: "drive-1", title: "Campus Drive 2026", status: "COMPLETED", applied_count: 10, selected_count: 4, selection_rate: 40 },
      ],
    },
    collaborations: { count: 1, latest_status: "ACTIVE", latest_title: "Research tie-up" },
    students_selected: 4,
    last_activity_at: "2026-02-01T00:00:00Z",
    tenancy_note: "Tenancy note",
    privacy_note: "Privacy note",
    ...overrides,
  };
}

describe("IndustryPartnerDetail", () => {
  afterEach(() => vi.resetAllMocks());

  it("fetches the partner once on mount", () => {
    mocks.getIndustryPartner.mockReturnValue(new Promise(() => {}));
    render(<IndustryPartnerDetail industryId="co-1" />);
    expect(mocks.getIndustryPartner).toHaveBeenCalledWith("co-1");
  });

  it("shows a loading state", () => {
    mocks.getIndustryPartner.mockReturnValue(new Promise(() => {}));
    render(<IndustryPartnerDetail industryId="co-1" />);
    expect(screen.getByText(/Loading industry partner/i)).toBeInTheDocument();
  });

  it("shows a not-visible message on 404", async () => {
    mocks.getIndustryPartner.mockRejectedValueOnce(new ApiError(404, "not found"));
    render(<IndustryPartnerDetail industryId="co-1" />);
    expect(await screen.findByText(/isn't visible to your institution/i)).toBeInTheDocument();
  });

  it("renders overview, relationship, jobs, internships, drives and collaborations", async () => {
    mocks.getIndustryPartner.mockResolvedValueOnce(detail());
    render(<IndustryPartnerDetail industryId="co-1" />);

    expect(await screen.findByText("Acme Corp")).toBeInTheDocument();
    expect(screen.getByText("We build things.")).toBeInTheDocument();
    expect(screen.getByText("Strong recruiter, visits every year.")).toBeInTheDocument();
    expect(screen.getByText("Software Engineer")).toBeInTheDocument();
    expect(screen.getByText("Backend Intern")).toBeInTheDocument();
    expect(screen.getByText("Campus Drive 2026")).toBeInTheDocument();
    expect(screen.getByText("Research tie-up")).toBeInTheDocument();
  });

  it("distinguishes job-selected students from internship-selected offers", async () => {
    mocks.getIndustryPartner.mockResolvedValueOnce(detail());
    render(<IndustryPartnerDetail industryId="co-1" />);
    await screen.findByText("Acme Corp");
    // Jobs card: 4 selected students; Internships card: 2 selected offers.
    expect(screen.getByText("Selected Students")).toBeInTheDocument();
    expect(screen.getByText("Selected Offers")).toBeInTheDocument();
  });

  it("shows N/A for a drive's selection rate instead of a fabricated value", async () => {
    mocks.getIndustryPartner.mockResolvedValueOnce(
      detail({
        placement_drives: {
          count: 1,
          unique_students_selected: 0,
          drives: [
            { id: "drive-1", title: "Empty Drive", status: "OPEN", applied_count: 0, selected_count: 0, selection_rate: null },
          ],
        },
      }),
    );
    render(<IndustryPartnerDetail industryId="co-1" />);
    expect(await screen.findByText("Empty Drive")).toBeInTheDocument();
    expect(screen.getByText("N/A")).toBeInTheDocument();
  });

  it("shows a not-tracked message when there is no explicit relationship", async () => {
    mocks.getIndustryPartner.mockResolvedValueOnce(
      detail({
        relationship_id: null,
        relationship_type: null,
        relationship_status: null,
        notes: null,
        has_explicit_relationship: false,
      }),
    );
    render(<IndustryPartnerDetail industryId="co-1" />);
    expect(await screen.findByText(/No explicit relationship tracked yet/i)).toBeInTheDocument();
  });

  it("never shows student contact info or industry-private notes, only aggregate privacy note", async () => {
    mocks.getIndustryPartner.mockResolvedValueOnce(detail());
    render(<IndustryPartnerDetail industryId="co-1" />);
    await screen.findByText("Acme Corp");
    expect(screen.queryByText(/@/)).not.toBeInTheDocument();
    expect(screen.getByText("Privacy note")).toBeInTheDocument();
    expect(screen.getByText("Tenancy note")).toBeInTheDocument();
  });
});
