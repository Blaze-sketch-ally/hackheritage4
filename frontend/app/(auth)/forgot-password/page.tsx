import { AuthShell } from "@/components/auth/auth-shell";
import { ForgotPasswordForm } from "@/components/auth/forgot-password-form";

export default function ForgotPasswordPage() {
  return (
    <AuthShell title="Reset your password" description="We'll help you get back into your account">
      <ForgotPasswordForm />
    </AuthShell>
  );
}
