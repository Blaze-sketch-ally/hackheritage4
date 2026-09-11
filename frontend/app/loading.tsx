import { Sparkles } from "lucide-react";

export default function Loading() {
  return (
    <div className="flex min-h-[60vh] w-full flex-col items-center justify-center gap-3">
      <div className="relative flex size-12 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-md shadow-indigo-600/30 animate-pulse">
        <span className="font-bold text-lg">A</span>
        <Sparkles className="absolute -top-1 -right-1 size-3.5 text-amber-300 animate-bounce" />
      </div>
      <p className="font-mono text-xs text-muted-foreground animate-pulse">
        Loading workspace...
      </p>
    </div>
  );
}
