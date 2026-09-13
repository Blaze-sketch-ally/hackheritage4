// Mirrors backend/app/schemas/participation.py and
// database/migrations/062-066_participation_*.sql. ONE reusable domain
// for PROJECT/TRAINING/WORKSHOP, discriminated by `kind` -- never three
// duplicated type modules.

export const PARTICIPATION_KINDS = ["PROJECT", "TRAINING", "WORKSHOP"] as const;
export type ParticipationKind = (typeof PARTICIPATION_KINDS)[number];

export const PARTICIPATION_KIND_LABELS: Record<ParticipationKind, string> = {
  PROJECT: "Project",
  TRAINING: "Training",
  WORKSHOP: "Workshop",
};

export type ProgramStatus = "DRAFT" | "PUBLISHED" | "ARCHIVED";
export type ResourceType = "VIDEO" | "DOCUMENT" | "LINK" | "REFERENCE" | "OTHER";
export const RESOURCE_TYPES: ResourceType[] = ["VIDEO", "DOCUMENT", "LINK", "REFERENCE", "OTHER"];

export type WorkspaceStatus = "ACTIVE" | "COMPLETED";
export type SubmissionStatus = "SUBMITTED" | "UNDER_REVIEW" | "REVIEWED";
export const SUBMISSION_STATUS_LABELS: Record<SubmissionStatus, string> = {
  SUBMITTED: "Submitted",
  UNDER_REVIEW: "Under Review",
  REVIEWED: "Reviewed",
};
export type ReviewStatus = "REVIEWED" | "NEEDS_REVISION" | "ACCEPTED";
export const REVIEW_STATUSES: ReviewStatus[] = ["ACCEPTED", "NEEDS_REVISION", "REVIEWED"];
export const REVIEW_STATUS_LABELS: Record<ReviewStatus, string> = {
  ACCEPTED: "Accepted",
  NEEDS_REVISION: "Needs revision",
  REVIEWED: "Reviewed",
};

export type FeedbackType = "GENERAL" | "PROGRESS" | "STRENGTH" | "IMPROVEMENT" | "FINAL_NOTE";
export const FEEDBACK_TYPES: FeedbackType[] = ["GENERAL", "PROGRESS", "STRENGTH", "IMPROVEMENT", "FINAL_NOTE"];
export const FEEDBACK_TYPE_LABELS: Record<FeedbackType, string> = {
  GENERAL: "General",
  PROGRESS: "Progress",
  STRENGTH: "Strength",
  IMPROVEMENT: "Improvement",
  FINAL_NOTE: "Final note",
};

export type RecommendedLevel = "Beginner" | "Intermediate" | "Advanced" | "Expert";
export const RECOMMENDED_LEVELS: RecommendedLevel[] = ["Beginner", "Intermediate", "Advanced", "Expert"];

export type RecommendationPriority = "LOW" | "MEDIUM" | "HIGH";
export const RECOMMENDATION_PRIORITIES: RecommendationPriority[] = ["LOW", "MEDIUM", "HIGH"];

export type EvaluationStatus = "DRAFT" | "FINALIZED";

export interface OpportunityRef {
  id: string;
  title: string;
  status: string;
}

export interface ProgramResponse {
  id: string;
  kind: ParticipationKind;
  project_id: string | null;
  training_id: string | null;
  workshop_id: string | null;
  title: string;
  description: string | null;
  status: ProgramStatus;
  published_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  opportunity: OpportunityRef | null;
}

export interface ModuleResponse {
  id: string;
  program_id: string;
  title: string;
  description: string | null;
  sequence_order: number;
  is_published: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface ResourceResponse {
  id: string;
  program_id: string;
  module_id: string | null;
  title: string;
  description: string | null;
  resource_type: ResourceType;
  resource_url: string | null;
  sequence_order: number;
  is_published: boolean;
  created_at: string | null;
}

export interface AssignmentResponse {
  id: string;
  program_id: string;
  module_id: string | null;
  title: string;
  description: string | null;
  instructions: string | null;
  due_at: string | null;
  max_score: number | null;
  is_required: boolean;
  is_published: boolean;
  sequence_order: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface ProgressSummary {
  completed_required: number;
  published_required: number;
  percent: number;
}

export interface WorkspaceResponse {
  id: string;
  kind: ParticipationKind;
  student_id: string;
  student_name: string | null;
  industry_id: string;
  project_id: string | null;
  training_id: string | null;
  workshop_id: string | null;
  project_application_id: string | null;
  training_application_id: string | null;
  workshop_application_id: string | null;
  workspace_status: WorkspaceStatus;
  started_at: string | null;
  completed_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  opportunity: OpportunityRef | null;
  program_id: string | null;
  progress: ProgressSummary | null;
}

export interface ReviewResponse {
  id: string;
  submission_id: string;
  reviewer_id: string;
  score: number | null;
  feedback: string | null;
  status: ReviewStatus;
  reviewed_at: string | null;
  created_at: string | null;
}

export interface SubmissionResponse {
  id: string;
  workspace_id: string;
  assignment_id: string;
  assignment_title: string | null;
  attempt_number: number;
  submission_text: string | null;
  submission_url: string | null;
  submitted_at: string | null;
  status: SubmissionStatus;
  created_at: string | null;
  latest_review: ReviewResponse | null;
}

export interface FeedbackResponse {
  id: string;
  workspace_id: string;
  industry_id: string;
  feedback_type: FeedbackType;
  title: string | null;
  feedback: string;
  created_at: string | null;
}

export interface SkillRecommendationResponse {
  id: string;
  workspace_id: string;
  skill_id: string;
  skill_name: string | null;
  recommended_level: RecommendedLevel | null;
  reason: string;
  priority: RecommendationPriority;
  created_by: string;
  created_at: string | null;
}

export interface CriterionResponse {
  id: string;
  program_id: string;
  name: string;
  description: string | null;
  max_score: number;
  weight: number;
  sequence_order: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface EvaluationScoreResponse {
  id: string;
  evaluation_id: string;
  criterion_id: string;
  criterion_name: string | null;
  max_score: number | null;
  score: number;
  feedback: string | null;
}

export interface EvaluationResponse {
  id: string;
  workspace_id: string;
  evaluator_id: string;
  status: EvaluationStatus;
  overall_score: number | null;
  overall_feedback: string | null;
  evaluated_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  scores: EvaluationScoreResponse[];
}

export interface CompletionResponse {
  id: string;
  workspace_id: string;
  final_evaluation_id: string | null;
  completed_at: string | null;
  completion_status: "COMPLETED";
  final_score: number | null;
  created_at: string | null;
}

/** The three FK field names, keyed by kind -- used to build request
 * bodies generically instead of branching three times at every call
 * site. */
export const OPPORTUNITY_FK: Record<ParticipationKind, "project_id" | "training_id" | "workshop_id"> = {
  PROJECT: "project_id",
  TRAINING: "training_id",
  WORKSHOP: "workshop_id",
};

export const APPLICATION_FK: Record<
  ParticipationKind,
  "project_application_id" | "training_application_id" | "workshop_application_id"
> = {
  PROJECT: "project_application_id",
  TRAINING: "training_application_id",
  WORKSHOP: "workshop_application_id",
};

/** Route base path per kind, for cross-linking back to the opportunity's
 * own existing pages (never invented -- these match the routes already
 * shipped for Project/Training/Workshop). */
export const INDUSTRY_OPPORTUNITY_BASE_PATH: Record<ParticipationKind, string> = {
  PROJECT: "/industry/projects",
  TRAINING: "/industry/training",
  WORKSHOP: "/industry/workshops",
};

export const STUDENT_OPPORTUNITY_BASE_PATH: Record<ParticipationKind, string> = {
  PROJECT: "/student/industry-projects",
  TRAINING: "/student/trainings",
  WORKSHOP: "/student/workshops",
};
