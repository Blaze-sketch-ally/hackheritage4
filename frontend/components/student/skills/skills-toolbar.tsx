"use client";

import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Filters } from "@/components/common/filters";
import { SearchBar } from "@/components/common/search-bar";
import type { SkillCategory } from "@/lib/student/skills";

export function SkillsToolbar({
  search,
  onSearchChange,
  categoryId,
  onCategoryChange,
  categories,
  onAddClick,
}: {
  search: string;
  onSearchChange: (value: string) => void;
  categoryId: string;
  onCategoryChange: (value: string) => void;
  categories: SkillCategory[];
  onAddClick: () => void;
}) {
  const options = [
    { value: "all", label: "All Categories" },
    ...categories.map((category) => ({ value: category.id, label: category.name })),
  ];

  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
      <SearchBar
        value={search}
        onChange={onSearchChange}
        placeholder="Search your skills..."
        aria-label="Search your skills"
      />
      <Filters value={categoryId} onChange={onCategoryChange} options={options} aria-label="Filter by category" />
      <Button onClick={onAddClick} className="sm:w-auto">
        <Plus /> Add Skill
      </Button>
    </div>
  );
}
