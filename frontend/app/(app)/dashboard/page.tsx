import { LayoutDashboard } from "lucide-react";
import type { Metadata } from "next";

import { SignedInAs } from "@/components/auth/signed-in-as";
import { EmptyState } from "@/components/states/empty-state";

export const metadata: Metadata = { title: "Dashboard" };

// Placeholder until the real dashboard (Sprint 6): who is signed in, and what will appear here.
export default function DashboardPage() {
  return (
    <>
      <section className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <SignedInAs />
      </section>
      <EmptyState
        icon={LayoutDashboard}
        title="Nothing to show yet"
        description="Applications, environments and deployments will show up here."
      />
    </>
  );
}
