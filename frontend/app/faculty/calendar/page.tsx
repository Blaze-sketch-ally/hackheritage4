import { FeatureRoadmapStub } from "@/components/common/feature-roadmap-stub";

export default function FacultyCalendarPage() {
  return (
    <FeatureRoadmapStub
      title="Academic Schedule & Office Hours"
      role="Faculty"
      badge="Roadmap · Q4 2026"
      estimatedRelease="Q4 2026"
      iconName="calendar"
      description="Synchronize student mentorship appointments, assessment evaluation windows, live project milestones, and department faculty meetings."
      highlights={[
        "Two-way synchronization with Google Calendar and Microsoft Outlook",
        "Configurable office hour booking slots for advisees and research students",
        "Deadline reminders for capstone grading and question bank reviews",
        "Automated conflict detection across academic and advisory schedules",
      ]}
      backHref="/faculty/dashboard"
      backLabel="Back to Dashboard"
    />
  );
}
