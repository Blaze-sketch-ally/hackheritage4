import { Loader2 } from "lucide-react";

// Root-level loading fallback, shown by Next.js while a route segment's
// Server Component data (e.g. the auth/role check in each role's
// layout.tsx) is still resolving. Without this, navigation to a new
// route segment left the previous page frozen on screen with no
// indication anything was happening.
export default function RootLoading() {
  return (
    <div className="flex flex-1 items-center justify-center p-8">
      <Loader2 className="size-6 animate-spin text-muted-foreground" aria-label="Loading" />
    </div>
  );
}
