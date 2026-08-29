const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const USERNAME_REGEX = /^[a-zA-Z0-9_.-]{3,30}$/;

export function isValidEmail(value: string): boolean {
  return EMAIL_REGEX.test(value.trim());
}

export function isValidUsername(value: string): boolean {
  return USERNAME_REGEX.test(value.trim());
}

export function isValidFullName(value: string): boolean {
  return value.trim().length >= 2;
}

/** Accepts either an email address or a username as a login identifier. */
export function isValidIdentifier(value: string): boolean {
  const trimmed = value.trim();
  if (!trimmed) return false;
  return trimmed.includes("@") ? isValidEmail(trimmed) : isValidUsername(trimmed);
}

/** Loose http(s) URL check for optional profile links. */
export function isValidUrl(value: string): boolean {
  try {
    const url = new URL(value.trim());
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

// Mirrors student_profiles.phone_format exactly (database/migrations/
// 012_student_profiles.sql) so client-side validation never accepts
// something the database would reject.
const PHONE_REGEX = /^[0-9+\-\s()]{7,20}$/;

export function isValidPhone(value: string): boolean {
  return PHONE_REGEX.test(value.trim());
}

export interface PasswordRequirements {
  minLength: boolean;
  hasUpper: boolean;
  hasLower: boolean;
  hasNumber: boolean;
}

export function getPasswordRequirements(password: string): PasswordRequirements {
  return {
    minLength: password.length >= 8,
    hasUpper: /[A-Z]/.test(password),
    hasLower: /[a-z]/.test(password),
    hasNumber: /[0-9]/.test(password),
  };
}

export function isPasswordValid(password: string): boolean {
  const req = getPasswordRequirements(password);
  return req.minLength && req.hasUpper && req.hasLower && req.hasNumber;
}

/** 0 (empty) to 4 (meets every requirement). */
export function getPasswordStrength(password: string): number {
  if (!password) return 0;
  const req = getPasswordRequirements(password);
  return Object.values(req).filter(Boolean).length;
}
