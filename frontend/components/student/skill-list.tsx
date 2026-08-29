import { Progress, ProgressLabel, ProgressValue } from "@/components/ui/progress";
import type { SkillProficiency } from "@/lib/mock/student-dashboard";

export function SkillList({ skills }: { skills: SkillProficiency[] }) {
  return (
    <div className="space-y-3">
      {skills.map((skill) => (
        <Progress key={skill.name} value={skill.level} className="gap-1.5">
          <div className="flex w-full items-center justify-between">
            <ProgressLabel>{skill.name}</ProgressLabel>
            <ProgressValue />
          </div>
        </Progress>
      ))}
    </div>
  );
}
