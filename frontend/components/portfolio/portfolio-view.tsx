import { CertificationList } from "@/components/portfolio/certification-list";
import { ProjectList } from "@/components/portfolio/project-list";

/** The single portfolio implementation, rendered from three routes
 * (/student/portfolio shows both sections; /student/projects and
 * /student/certifications each lock to one section) -- never a
 * per-route duplicate, same `section`-lock pattern Phase 1M's
 * OpportunityListView already established with `lockedType`. */
export function PortfolioView({ section = "all" }: { section?: "all" | "projects" | "certifications" }) {
  return (
    <div className="space-y-8">
      {(section === "all" || section === "projects") && (
        <section className="space-y-3">
          <div>
            <h2 className="text-lg font-semibold">Projects</h2>
            <p className="text-sm text-muted-foreground">Work you&apos;ve built, with links a reviewer can follow.</p>
          </div>
          <ProjectList />
        </section>
      )}

      {(section === "all" || section === "certifications") && (
        <section className="space-y-3">
          <div>
            <h2 className="text-lg font-semibold">Certifications</h2>
            <p className="text-sm text-muted-foreground">Credentials that strengthen your professional profile.</p>
          </div>
          <CertificationList />
        </section>
      )}
    </div>
  );
}
