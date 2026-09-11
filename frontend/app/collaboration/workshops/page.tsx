import { FeatureRoadmapStub } from "@/components/common/feature-roadmap-stub";

export default function CollaborationWorkshopsPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <FeatureRoadmapStub
        title="Technical Workshops & Bootcamps"
        badge="Roadmap Phase 4"
        description="Intensive, hands-on masterclasses hosted by industry practitioners and distinguished faculty on cutting-edge technologies and emerging industry standards."
        highlights={[
          "Interactive live coding labs and virtual sandbox environments",
          "Attendance and participation tracking via institutional SSO",
          "Hands-on capstone evaluations with immediate feedback",
          "Digitally verified workshop certificates issued to student profiles",
        ]}
        backHref="/collaboration"
        backLabel="Back to Collaboration Hub"
        estimatedRelease="Q4 2026"
        iconName="sparkles"
      />
    </div>
  );
}
