"use client";

import { FacultyOpportunityManagementView } from "@/components/shared/faculty-opportunity-management-view";
import {
  closeFacultyOpportunity,
  createFacultyOpportunity,
  listFacultyOpportunityEois,
  listOwnFacultyOpportunities,
  publishFacultyOpportunity,
  reviewFacultyOpportunityEoi,
  updateFacultyOpportunity,
} from "@/lib/industry/faculty-opportunities";

export function IndustryFacultyOpportunitiesView() {
  return (
    <FacultyOpportunityManagementView
      api={{
        listOpportunities: listOwnFacultyOpportunities,
        createOpportunity: createFacultyOpportunity,
        updateOpportunity: updateFacultyOpportunity,
        publishOpportunity: publishFacultyOpportunity,
        closeOpportunity: closeFacultyOpportunity,
        listEois: listFacultyOpportunityEois,
        reviewEoi: reviewFacultyOpportunityEoi,
      }}
    />
  );
}
