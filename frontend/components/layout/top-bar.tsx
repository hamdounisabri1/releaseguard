"use client";

import { usePathname } from "next/navigation";
import { Suspense } from "react";

import { AccountMenu } from "@/components/auth/account-menu";
import { Separator } from "@/components/ui/separator";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { findNavItem } from "@/lib/navigation";

const APP_TITLE = "ReleaseGuard";

/** The current section's name; request-time data, so it streams in after the static shell. */
function SectionTitle() {
  return <>{findNavItem(usePathname())?.title ?? APP_TITLE}</>;
}

export function TopBar() {
  return (
    <header className="sticky top-0 z-10 flex h-14 shrink-0 items-center gap-2 border-b bg-background px-4">
      <SidebarTrigger className="-ml-1 size-9" />
      <Separator
        orientation="vertical"
        className="mr-1 data-vertical:h-5 data-vertical:self-center"
      />
      <p className="truncate text-sm font-medium">
        <Suspense fallback={APP_TITLE}>
          <SectionTitle />
        </Suspense>
      </p>
      <div className="ml-auto flex items-center gap-2">
        <AccountMenu />
      </div>
    </header>
  );
}
