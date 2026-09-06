import { afterEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: { get: mocks.get, post: mocks.post },
  ApiError: class ApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
    }
  },
}));

import {
  getLearningResource,
  getRecommendedLearningResources,
  listLearningResources,
  listMyLearningProgress,
  setLearningProgress,
} from "@/lib/student/learning";

describe("lib/student/learning", () => {
  afterEach(() => vi.resetAllMocks());

  it("listLearningResources hits the resources endpoint with no query when unfiltered", () => {
    mocks.get.mockResolvedValueOnce({ resources: [] });
    void listLearningResources();
    expect(mocks.get).toHaveBeenCalledWith("/api/v1/student/learning/resources");
  });

  it("listLearningResources passes only the supported server-side filters", () => {
    mocks.get.mockResolvedValueOnce({ resources: [] });
    void listLearningResources({
      skillId: "11111111-1111-1111-1111-111111111111",
      difficulty: "Advanced",
      resourceType: "VIDEO",
    });
    const url = mocks.get.mock.calls[0][0] as string;
    const qs = new URLSearchParams(url.split("?")[1]);
    expect(qs.get("skill_id")).toBe("11111111-1111-1111-1111-111111111111");
    expect(qs.get("difficulty")).toBe("Advanced");
    expect(qs.get("resource_type")).toBe("VIDEO");
    // no unsupported params
    expect(qs.get("search")).toBeNull();
    expect(qs.get("student_id")).toBeNull();
  });

  it("getLearningResource encodes the id into the path", () => {
    mocks.get.mockResolvedValueOnce({});
    void getLearningResource("abc/def");
    expect(mocks.get).toHaveBeenCalledWith("/api/v1/student/learning/resources/abc%2Fdef");
  });

  it("listMyLearningProgress hits the progress endpoint", () => {
    mocks.get.mockResolvedValueOnce({ progress: [] });
    void listMyLearningProgress();
    expect(mocks.get).toHaveBeenCalledWith("/api/v1/student/learning/progress");
  });

  it("setLearningProgress POSTs a body of ONLY { status } -- nothing else", () => {
    mocks.post.mockResolvedValueOnce({ resource_id: "r1", status: "COMPLETED" });
    void setLearningProgress("r1", "COMPLETED");

    expect(mocks.post).toHaveBeenCalledTimes(1);
    const [path, body] = mocks.post.mock.calls[0];
    expect(path).toBe("/api/v1/student/learning/resources/r1/progress");
    expect(body).toEqual({ status: "COMPLETED" });
    // explicitly: none of the server-owned fields are ever sent
    for (const forbidden of [
      "student_id",
      "started_at",
      "completed_at",
      "created_at",
      "updated_at",
      "score",
      "percentage",
      "is_verified",
      "verified",
      "verified_at",
      "assessment_id",
      "student_skill_id",
    ]) {
      expect(body).not.toHaveProperty(forbidden);
    }
  });

  it("getRecommendedLearningResources hits /recommended with no query and no body", () => {
    mocks.get.mockResolvedValueOnce({ mode: "PERSONAL", recommendations: [] });
    void getRecommendedLearningResources();
    expect(mocks.get).toHaveBeenCalledTimes(1);
    expect(mocks.get).toHaveBeenCalledWith("/api/v1/student/learning/recommended");
    // no second arg -- no student_id, no skill id, nothing
    expect(mocks.get.mock.calls[0]).toHaveLength(1);
    expect(mocks.post).not.toHaveBeenCalled();
  });

  it.each(["SAVED", "IN_PROGRESS", "COMPLETED"] as const)(
    "setLearningProgress forwards the %s status verbatim",
    (status) => {
      mocks.post.mockResolvedValueOnce({ resource_id: "r1", status });
      void setLearningProgress("r1", status);
      expect(mocks.post.mock.calls[0][1]).toEqual({ status });
    },
  );
});
