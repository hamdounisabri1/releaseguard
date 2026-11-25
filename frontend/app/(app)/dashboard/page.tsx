import type { Metadata } from "next";

export const metadata: Metadata = { title: "Dashboard" };

// Placeholder: SCRUM-28 adds the auth guard, Sprint 6 the real dashboard content.
export default function DashboardPage() {
  return (
    <section className="flex flex-col gap-1">
      <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
      <p className="text-sm text-muted-foreground">
        Applications, environments and deployments will show up here.
      </p>
    </section>
  );
}
