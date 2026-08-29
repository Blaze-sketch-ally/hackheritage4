"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { MailCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { FormError } from "@/components/auth/form-error";
import { FormSuccess } from "@/components/auth/form-success";
import { createClient } from "@/lib/supabase/client";
import { getAuthErrorMessage, resendSignupVerificationEmail } from "@/lib/auth";

const RESEND_COOLDOWN_SECONDS = 60;

export function VerifyEmailPanel() {
  const searchParams = useSearchParams();
  const email = searchParams.get("email");

  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [cooldown, setCooldown] = useState(0);

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setInterval(() => setCooldown((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(timer);
  }, [cooldown]);

  async function handleResend() {
    if (!email || cooldown > 0 || sending) return;
    setError(null);
    setSuccess(null);
    setSending(true);

    try {
      const { error: resendError } = await resendSignupVerificationEmail(createClient(), email);
      setSending(false);

      if (resendError) {
        setError(getAuthErrorMessage(resendError));
        return;
      }

      setCooldown(RESEND_COOLDOWN_SECONDS);
      setSuccess("Verification email sent. Please check your inbox.");
    } catch (err) {
      console.error("Resend verification email failed:", err);
      setSending(false);
      setError(getAuthErrorMessage(err));
    }
  }

  return (
    <div className="flex flex-col items-center gap-4 text-center">
      <MailCheck className="size-10 text-primary" aria-hidden="true" />
      <p className="text-sm text-muted-foreground">
        {email ? (
          <>
            We sent a verification link to <span className="font-medium text-foreground">{email}</span>.
            Click the link to activate your account.
          </>
        ) : (
          "Check your inbox for a verification link to activate your account."
        )}
      </p>

      <FormError message={error} />
      <FormSuccess message={success} />

      {email ? (
        <Button
          type="button"
          variant="outline"
          className="h-10 w-full"
          onClick={handleResend}
          disabled={sending || cooldown > 0}
        >
          {sending ? "Sending..." : cooldown > 0 ? `Resend email in ${cooldown}s` : "Resend email"}
        </Button>
      ) : null}
    </div>
  );
}
