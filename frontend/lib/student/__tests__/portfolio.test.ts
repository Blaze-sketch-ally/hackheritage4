import { afterEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: { get: mocks.get, post: mocks.post, put: mocks.put, delete: mocks.del },
  ApiError: class ApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
    }
  },
}));

import {
  createAchievement,
  createCertification,
  createProject,
  deleteAchievement,
  deleteCertification,
  deleteProject,
  getPortfolio,
  getProject,
  listAchievements,
  listCertifications,
  listProjects,
  updateProject,
} from "@/lib/student/portfolio";

const FORBIDDEN = ["student_id", "owner_id", "id", "created_at", "updated_at", "is_verified"];

describe("lib/student/portfolio", () => {
  afterEach(() => vi.resetAllMocks());

  it("reads hit the right endpoints with no query string", () => {
    mocks.get.mockResolvedValue({});
    void getPortfolio();
    void listProjects();
    void listCertifications();
    void listAchievements();
    void getProject("p1/x");
    expect(mocks.get.mock.calls.map((c) => c[0])).toEqual([
      "/api/v1/student/portfolio",
      "/api/v1/student/projects",
      "/api/v1/student/certifications",
      "/api/v1/student/achievements",
      "/api/v1/student/projects/p1%2Fx",
    ]);
  });

  it("createProject POSTs only the input body -- never an ownership field", () => {
    mocks.post.mockResolvedValue({});
    void createProject({ title: "P", skill_ids: ["s1"] });
    const [path, body] = mocks.post.mock.calls[0];
    expect(path).toBe("/api/v1/student/projects");
    expect(body).toEqual({ title: "P", skill_ids: ["s1"] });
    for (const f of FORBIDDEN) expect(body).not.toHaveProperty(f);
  });

  it("createCertification / createAchievement send only their input", () => {
    mocks.post.mockResolvedValue({});
    void createCertification({ name: "C" });
    void createAchievement({ title: "A" });
    expect(mocks.post.mock.calls[0]).toEqual(["/api/v1/student/certifications", { name: "C" }]);
    expect(mocks.post.mock.calls[1]).toEqual(["/api/v1/student/achievements", { title: "A" }]);
    for (const [, body] of mocks.post.mock.calls) {
      for (const f of FORBIDDEN) expect(body).not.toHaveProperty(f);
    }
  });

  it("updateProject PUTs to the id-scoped path", () => {
    mocks.put.mockResolvedValue({});
    void updateProject("abc", { title: "New" });
    expect(mocks.put.mock.calls[0]).toEqual(["/api/v1/student/projects/abc", { title: "New" }]);
  });

  it("delete calls hit the id-scoped path", () => {
    mocks.del.mockResolvedValue(undefined);
    void deleteProject("p1");
    void deleteCertification("c1");
    void deleteAchievement("a1");
    expect(mocks.del.mock.calls.map((c) => c[0])).toEqual([
      "/api/v1/student/projects/p1",
      "/api/v1/student/certifications/c1",
      "/api/v1/student/achievements/a1",
    ]);
  });
});
