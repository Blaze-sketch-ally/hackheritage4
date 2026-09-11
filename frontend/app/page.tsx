import { redirect } from "next/navigation";

// `/` had no real landing page (just a static placeholder) -- the actual
// entry point for both new and returning visitors is the login flow.
// /login itself already handles an already-authenticated visitor (redirects
// to their role dashboard, see app/(auth)/login/page.tsx), so this can
// unconditionally redirect here rather than duplicate that auth check.
// A plain `redirect()` call with no dynamic data dependency lets Next.js
// serve this as a server-side redirect without a client-side navigation.
export default function HomePage() {
  redirect("/login");
}
