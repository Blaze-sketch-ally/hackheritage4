import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { listMyExpressions, getIncomingCollaborations } = vi.hoisted(() => ({
  listMyExpressions: vi.fn(),
  getIncomingCollaborations: vi.fn(),
}));

vi.mock("@/lib/faculty/opportunities", () => ({
  listMyExpressions,
  withdrawExpression: vi.fn(),
}));

vi.mock("@/lib/industry/collaborations", () => ({
  getIncomingCollaborations,
  acceptCollaboration: vi.fn(),
  rejectCollaboration: vi.fn(),
}));

import { FacultyApplicationsTabs } from "@/components/faculty/faculty-applications-tabs";

describe("FacultyApplicationsTabs", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("keeps My EOIs and Collaboration Requests as separate, non-conflated tabs", async () => {
    listMyExpressions.mockResolvedValue({ expressions: [] });
    getIncomingCollaborations.mockResolvedValue({ collaborations: [] });

    render(<FacultyApplicationsTabs />);

    // My EOIs tab is the default and loads its own data source.
    expect(await screen.findByText(/haven't expressed interest/i)).toBeInTheDocument();
    expect(listMyExpressions).toHaveBeenCalled();

    await userEvent.click(screen.getByRole("tab", { name: /collaboration requests/i }));

    await waitFor(() => expect(getIncomingCollaborations).toHaveBeenCalled());
    expect(await screen.findByText(/no collaboration requests/i)).toBeInTheDocument();
  });
});
