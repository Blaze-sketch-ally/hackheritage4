import { AuthShell } from "@/components/auth/auth-shell";
import { RegisterForm } from "@/components/auth/register-form";

export default function RegisterPage() {
  return (
    <AuthShell title="Create your account" description="Join the Academia-Industry Collaboration Portal">
      <RegisterForm />
    </AuthShell>
  );
}
