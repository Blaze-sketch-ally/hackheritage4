import { Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { MOCK_AI_RECOMMENDATIONS } from "@/lib/mock/student-dashboard";

export function AiRecommendations() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>AI Recommendations</CardTitle>
        <CardAction>
          <Button variant="ghost" size="sm" disabled title="AI recommendation engine isn't built yet">
            View All
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent className="space-y-3">
        {MOCK_AI_RECOMMENDATIONS.map((rec) => (
          <div key={rec.id} className="flex items-start gap-2.5 rounded-lg border border-border/60 p-3">
            <Sparkles className="mt-0.5 size-4 shrink-0 text-violet-600 dark:text-violet-400" aria-hidden="true" />
            <div className="space-y-0.5">
              <p className="text-sm font-medium">{rec.title}</p>
              <p className="text-xs text-muted-foreground">{rec.reason}</p>
            </div>
          </div>
        ))}
        <Button
          variant="secondary"
          size="sm"
          className="w-full"
          disabled
          title="AI Career Advisor isn't built yet"
        >
          Ask AI Career Advisor
        </Button>
      </CardContent>
    </Card>
  );
}
