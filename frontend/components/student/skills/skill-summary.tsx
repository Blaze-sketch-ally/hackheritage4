import { Card, CardContent } from "@/components/ui/card";

export function SkillSummary({
  total,
  verified,
  advancedPlus,
}: {
  total: number;
  verified: number;
  advancedPlus: number;
}) {
  const items = [
    { label: "Total Skills", value: total },
    { label: "Verified Skills", value: verified },
    { label: "Advanced+ Skills", value: advancedPlus },
  ];

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      {items.map((item) => (
        <Card key={item.label}>
          <CardContent className="space-y-1">
            <p className="text-sm text-muted-foreground">{item.label}</p>
            <p className="text-2xl font-semibold tracking-tight">{item.value}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
