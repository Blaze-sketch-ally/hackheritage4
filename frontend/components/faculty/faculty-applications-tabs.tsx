"use client";

import { FacultyApplicationsView } from "@/components/faculty/faculty-applications-view";
import { FacultyEoiView } from "@/components/faculty/faculty-eoi-view";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

/** Separates two structurally different things that must never be
 * conflated (see the approved F3.4 architecture):
 * - "My EOIs": Faculty-initiated expressions of interest against a
 *   public Industry/Institution Faculty opportunity listing.
 * - "Collaboration Requests": Industry-initiated proposals addressed
 *   directly at this Faculty member (industry_collaborations) -- this
 *   is the same FacultyApplicationsView built in Phase F3.2, unchanged,
 *   just no longer mislabeled as "applications" on its own. */
export function FacultyApplicationsTabs() {
  return (
    <Tabs defaultValue="eois">
      <TabsList>
        <TabsTrigger value="eois">My EOIs</TabsTrigger>
        <TabsTrigger value="collaborations">Collaboration Requests</TabsTrigger>
      </TabsList>
      <TabsContent value="eois" className="pt-4">
        <FacultyEoiView />
      </TabsContent>
      <TabsContent value="collaborations" className="pt-4">
        <FacultyApplicationsView />
      </TabsContent>
    </Tabs>
  );
}
