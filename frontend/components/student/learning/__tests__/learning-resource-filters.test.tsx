import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import {
  EMPTY_LEARNING_FILTERS,
  LearningResourceFilters,
} from "@/components/student/learning/learning-resource-filters";

describe("LearningResourceFilters", () => {
  it("renders the search box and both server-side filter controls", () => {
    render(
      <LearningResourceFilters filters={EMPTY_LEARNING_FILTERS} onChange={vi.fn()} />,
    );
    expect(screen.getByLabelText("Search learning resources")).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: /filter by level/i })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: /filter by type/i })).toBeInTheDocument();
  });

  it("emits the new search text without touching the other filters", async () => {
    const onChange = vi.fn();
    render(<LearningResourceFilters filters={EMPTY_LEARNING_FILTERS} onChange={onChange} />);

    await userEvent.type(screen.getByLabelText("Search learning resources"), "d");

    expect(onChange).toHaveBeenLastCalledWith({
      ...EMPTY_LEARNING_FILTERS,
      search: "d",
    });
  });

  it("hides the Clear button when no filter is active and shows it when one is", () => {
    const { rerender } = render(
      <LearningResourceFilters filters={EMPTY_LEARNING_FILTERS} onChange={vi.fn()} />,
    );
    expect(screen.queryByRole("button", { name: /clear/i })).not.toBeInTheDocument();

    rerender(
      <LearningResourceFilters
        filters={{ ...EMPTY_LEARNING_FILTERS, difficulty: "Advanced" }}
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: /clear/i })).toBeInTheDocument();
  });

  it("Clear resets every filter back to the empty state", async () => {
    const onChange = vi.fn();
    render(
      <LearningResourceFilters
        filters={{ search: "python", difficulty: "Beginner", resourceType: "VIDEO" }}
        onChange={onChange}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: /clear/i }));
    expect(onChange).toHaveBeenCalledWith(EMPTY_LEARNING_FILTERS);
  });
});
