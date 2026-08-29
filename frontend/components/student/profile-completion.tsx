import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

export function ProfileCompletion({ percent }: { percent: number }) {
  return (
    <Card>
      <CardContent className="space-y-3">
        <div className="flex items-center justify-between">
          <p className="text-sm font-medium">Profile Completion</p>
          <span className="text-sm font-semibold text-indigo-600 dark:text-indigo-400">{percent}%</span>
        </div>
        <Progress value={percent} />
        <p className="text-xs text-muted-foreground">
          Complete your profile to improve your opportunity matches.
        </p>
        <Button
          size="sm"
          className="w-full"
          render={<Link href="/student/profile" />}
          nativeButton={false}
        >
          Complete Profile
        </Button>
      </CardContent>
    </Card>
  );
}
