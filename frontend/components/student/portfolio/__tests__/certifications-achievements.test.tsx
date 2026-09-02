import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  listCertifications: vi.fn(),
  createCertification: vi.fn(),
  updateCertification: vi.fn(),
  deleteCertification: vi.fn(),
  listAchievements: vi.fn(),
  createAchievement: vi.fn(),
  updateAchievement: vi.fn(),
  deleteAchievement: vi.fn(),
}));

vi.mock("@/lib/student/portfolio", () => mocks);

import { CertificationsView } from "@/components/student/portfolio/certifications-view";
import { AchievementsView } from "@/components/student/portfolio/achievements-view";
import { ApiError } from "@/lib/api";

const cert = {
  id: "c1",
  name: "AWS CCP",
  issuing_organization: "AWS",
  issue_date: "2026-02-01",
  expiry_date: null,
  credential_id: null,
  credential_url: null,
  created_at: null,
  updated_at: null,
};
const ach = {
  id: "a1",
  title: "Hackathon Winner",
  description: "1st place",
  achievement_date: "2026-08-30",
  issuing_organization: "AIC",
  url: null,
  created_at: null,
  updated_at: null,
};

describe("CertificationsView", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows a truthful empty state", async () => {
    mocks.listCertifications.mockResolvedValue({ certifications: [] });
    render(<CertificationsView />);
    expect(await screen.findByText("No certifications yet")).toBeInTheDocument();
  });

  it("renders real certifications and creates one without an ownership field", async () => {
    mocks.listCertifications.mockResolvedValue({ certifications: [cert] });
    mocks.createCertification.mockResolvedValue({ ...cert, id: "c2", name: "GCP ACE" });
    render(<CertificationsView />);
    expect(await screen.findByText("AWS CCP")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /add certification/i }));
    await userEvent.type(screen.getByLabelText("Name *"), "GCP ACE");
    await userEvent.click(screen.getByRole("button", { name: /^add certification$/i }));

    await waitFor(() => expect(mocks.createCertification).toHaveBeenCalled());
    const body = mocks.createCertification.mock.calls[0][0];
    expect(body.name).toBe("GCP ACE");
    expect(body).not.toHaveProperty("student_id");
    expect(await screen.findByText("GCP ACE")).toBeInTheDocument();
  });

  it("validates expiry not before issue date", async () => {
    mocks.listCertifications.mockResolvedValue({ certifications: [] });
    render(<CertificationsView />);
    await userEvent.click(await screen.findByRole("button", { name: /add your first certification/i }));
    await userEvent.type(screen.getByLabelText("Name *"), "X");
    await userEvent.type(screen.getByLabelText("Issue date"), "2026-06-01");
    await userEvent.type(screen.getByLabelText("Expiry date"), "2026-01-01");
    await userEvent.click(screen.getByRole("button", { name: /^add certification$/i }));
    expect(await screen.findByText(/expiry date can't be before/i)).toBeInTheDocument();
    expect(mocks.createCertification).not.toHaveBeenCalled();
  });

  it("deletes only after confirmation", async () => {
    mocks.listCertifications.mockResolvedValue({ certifications: [cert] });
    mocks.deleteCertification.mockResolvedValue(undefined);
    render(<CertificationsView />);
    await userEvent.click(await screen.findByRole("button", { name: "Delete" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: /delete certification/i }));
    await waitFor(() => expect(mocks.deleteCertification).toHaveBeenCalledWith("c1"));
  });
});

describe("AchievementsView", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows a truthful empty state", async () => {
    mocks.listAchievements.mockResolvedValue({ achievements: [] });
    render(<AchievementsView />);
    expect(await screen.findByText("No achievements yet")).toBeInTheDocument();
  });

  it("renders real achievements and creates one; error state has retry", async () => {
    mocks.listAchievements
      .mockRejectedValueOnce(new ApiError(500, "down"))
      .mockResolvedValueOnce({ achievements: [ach] });
    render(<AchievementsView />);
    await userEvent.click(await screen.findByRole("button", { name: /try again/i }));
    expect(await screen.findByText("Hackathon Winner")).toBeInTheDocument();

    mocks.createAchievement.mockResolvedValue({ ...ach, id: "a2", title: "Dean's List" });
    await userEvent.click(screen.getByRole("button", { name: /add achievement/i }));
    await userEvent.type(screen.getByLabelText("Title *"), "Dean's List");
    await userEvent.click(screen.getByRole("button", { name: /^add achievement$/i }));
    await waitFor(() => expect(mocks.createAchievement).toHaveBeenCalled());
    expect(mocks.createAchievement.mock.calls[0][0]).not.toHaveProperty("student_id");
    expect(await screen.findByText("Dean's List")).toBeInTheDocument();
  });
});
