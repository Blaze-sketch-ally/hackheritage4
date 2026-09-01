import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { GraduationCap } from "lucide-react";
import { ModuleSummaryCard, type ModuleSummaryState } from "@/components/industry/dashboard/module-summary-card";

const STATUS_ORDER = ["DRAFT", "PUBLISHED", "CLOSED", "ARCHIVED"] as const;
const STATUS_LABELS: Record<string, string> = {
  DRAFT: "Draft",
  PUBLISHED: "Published",
  CLOSED: "Closed",
  ARCHIVED: "Archived",
};

function renderCard(state: ModuleSummaryState, overrides: Partial<React.ComponentProps<typeof ModuleSummaryCard>> = {}) {
  return render(
    <ModuleSummaryCard
      title="Internships"
      icon={GraduationCap}
      listHref="/industry/internships"
      createHref="/industry/internships/create"
      statusOrder={STATUS_ORDER}
      statusLabels={STATUS_LABELS}
      state={state}
      {...overrides}
    />,
  );
}

describe("ModuleSummaryCard", () => {
  it("renders the module title", () => {
    renderCard({ status: "loading" });
    expect(screen.getByText("Internships")).toBeInTheDocument();
  });

  it("shows a loading state", () => {
    renderCard({ status: "loading" });
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("shows an error message without crashing", () => {
    renderCard({ status: "error", message: "Could not load internships." });
    expect(screen.getByText("Could not load internships.")).toBeInTheDocument();
  });

  it("renders total and per-status counts", () => {
    renderCard({ status: "ready", total: 5, counts: { DRAFT: 2, PUBLISHED: 3 } });
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("Draft:")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("Published:")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("only shows statuses with a non-zero count", () => {
    renderCard({ status: "ready", total: 2, counts: { DRAFT: 2, PUBLISHED: 0, CLOSED: 0, ARCHIVED: 0 } });
    expect(screen.getByText("Draft:")).toBeInTheDocument();
    expect(screen.queryByText("Published:")).not.toBeInTheDocument();
    expect(screen.queryByText("Closed:")).not.toBeInTheDocument();
    expect(screen.queryByText("Archived:")).not.toBeInTheDocument();
  });

  it("handles a zero total gracefully", () => {
    renderCard({ status: "ready", total: 0, counts: {} });
    expect(screen.getByText("None yet.")).toBeInTheDocument();
  });

  it("renders a working list link", () => {
    renderCard({ status: "ready", total: 1, counts: { DRAFT: 1 } });
    // The CTA is a Base UI <Button> rendered as a Next.js <Link>, so it is
    // an <a href> exposed with role="button" (nativeButton={false}) --
    // matches the pattern used elsewhere in this app (see student components).
    expect(screen.getByRole("button", { name: "View all" })).toHaveAttribute(
      "href",
      "/industry/internships",
    );
  });

  it("renders a create link when provided", () => {
    renderCard({ status: "ready", total: 0, counts: {} });
    expect(screen.getByRole("button", { name: "Create" })).toHaveAttribute(
      "href",
      "/industry/internships/create",
    );
  });

  it("does not render a create link when none is provided (e.g. modules without a create CTA)", () => {
    renderCard({ status: "ready", total: 0, counts: {} }, { createHref: undefined });
    expect(screen.queryByRole("button", { name: "Create" })).not.toBeInTheDocument();
  });

  it("respects a custom create label", () => {
    renderCard({ status: "ready", total: 0, counts: {} }, { createLabel: "Propose Collaboration" });
    expect(screen.getByRole("button", { name: "Propose Collaboration" })).toBeInTheDocument();
  });

  it("passes nativeButton={false} so its Link CTAs emit no Base UI native-button error (QA finding F1)", () => {
    // The <Button render={<Link/>}> CTAs render an <a>, not a <button>, so
    // they must be given nativeButton={false}. Without it Base UI (a) logs
    // "...expected a native <button>..." on every render and (b) puts a
    // stray type="button" on the anchor instead of role="button".
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    try {
      renderCard({ status: "ready", total: 1, counts: { DRAFT: 1 } });

      const viewAll = screen.getByRole("button", { name: "View all" });
      const create = screen.getByRole("button", { name: "Create" });
      // Deterministic DOM contract of nativeButton={false} on a non-button:
      expect(viewAll.tagName).toBe("A");
      expect(viewAll).not.toHaveAttribute("type");
      expect(create.tagName).toBe("A");
      expect(create).not.toHaveAttribute("type");

      const nativeButtonWarning = errorSpy.mock.calls.find((args) =>
        args.some((a) => typeof a === "string" && a.includes("expected a native <button>")),
      );
      expect(nativeButtonWarning).toBeUndefined();
    } finally {
      errorSpy.mockRestore();
    }
  });

  it("does not assume a universal lifecycle -- uses whatever statusOrder/statusLabels it's given", () => {
    renderCard(
      { status: "ready", total: 1, counts: { SENT: 1 } },
      {
        statusOrder: ["DRAFT", "SENT", "ACCEPTED", "REJECTED", "ACTIVE", "COMPLETED", "CANCELLED"],
        statusLabels: {
          DRAFT: "Draft",
          SENT: "Sent",
          ACCEPTED: "Accepted",
          REJECTED: "Rejected",
          ACTIVE: "Active",
          COMPLETED: "Completed",
          CANCELLED: "Cancelled",
        },
      },
    );
    expect(screen.getByText("Sent:")).toBeInTheDocument();
    expect(screen.queryByText("Published:")).not.toBeInTheDocument();
  });
});
