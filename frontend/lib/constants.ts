export const APP_NAME = "AIC Portal";

export const USER_ROLES = {
  STUDENT: "STUDENT",
  FACULTY: "FACULTY",
  INDUSTRY: "INDUSTRY",
  INSTITUTION: "INSTITUTION",
  ADMIN: "ADMIN",
} as const;

export type UserRole = (typeof USER_ROLES)[keyof typeof USER_ROLES];

// Roles a user may pick for themselves during onboarding. ADMIN is
// deliberately excluded — it's never offered in public UI and is assigned
// out-of-band (not through this app yet).
export const PUBLIC_ROLES = [
  USER_ROLES.STUDENT,
  USER_ROLES.FACULTY,
  USER_ROLES.INDUSTRY,
  USER_ROLES.INSTITUTION,
] as const;

export type PublicRole = (typeof PUBLIC_ROLES)[number];

export const ROLE_LABELS: Record<PublicRole, { title: string; description: string }> = {
  STUDENT: {
    title: "Student",
    description: "Find internships, projects, and industry opportunities.",
  },
  FACULTY: {
    title: "Faculty / Academician",
    description: "Connect students, research, and industry.",
  },
  INDUSTRY: {
    title: "Industry",
    description: "Collaborate with institutions and discover talent.",
  },
  INSTITUTION: {
    title: "Institution",
    description: "Manage academia-industry collaboration for your institution.",
  },
};

// Simple, inclusive option set for the student_profiles.gender field.
// Deliberately not an exhaustive taxonomy — gender is optional and free
// enough to cover the common cases without over-collecting.
export const GENDER_OPTIONS = ["Male", "Female", "Non-binary", "Prefer not to say"] as const;

export type Gender = (typeof GENDER_OPTIONS)[number];
