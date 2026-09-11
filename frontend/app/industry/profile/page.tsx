import { FeatureRoadmapStub } from "@/components/common/feature-roadmap-stub";

export default function IndustryProfilePage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <FeatureRoadmapStub
        title="Corporate Employer Profile & Branding"
        role="Industry"
        badge="Industry Roadmap"
        description="Showcase your company culture, technology stack, employee benefits, office locations, and video testimonials to attract prospective candidates."
        highlights={[
          "Rich employer branding hub with custom media and tech stack tags",
          "Verified corporate domain, tax ID, and recruiter seat management",
          "Public company storefront visible across all student opportunity searches",
          "Candidate brand impression and job view engagement analytics",
        ]}
        backHref="/industry/dashboard"
        backLabel="Back to Industry Dashboard"
        estimatedRelease="Q4 2026"
        iconName="building"
      />
    </div>
  );
}
