import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import {
  EMPTY_OPPORTUNITY_FILTERS,
  OpportunityFilters,
  opportunityFiltersActive,
  opportunityFiltersFromParams,
  opportunityFiltersNarrow,
  opportunityFiltersToApiParams,
  opportunityFiltersToQuery,
} from "@/components/student/opportunities/opportunity-filters";

describe("OpportunityFilters (component)", () => {
  it("renders search + work mode + sort, and the stipend filter for internships", () => {
    render(
      <OpportunityFilters
        sourceType="INTERNSHIP"
        filters={EMPTY_OPPORTUNITY_FILTERS}
        onChange={vi.fn()}
        onReset={vi.fn()}
      />,
    );
    expect(screen.getByLabelText("Search internships")).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: /filter by work mode/i })).toBeInTheDocument();
    expect(
      screen.getByRole("combobox", { name: /filter by minimum stipend/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: /sort opportunities/i })).toBeInTheDocument();
    // no job-only control
    expect(
      screen.queryByRole("combobox", { name: /minimum salary/i }),
    ).not.toBeInTheDocument();
  });

  it("renders the salary filter for jobs and not the stipend filter", () => {
    render(
      <OpportunityFilters
        sourceType="JOB"
        filters={EMPTY_OPPORTUNITY_FILTERS}
        onChange={vi.fn()}
        onReset={vi.fn()}
      />,
    );
    expect(screen.getByLabelText("Search jobs")).toBeInTheDocument();
    expect(
      screen.getByRole("combobox", { name: /filter by minimum salary/i }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("combobox", { name: /minimum stipend/i }),
    ).not.toBeInTheDocument();
  });

  it("emits new search text without touching the other filters", async () => {
    const onChange = vi.fn();
    render(
      <OpportunityFilters
        sourceType="INTERNSHIP"
        filters={EMPTY_OPPORTUNITY_FILTERS}
        onChange={onChange}
        onReset={vi.fn()}
      />,
    );
    await userEvent.type(screen.getByLabelText("Search internships"), "d");
    expect(onChange).toHaveBeenLastCalledWith({ ...EMPTY_OPPORTUNITY_FILTERS, search: "d" });
  });

  it("shows Reset only when a filter is active, and Reset calls onReset", async () => {
    const onReset = vi.fn();
    const { rerender } = render(
      <OpportunityFilters
        sourceType="INTERNSHIP"
        filters={EMPTY_OPPORTUNITY_FILTERS}
        onChange={vi.fn()}
        onReset={onReset}
      />,
    );
    expect(screen.queryByRole("button", { name: /reset/i })).not.toBeInTheDocument();

    rerender(
      <OpportunityFilters
        sourceType="INTERNSHIP"
        filters={{ ...EMPTY_OPPORTUNITY_FILTERS, workMode: "REMOTE" }}
        onChange={vi.fn()}
        onReset={onReset}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: /reset/i }));
    expect(onReset).toHaveBeenCalledTimes(1);
  });
});

describe("opportunity filter helpers", () => {
  it("opportunityFiltersActive reflects every non-default control", () => {
    expect(opportunityFiltersActive(EMPTY_OPPORTUNITY_FILTERS)).toBe(false);
    expect(opportunityFiltersActive({ ...EMPTY_OPPORTUNITY_FILTERS, search: "x" })).toBe(true);
    expect(opportunityFiltersActive({ ...EMPTY_OPPORTUNITY_FILTERS, workMode: "HYBRID" })).toBe(true);
    expect(opportunityFiltersActive({ ...EMPTY_OPPORTUNITY_FILTERS, minComp: "20000" })).toBe(true);
    expect(opportunityFiltersActive({ ...EMPTY_OPPORTUNITY_FILTERS, sort: "deadline" })).toBe(true);
  });

  it("opportunityFiltersNarrow ignores sort (sort never hides results)", () => {
    expect(opportunityFiltersNarrow({ ...EMPTY_OPPORTUNITY_FILTERS, sort: "deadline" })).toBe(false);
    expect(opportunityFiltersNarrow({ ...EMPTY_OPPORTUNITY_FILTERS, search: "x" })).toBe(true);
  });

  it("opportunityFiltersFromParams reads valid values and snaps invalid ones to defaults", () => {
    const good = opportunityFiltersFromParams(
      new URLSearchParams("search=react&work_mode=REMOTE&min_stipend=20000&order_by=deadline"),
      "INTERNSHIP",
    );
    expect(good).toEqual({
      search: "react",
      workMode: "REMOTE",
      minComp: "20000",
      sort: "deadline",
    });

    const garbage = opportunityFiltersFromParams(
      new URLSearchParams("work_mode=banana&order_by=cheapest&min_stipend=abc"),
      "INTERNSHIP",
    );
    expect(garbage).toEqual(EMPTY_OPPORTUNITY_FILTERS);
  });

  it("opportunityFiltersFromParams keeps stipend/salary params to the right source type", () => {
    // a salary param on an internship URL is ignored, and vice versa
    expect(
      opportunityFiltersFromParams(new URLSearchParams("min_salary=1000000"), "INTERNSHIP").minComp,
    ).toBe("all");
    expect(
      opportunityFiltersFromParams(new URLSearchParams("min_stipend=20000"), "JOB").minComp,
    ).toBe("all");
    expect(
      opportunityFiltersFromParams(new URLSearchParams("min_salary=1000000"), "JOB").minComp,
    ).toBe("1000000");
  });

  it("opportunityFiltersToQuery only serializes non-default values", () => {
    expect(opportunityFiltersToQuery(EMPTY_OPPORTUNITY_FILTERS, "INTERNSHIP")).toBe("");
    expect(
      opportunityFiltersToQuery(
        { search: "  data  ", workMode: "REMOTE", minComp: "30000", sort: "deadline" },
        "INTERNSHIP",
      ),
    ).toBe("search=data&work_mode=REMOTE&min_stipend=30000&order_by=deadline");
    expect(
      opportunityFiltersToQuery(
        { search: "", workMode: "all", minComp: "1000000", sort: "newest" },
        "JOB",
      ),
    ).toBe("min_salary=1000000");
  });

  it("opportunityFiltersToApiParams maps compensation to the right key per source type", () => {
    const asInternship = opportunityFiltersToApiParams(
      { search: "x", workMode: "REMOTE", minComp: "20000", sort: "deadline" },
      "INTERNSHIP",
    );
    expect(asInternship).toEqual({
      sourceType: "INTERNSHIP",
      search: "x",
      workMode: "REMOTE",
      minStipend: 20000,
      minSalary: undefined,
      sort: "deadline",
    });

    const asJob = opportunityFiltersToApiParams(
      { search: "", workMode: "all", minComp: "1000000", sort: "newest" },
      "JOB",
    );
    expect(asJob).toEqual({
      sourceType: "JOB",
      search: undefined,
      workMode: undefined,
      minStipend: undefined,
      minSalary: 1000000,
      sort: "newest",
    });
  });
});
