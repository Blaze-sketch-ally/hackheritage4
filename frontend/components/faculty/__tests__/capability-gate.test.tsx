import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const { useFacultyCapabilitiesContext } = vi.hoisted(() => ({
  useFacultyCapabilitiesContext: vi.fn(),
}));

vi.mock("@/lib/faculty/capabilities", async () => {
  const actual = await vi.importActual<typeof import("@/lib/faculty/capabilities")>("@/lib/faculty/capabilities");
  return { ...actual, useFacultyCapabilitiesContext };
});

import { CapabilityGate } from "@/components/faculty/capability-gate";

describe("CapabilityGate", () => {
  it("shows a checking-access state while capabilities are loading, never the gated content", () => {
    useFacultyCapabilitiesContext.mockReturnValue({ status: "loading" });
    render(
      <CapabilityGate capability="assessment_author" deniedMessage="nope">
        <p>Secret form</p>
      </CapabilityGate>,
    );

    expect(screen.getByText(/checking your access/i)).toBeInTheDocument();
    expect(screen.queryByText("Secret form")).not.toBeInTheDocument();
  });

  it("shows an error state, never the gated content, on a capability load error", () => {
    useFacultyCapabilitiesContext.mockReturnValue({ status: "error", error: new Error("boom") });
    render(
      <CapabilityGate capability="assessment_author" deniedMessage="nope">
        <p>Secret form</p>
      </CapabilityGate>,
    );

    expect(screen.getByText(/could not verify your access/i)).toBeInTheDocument();
    expect(screen.queryByText("Secret form")).not.toBeInTheDocument();
  });

  it("renders a clean unauthorized state, never the gated content, when the single required capability is missing", () => {
    useFacultyCapabilitiesContext.mockReturnValue({ status: "ready", capabilities: [] });
    render(
      <CapabilityGate capability="assessment_author" deniedMessage="Ask an Admin for Author.">
        <p>Secret form</p>
      </CapabilityGate>,
    );

    expect(screen.getByText(/don't have permission/i)).toBeInTheDocument();
    expect(screen.getByText("Ask an Admin for Author.")).toBeInTheDocument();
    expect(screen.queryByText("Secret form")).not.toBeInTheDocument();
  });

  it("renders the gated content when the single required capability is held", () => {
    useFacultyCapabilitiesContext.mockReturnValue({ status: "ready", capabilities: ["assessment_author"] });
    render(
      <CapabilityGate capability="assessment_author" deniedMessage="nope">
        <p>Secret form</p>
      </CapabilityGate>,
    );

    expect(screen.getByText("Secret form")).toBeInTheDocument();
    expect(screen.queryByText(/don't have permission/i)).not.toBeInTheDocument();
  });

  it("renders the gated content when any one of anyOf's capabilities is held", () => {
    useFacultyCapabilitiesContext.mockReturnValue({ status: "ready", capabilities: ["assessment_reviewer"] });
    render(
      <CapabilityGate anyOf={["assessment_author", "assessment_reviewer"]} deniedMessage="nope">
        <p>Question bank</p>
      </CapabilityGate>,
    );

    expect(screen.getByText("Question bank")).toBeInTheDocument();
  });

  it("denies access when none of anyOf's capabilities is held", () => {
    useFacultyCapabilitiesContext.mockReturnValue({ status: "ready", capabilities: ["assessment_evaluator"] });
    render(
      <CapabilityGate anyOf={["assessment_author", "assessment_reviewer"]} deniedMessage="nope">
        <p>Question bank</p>
      </CapabilityGate>,
    );

    expect(screen.queryByText("Question bank")).not.toBeInTheDocument();
    expect(screen.getByText(/don't have permission/i)).toBeInTheDocument();
  });
});
