import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ getInstitutionInternships: vi.fn() }));

vi.mock("@/lib/institution/internships", () => ({
  getInstitutionInternships: mocks.getInstitutionInternships,
}));

import { CompanyInternshipsCard } from "@/components/institution/industry-partners/company-internships-card";

describe("CompanyInternshipsCard", () => {
  afterEach(() => vi.resetAllMocks());

  it("requests internships scoped to this company", () => {
    mocks.getInstitutionInternships.mockReturnValue(new Promise(() => {}));
    render(<CompanyInternshipsCard industryId="co-1" />);
    expect(mocks.getInstitutionInternships).toHaveBeenCalledWith({ company_id: "co-1" });
  });

  it("shows an empty state when the institution has curated none from this company", async () => {
    mocks.getInstitutionInternships.mockResolvedValueOnce({ internships: [], mode_options: [], status_options: [] });
    render(<CompanyInternshipsCard industryId="co-1" />);
    expect(await screen.findByText(/hasn't curated any internships from this company/i)).toBeInTheDocument();
  });

  it("lists curated internships from this company with a link to the full record", async () => {
    mocks.getInstitutionInternships.mockResolvedValueOnce({
      internships: [
        {
          id: "i1", title: "Backend Intern", company_name: "Acme Corp", industry_id: "co-1", work_mode: "REMOTE",
          duration_months: 3, stipend_amount: null, stipend_currency: "INR", application_deadline: null,
          start_date: null, status: "PUBLISHED", association_id: "assoc-1", association_status: "ACTIVE",
          added_at: null, applicants_from_institution: 0, selected_from_institution: 0,
        },
      ],
      mode_options: ["REMOTE"],
      status_options: ["PUBLISHED"],
    });
    render(<CompanyInternshipsCard industryId="co-1" />);
    const link = await screen.findByText("Backend Intern");
    expect(link.closest("a")).toHaveAttribute("href", "/institution/internships/i1");
  });
});
