import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ApiError } from "@/lib/api";

const mocks = vi.hoisted(() => ({
  sendCareerChatMessage: vi.fn(),
}));

vi.mock("@/lib/student/career-chat", () => ({
  sendCareerChatMessage: mocks.sendCareerChatMessage,
}));

import { CareerChatWidget } from "@/components/ai/career-chat-widget";
import type { CareerChatResponse } from "@/types/career-chat";

const BASE_META = {
  provider: "groq" as const,
  model: "test",
  ai_available: true,
  intent: "SKILL_GAP" as const,
  intent_source: "KEYWORD" as const,
};

function response(overrides: Partial<CareerChatResponse> = {}): CareerChatResponse {
  return {
    message: "Your highest-priority skill gap is Python.",
    intent: "SKILL_GAP",
    cards: [],
    suggested_actions: [],
    meta: BASE_META,
    disclaimer: "Career AI explanations are advisory.",
    ...overrides,
  };
}

async function openWidget() {
  const user = userEvent.setup();
  render(<CareerChatWidget />);
  await user.click(screen.getByRole("button", { name: /open career ai chat/i }));
  return user;
}

describe("CareerChatWidget", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows the launcher and starts closed", () => {
    render(<CareerChatWidget />);
    expect(screen.getByRole("button", { name: /open career ai chat/i })).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("opens the drawer when the launcher is clicked", async () => {
    await openWidget();
    expect(screen.getByRole("dialog", { name: /career ai chat/i })).toBeInTheDocument();
    expect(screen.getByText("Your personalized career assistant")).toBeInTheDocument();
  });

  it("closes the drawer via the close button", async () => {
    const user = await openWidget();
    await user.click(screen.getByRole("button", { name: /close career ai chat/i }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("closes the drawer on Escape", async () => {
    const user = await openWidget();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("shows quick prompts when empty", async () => {
    await openWidget();
    expect(screen.getByRole("button", { name: "What should I learn next?" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Show my skill gaps" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Recommend jobs for me" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "What's my career plan?" })).toBeInTheDocument();
  });

  it("sends a quick prompt and renders the assistant reply", async () => {
    mocks.sendCareerChatMessage.mockResolvedValue(response());
    const user = await openWidget();
    await user.click(screen.getByRole("button", { name: "Show my skill gaps" }));

    expect(await screen.findByText("Your highest-priority skill gap is Python.")).toBeInTheDocument();
    expect(mocks.sendCareerChatMessage).toHaveBeenCalledWith("Show my skill gaps", []);
    // quick prompts disappear once there's a conversation
    expect(screen.queryByRole("button", { name: "Show my skill gaps" })).not.toBeInTheDocument();
  });

  it("sends a manually typed message via the send button", async () => {
    mocks.sendCareerChatMessage.mockResolvedValue(response({ message: "Here is your career plan." }));
    const user = await openWidget();
    await user.type(screen.getByPlaceholderText(/ask about your career/i), "Give me my career plan");
    await user.click(screen.getByRole("button", { name: /send message/i }));

    expect(await screen.findByText("Here is your career plan.")).toBeInTheDocument();
    expect(screen.getByText("Give me my career plan")).toBeInTheDocument();
  });

  it("sends on Enter and inserts a newline on Shift+Enter", async () => {
    mocks.sendCareerChatMessage.mockResolvedValue(response());
    const user = await openWidget();
    const textarea = screen.getByPlaceholderText(/ask about your career/i);
    await user.type(textarea, "Show my skill gaps");
    await user.keyboard("{Enter}");
    expect(await screen.findByText("Show my skill gaps")).toBeInTheDocument();

    await user.type(textarea, "line1{Shift>}{Enter}{/Shift}line2");
    expect(textarea).toHaveValue("line1\nline2");
    expect(mocks.sendCareerChatMessage).toHaveBeenCalledTimes(1);
  });

  it("shows a loading indicator while waiting for the response", async () => {
    let resolvePromise: (value: CareerChatResponse) => void = () => {};
    mocks.sendCareerChatMessage.mockReturnValue(
      new Promise<CareerChatResponse>((resolve) => {
        resolvePromise = resolve;
      }),
    );
    const user = await openWidget();
    await user.click(screen.getByRole("button", { name: "Show my skill gaps" }));

    expect(await screen.findByText(/career ai is thinking/i)).toBeInTheDocument();
    resolvePromise(response());
    await waitFor(() => expect(screen.queryByText(/career ai is thinking/i)).not.toBeInTheDocument());
  });

  it("renders a SKILL card with a working navigation link", async () => {
    mocks.sendCareerChatMessage.mockResolvedValue(
      response({
        cards: [
          {
            type: "SKILL", skill_id: "s1", skill_name: "Python", current_level: "Beginner",
            target_level: "Intermediate", status: "MISSING", priority: "HIGH", importance: "CORE",
            reason: "Required for this role.",
          },
        ],
      }),
    );
    const user = await openWidget();
    await user.click(screen.getByRole("button", { name: "Show my skill gaps" }));

    expect(await screen.findByText("Python")).toBeInTheDocument();
    expect(screen.getByText(/Beginner/)).toBeInTheDocument();
    const link = screen.getByRole("button", { name: /view skill gap/i });
    expect(link).toHaveAttribute("href", "/student/skill-gap");
  });

  it("renders a COURSE card with an external open-course link", async () => {
    mocks.sendCareerChatMessage.mockResolvedValue(
      response({
        cards: [
          {
            type: "COURSE", candidate_id: "c1", title: "Python Basics", provider: "Catalog",
            url: "https://example.org/course", level: "Beginner", duration_text: "4h", skill_name: "Python",
            reason: null,
          },
        ],
      }),
    );
    const user = await openWidget();
    await user.click(screen.getByRole("button", { name: "What should I learn next?" }));

    expect(await screen.findByText("Python Basics")).toBeInTheDocument();
    const link = screen.getByRole("button", { name: /open course/i });
    expect(link).toHaveAttribute("href", "https://example.org/course");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("renders a YOUTUBE_VIDEO card with thumbnail, duration, views, and watch link", async () => {
    mocks.sendCareerChatMessage.mockResolvedValue(
      response({
        cards: [
          {
            type: "YOUTUBE_VIDEO", video_id: "dQw4w9WgXcQ", title: "Python Full Course",
            channel_title: "Example Academy", thumbnail_url: "https://i.ytimg.com/vi/x/hqdefault.jpg",
            watch_url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ", duration_text: "1h 20m",
            view_count: 125_000, published_at: "2026-01-01T00:00:00Z", skill_name: "Python", reason: null,
          },
        ],
      }),
    );
    const user = await openWidget();
    await user.click(screen.getByRole("button", { name: "Show YouTube learning videos" }));

    expect(await screen.findByText("Python Full Course")).toBeInTheDocument();
    expect(screen.getByText("Example Academy")).toBeInTheDocument();
    expect(screen.getByText("1h 20m")).toBeInTheDocument();
    expect(screen.getByText("125K")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Python Full Course" })).toHaveAttribute(
      "src",
      "https://i.ytimg.com/vi/x/hqdefault.jpg",
    );
    const link = screen.getByRole("button", { name: /watch on youtube/i });
    expect(link).toHaveAttribute("href", "https://www.youtube.com/watch?v=dQw4w9WgXcQ");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("renders an OPPORTUNITY card with match score and detail link", async () => {
    mocks.sendCareerChatMessage.mockResolvedValue(
      response({
        cards: [
          {
            type: "OPPORTUNITY", opportunity_id: "op1", opportunity_type: "INTERNSHIP",
            title: "Backend Intern", company: "Acme", match_score: 82, match_band: "STRONG",
            matched_count: 4, gap_count: 1, detail_url: "/student/internships/op1", reason: null,
          },
        ],
      }),
    );
    const user = await openWidget();
    await user.click(screen.getByRole("button", { name: "Recommend jobs for me" }));

    expect(await screen.findByText("Backend Intern")).toBeInTheDocument();
    expect(screen.getByText("Acme")).toBeInTheDocument();
    expect(screen.getByText(/82%/)).toBeInTheDocument();
    expect(screen.getByText(/Strong match/)).toBeInTheDocument();
    const link = screen.getByRole("button", { name: /view opportunity/i });
    expect(link).toHaveAttribute("href", "/student/internships/op1");
  });

  it("renders an ASSESSMENT card with a skill-gap CTA", async () => {
    mocks.sendCareerChatMessage.mockResolvedValue(
      response({
        cards: [
          {
            type: "ASSESSMENT", skill_id: "s1", skill_name: "Python", action: "TAKE_ASSESSMENT",
            note: "Take the Python assessment to verify this skill.", cta_url: "/student/skill-gap",
          },
        ],
      }),
    );
    const user = await openWidget();
    await user.type(screen.getByPlaceholderText(/ask about your career/i), "Which assessment should I take?");
    await user.keyboard("{Enter}");

    expect(await screen.findByText("Take the Python assessment to verify this skill.")).toBeInTheDocument();
    const link = screen.getByRole("button", { name: /go to skill gap/i });
    expect(link).toHaveAttribute("href", "/student/skill-gap");
  });

  it("renders nothing extra when the response has no cards (empty recommendations)", async () => {
    mocks.sendCareerChatMessage.mockResolvedValue(
      response({ message: "No current opportunity recommendations are available yet.", cards: [] }),
    );
    const user = await openWidget();
    await user.click(screen.getByRole("button", { name: "Recommend jobs for me" }));

    expect(await screen.findByText("No current opportunity recommendations are available yet.")).toBeInTheDocument();
  });

  it("shows an error bubble with a retry option on failure, and retry resends the same message", async () => {
    mocks.sendCareerChatMessage.mockRejectedValueOnce(new ApiError(500, "The server had a problem."));
    mocks.sendCareerChatMessage.mockResolvedValueOnce(response({ message: "Recovered." }));
    const user = await openWidget();
    await user.click(screen.getByRole("button", { name: "Show my skill gaps" }));

    expect(await screen.findByText("The server had a problem.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /retry/i }));

    expect(await screen.findByText("Recovered.")).toBeInTheDocument();
    expect(mocks.sendCareerChatMessage).toHaveBeenCalledTimes(2);
    // The retry resends the same user text; history now also includes
    // the error bubble that was added to the conversation in between.
    expect(mocks.sendCareerChatMessage).toHaveBeenNthCalledWith(2, "Show my skill gaps", [
      { role: "user", content: "Show my skill gaps" },
      { role: "assistant", content: "The server had a problem." },
    ]);
  });

  it("shows a generic error message for a non-ApiError failure", async () => {
    mocks.sendCareerChatMessage.mockRejectedValue(new Error("boom"));
    const user = await openWidget();
    await user.click(screen.getByRole("button", { name: "Show my skill gaps" }));

    expect(await screen.findByText("Something went wrong. Please try again.")).toBeInTheDocument();
  });
});
