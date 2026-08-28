export const APP_NAME = "AIC Portal";

export const USER_ROLES = {
  STUDENT: "STUDENT",
  FACULTY: "FACULTY",
  INDUSTRY: "INDUSTRY",
  INSTITUTION: "INSTITUTION",
  ADMIN: "ADMIN",
} as const;

export type UserRole = (typeof USER_ROLES)[keyof typeof USER_ROLES];
