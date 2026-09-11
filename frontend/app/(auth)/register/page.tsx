import { AuthShell } from "@/components/auth/auth-shell";
import { RegisterForm } from "@/components/auth/register-form";

export default function RegisterPage() {
  return (
    <AuthShell
      title="Create Account"
      description="Join the national trust network connecting verified students, faculty, and recruiters"
    >
      <RegisterForm />
    </AuthShell>
  );
}
