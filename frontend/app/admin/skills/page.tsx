import { FeatureRoadmapStub } from "@/components/common/feature-roadmap-stub";

export default function AdminSkillsPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <FeatureRoadmapStub
        title="Skill Taxonomy & Ontology Engine"
        role="Admin"
        badge="Admin Roadmap"
        description="Manage the central SkillBridge skill ontology, industry competency standards, and automated course-to-skill mapping dictionaries."
        highlights={[
          "Hierarchical skill taxonomy with semantic tag relationship graphs",
          "Market demand trend tracking calibrated against live job listings",
          "Automated curriculum-to-competency alignment algorithm",
          "Standardized assessment rubric and question pool categorization",
        ]}
        backHref="/admin"
        backLabel="Back to Admin Console"
        estimatedRelease="Q4 2026"
        iconName="lightbulb"
      />
    </div>
  );
}
