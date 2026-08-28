import { type NextRequest } from "next/server";
import { updateSession } from "@/lib/supabase/middleware";

// Session refresh only for now. Role-based authorization / redirects are
// added when the Authentication feature is implemented.
export async function middleware(request: NextRequest) {
  return updateSession(request);
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
