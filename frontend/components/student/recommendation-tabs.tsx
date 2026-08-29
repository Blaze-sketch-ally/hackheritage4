"use client";

import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { RecommendationCard } from "@/components/student/recommendation-card";
import { MOCK_RECOMMENDATIONS, type RecommendationCategory } from "@/lib/mock/student-dashboard";

const TABS: { value: RecommendationCategory; label: string }[] = [
  { value: "internships", label: "Internships" },
  { value: "jobs", label: "Jobs" },
  { value: "courses", label: "Courses" },
  { value: "projects", label: "Projects" },
];

export function RecommendationTabs() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Recommended For You</CardTitle>
        <CardDescription>Demo recommendations — the real matching engine isn&apos;t built yet.</CardDescription>
      </CardHeader>
      <Tabs defaultValue="internships" className="px-(--card-spacing)">
        <TabsList>
          {TABS.map((tab) => (
            <TabsTrigger key={tab.value} value={tab.value}>
              {tab.label}
            </TabsTrigger>
          ))}
        </TabsList>
        {TABS.map((tab) => (
          <TabsContent key={tab.value} value={tab.value} className="grid gap-3 pt-4 sm:grid-cols-2 xl:grid-cols-3">
            {MOCK_RECOMMENDATIONS[tab.value].map((item) => (
              <RecommendationCard key={item.id} item={item} />
            ))}
          </TabsContent>
        ))}
      </Tabs>
    </Card>
  );
}
