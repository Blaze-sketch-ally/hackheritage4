import { beforeEach, describe, expect, it } from "vitest";
import {
  clearStoredAttempt,
  loadStoredAttempt,
  saveStoredAnswer,
  saveStoredAttempt,
} from "@/lib/student/assessment-session";

describe("assessment-session sessionStorage helpers", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
  });

  it("returns null when nothing is stored for an assessment", () => {
    expect(loadStoredAttempt("assessment-1")).toBeNull();
  });

  it("round-trips an attempt id and answers through sessionStorage", () => {
    saveStoredAttempt({
      assessmentId: "assessment-1",
      attemptId: "attempt-1",
      answers: { q1: { question_id: "q1", selected_option_ids: ["opt1"] } },
    });

    expect(loadStoredAttempt("assessment-1")).toEqual({
      assessmentId: "assessment-1",
      attemptId: "attempt-1",
      answers: { q1: { question_id: "q1", selected_option_ids: ["opt1"] } },
    });
  });

  it("keeps state isolated per assessment id", () => {
    saveStoredAttempt({ assessmentId: "a1", attemptId: "attempt-a", answers: {} });
    saveStoredAttempt({ assessmentId: "a2", attemptId: "attempt-b", answers: {} });

    expect(loadStoredAttempt("a1")?.attemptId).toBe("attempt-a");
    expect(loadStoredAttempt("a2")?.attemptId).toBe("attempt-b");
  });

  it("saveStoredAnswer merges into existing answers for the same attempt", () => {
    saveStoredAttempt({
      assessmentId: "a1",
      attemptId: "attempt-1",
      answers: { q1: { question_id: "q1", answer_text: "first" } },
    });

    saveStoredAnswer("a1", "attempt-1", { question_id: "q2", selected_option_ids: ["opt9"] });

    expect(loadStoredAttempt("a1")?.answers).toEqual({
      q1: { question_id: "q1", answer_text: "first" },
      q2: { question_id: "q2", selected_option_ids: ["opt9"] },
    });
  });

  it("saveStoredAnswer discards stale answers if the attempt id changed", () => {
    saveStoredAttempt({
      assessmentId: "a1",
      attemptId: "old-attempt",
      answers: { q1: { question_id: "q1", answer_text: "stale" } },
    });

    saveStoredAnswer("a1", "new-attempt", { question_id: "q2", answer_text: "fresh" });

    expect(loadStoredAttempt("a1")).toEqual({
      assessmentId: "a1",
      attemptId: "new-attempt",
      answers: { q2: { question_id: "q2", answer_text: "fresh" } },
    });
  });

  it("clearStoredAttempt removes only the given assessment's entry", () => {
    saveStoredAttempt({ assessmentId: "a1", attemptId: "attempt-a", answers: {} });
    saveStoredAttempt({ assessmentId: "a2", attemptId: "attempt-b", answers: {} });

    clearStoredAttempt("a1");

    expect(loadStoredAttempt("a1")).toBeNull();
    expect(loadStoredAttempt("a2")?.attemptId).toBe("attempt-b");
  });

  it("treats corrupt stored JSON the same as nothing stored", () => {
    window.sessionStorage.setItem("aic:assessment-attempt:a1", "{not valid json");
    expect(loadStoredAttempt("a1")).toBeNull();
  });

  it("ignores a stored entry whose assessmentId doesn't match the key (defensive)", () => {
    window.sessionStorage.setItem(
      "aic:assessment-attempt:a1",
      JSON.stringify({ assessmentId: "different", attemptId: "x", answers: {} }),
    );
    expect(loadStoredAttempt("a1")).toBeNull();
  });
});
