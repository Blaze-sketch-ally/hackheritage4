/**
 * Faculty <-> Student mentorship (Phase F4.2). Mirrors
 * backend/app/schemas/faculty_student_mentorship.py exactly -- no
 * invented fields. Deliberately distinct from faculty-engagement.ts
 * (Industry/Institution <-> Faculty) -- a different relationship with
 * different participants and a different lifecycle.
 */

export const MENTORSHIP_STATUSES = [
  "REQUESTED",
  "ACCEPTED",
  "ACTIVE",
  "DECLINED",
  "WITHDRAWN",
  "COMPLETED",
  "ENDED",
] as const;

export type MentorshipStatus = (typeof MENTORSHIP_STATUSES)[number];

export const MENTORSHIP_STATUS_LABELS: Record<MentorshipStatus, string> = {
  REQUESTED: "Requested",
  ACCEPTED: "Accepted",
  ACTIVE: "Active",
  DECLINED: "Declined",
  WITHDRAWN: "Withdrawn",
  COMPLETED: "Completed",
  ENDED: "Ended",
};

export interface FacultyStudentMentorship {
  id: string;
  faculty_id: string;
  student_id: string;
  requested_by: string;
  status: MentorshipStatus;
  focus_area: string | null;
  start_date: string | null;
  end_date: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface FacultyStudentMentorshipListResponse {
  mentorships: FacultyStudentMentorship[];
}

// ---- The authorized mentee data bundle -- ACTIVE mentorships only ----

export interface MenteeAcademicProfile {
  institution_name: string | null;
  department: string | null;
  degree: string | null;
  graduation_year: number | null;
  cgpa: number | null;
  percentage: number | null;
  career_goals: string | null;
  preferred_roles: string[];
  interests: string[];
}

export interface MenteeSkill {
  skill_id: string;
  proficiency_level: string;
  proficiency_score: number | null;
  is_verified: boolean;
}

export interface MenteeAssessmentAttempt {
  id: string;
  assessment_id: string;
  status: string;
  score: number | null;
  total_marks: number | null;
  percentage: number | null;
  submitted_at: string | null;
}

export interface MenteeProject {
  id: string;
  student_id: string;
  title: string;
  description: string;
  technologies: string[];
  project_url: string | null;
  github_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface MenteeCertification {
  id: string;
  student_id: string;
  name: string;
  issuer: string;
  issue_date: string | null;
  credential_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface MenteeProfileBundle {
  mentorship_id: string;
  student_id: string;
  full_name: string | null;
  email: string | null;
  username: string | null;
  academic_profile: MenteeAcademicProfile | null;
  skills: MenteeSkill[];
  assessment_attempts: MenteeAssessmentAttempt[];
  projects: MenteeProject[];
  certifications: MenteeCertification[];
}

// ---- Private mentor notes -- never exposed to the Student ----

export interface MentorshipNote {
  id: string;
  mentorship_id: string;
  faculty_id: string;
  note: string;
  created_at: string | null;
  updated_at: string | null;
}
