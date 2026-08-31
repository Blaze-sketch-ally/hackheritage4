import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { listMyCertifications, createCertification, deleteCertification } = vi.hoisted(() => ({
  listMyCertifications: vi.fn(),
  createCertification: vi.fn(),
  updateCertification: vi.fn(),
  deleteCertification: vi.fn(),
}));

vi.mock("@/lib/student/portfolio", () => ({
  listMyCertifications,
  createCertification,
  updateCertification: vi.fn(),
  deleteCertification,
}));

import { CertificationList } from "@/components/portfolio/certification-list";
import { ApiError } from "@/lib/api";

function certification(overrides = {}) {
  return {
    id: "c1",
    student_id: "s1",
    name: "AWS Certified Cloud Practitioner",
    issuer: "Amazon Web Services",
    issue_date: "2025-06-01",
    credential_url: "https://aws.amazon.com/verification/abc123",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("CertificationList", () => {
  afterEach(() => vi.clearAllMocks());

  it("shows a loading state before data arrives", () => {
    listMyCertifications.mockReturnValue(new Promise(() => {}));
    render(<CertificationList />);
    expect(screen.getByLabelText("Loading certifications")).toBeInTheDocument();
  });

  it("shows the empty state with no mock data", async () => {
    listMyCertifications.mockResolvedValue({ certifications: [] });
    render(<CertificationList />);
    expect(
      await screen.findByText("Add certifications that strengthen your professional profile."),
    ).toBeInTheDocument();
  });

  it("renders a certification once loaded", async () => {
    listMyCertifications.mockResolvedValue({ certifications: [certification()] });
    render(<CertificationList />);
    expect(await screen.findByText("AWS Certified Cloud Practitioner")).toBeInTheDocument();
    expect(screen.getByText("Amazon Web Services")).toBeInTheDocument();
    expect(screen.getByText("View credential")).toBeInTheDocument();
  });

  it("shows an error state when the API call fails", async () => {
    listMyCertifications.mockRejectedValue(new ApiError(500, "Backend unavailable right now."));
    render(<CertificationList />);
    expect(await screen.findByText("Backend unavailable right now.")).toBeInTheDocument();
  });

  it("creates a certification through the inline form", async () => {
    listMyCertifications
      .mockResolvedValueOnce({ certifications: [] })
      .mockResolvedValueOnce({ certifications: [certification()] });
    createCertification.mockResolvedValue(certification());
    render(<CertificationList />);
    await screen.findByText("Add certifications that strengthen your professional profile.");

    await userEvent.click(screen.getByRole("button", { name: /add certification/i }));
    await userEvent.type(screen.getByLabelText("Certification name"), "AWS Certified Cloud Practitioner");
    await userEvent.type(screen.getByLabelText("Issuer"), "Amazon Web Services");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(createCertification).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("AWS Certified Cloud Practitioner")).toBeInTheDocument();
  });

  it("deletes a certification after confirmation", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    listMyCertifications
      .mockResolvedValueOnce({ certifications: [certification()] })
      .mockResolvedValueOnce({ certifications: [] });
    deleteCertification.mockResolvedValue(undefined);
    render(<CertificationList />);
    await screen.findByText("AWS Certified Cloud Practitioner");

    await userEvent.click(screen.getByRole("button", { name: /delete certification/i }));

    await waitFor(() => expect(deleteCertification).toHaveBeenCalledWith("c1"));
    confirmSpy.mockRestore();
  });
});
