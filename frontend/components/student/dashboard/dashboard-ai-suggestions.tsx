import Link from "next/link";
import { Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/**
 * Honest placeholder for AI career suggestions. The AI services
 * (backend/app/ai/*) are not implemented, so this shows a clear
 * coming-soon state and points the student at the real, deterministic
 * Skill Gap analysis they can use today — no fabricated AI tips.
 */
export function DashboardAiSuggestions() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Sparkles className="size-4 text-violet-600 dark:text-violet-400" aria-hidden="true" />
          AI Career Suggestions
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground">
          AI-powered suggestions are coming soon. In the meantime, your Skill Gap analysis gives you
          concrete, data-driven next steps toward a target role.
        </p>
        <Button
          variant="secondary"
          size="sm"
          className="w-full"
          render={<Link href="/student/skill-gap" />}
          nativeButton={false}
        >
          Open Skill Gap Analysis
        </Button>
      </CardContent>
    </Card>
  );
}
