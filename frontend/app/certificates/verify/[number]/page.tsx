import { CertificateVerificationView } from "@/components/public/certificate-verification-view";

/** Public certificate verification -- no auth, unlike every other page in
 * this app. Anyone with a certificate number (e.g. from a printed / PDF
 * certificate) can confirm it here. */
export default async function VerifyCertificatePage({
  params,
}: {
  params: Promise<{ number: string }>;
}) {
  const { number } = await params;

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-4 p-6">
      <div className="text-center">
        <h1 className="text-xl font-semibold">Certificate Verification</h1>
        <p className="text-sm text-muted-foreground">AIC Portal — Internship Certificates</p>
      </div>
      <CertificateVerificationView certificateNumber={decodeURIComponent(number)} />
    </div>
  );
}
