import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  verifyCertificate: vi.fn(),
}));

vi.mock("@/lib/public/certificates", () => mocks);

import { CertificateVerificationView } from "@/components/public/certificate-verification-view";
import { ApiError } from "@/lib/api";
import type { PublicCertificate } from "@/types/internship-completion";

function cert(over: Partial<PublicCertificate> = {}): PublicCertificate {
  return {
    certificate_number: "AIC-INT-2026-AAAAAAAAAAAAA",
    student_name: "Asha Rao",
    company_name: "TechNova",
    title: "ML Engineering Intern",
    issued_at: "2026-09-10T00:00:00Z",
    status: "VALID",
    ...over,
  };
}

describe("CertificateVerificationView", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows a loading state then a valid certificate", async () => {
    mocks.verifyCertificate.mockResolvedValueOnce(cert());
    render(<CertificateVerificationView certificateNumber="AIC-INT-2026-AAAAAAAAAAAAA" />);

    expect(screen.getByLabelText("Verifying certificate")).toBeInTheDocument();
    expect(await screen.findByText("Valid certificate")).toBeInTheDocument();
    expect(screen.getByText("Asha Rao")).toBeInTheDocument();
    expect(screen.getByText(/TechNova/)).toBeInTheDocument();
    expect(screen.getByText("AIC-INT-2026-AAAAAAAAAAAAA")).toBeInTheDocument();
  });

  it("shows a revoked certificate distinctly", async () => {
    mocks.verifyCertificate.mockResolvedValueOnce(cert({ status: "REVOKED" }));
    render(<CertificateVerificationView certificateNumber="AIC-INT-2026-AAAAAAAAAAAAA" />);
    expect(await screen.findByText("Revoked certificate")).toBeInTheDocument();
  });

  it("shows a not-found message for a 404", async () => {
    mocks.verifyCertificate.mockRejectedValueOnce(new ApiError(404, "Certificate not found."));
    render(<CertificateVerificationView certificateNumber="AIC-INT-2026-ZZZZZZZZZZZZZ" />);
    expect(await screen.findByText("No certificate matches this number.")).toBeInTheDocument();
  });

  it("shows a malformed-number message for a 422", async () => {
    mocks.verifyCertificate.mockRejectedValueOnce(
      new ApiError(422, "That doesn't look like a valid certificate number."),
    );
    render(<CertificateVerificationView certificateNumber="not-a-number" />);
    expect(
      (await screen.findAllByText("That doesn't look like a valid certificate number.")).length,
    ).toBeGreaterThan(0);
  });

  it("never renders private fields", async () => {
    mocks.verifyCertificate.mockResolvedValueOnce(cert());
    const { container } = render(
      <CertificateVerificationView certificateNumber="AIC-INT-2026-AAAAAAAAAAAAA" />,
    );
    await screen.findByText("Valid certificate");
    expect(container.textContent).not.toMatch(/@|student_id|workspace_id|email/i);
  });
});
