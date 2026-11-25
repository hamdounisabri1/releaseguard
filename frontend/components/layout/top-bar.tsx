"use client";

import { usePathname } from "next/navigation";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Separator } from "@/components/ui/separator";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { findNavItem } from "@/lib/navigation";

export function TopBar() {
  const pathname = usePathname();
  const section = findNavItem(pathname);

  return (
    <header className="sticky top-0 z-10 flex h-14 shrink-0 items-center gap-2 border-b bg-background px-4">
      <SidebarTrigger className="-ml-1 size-9" />
      <Separator
        orientation="vertical"
        className="mr-1 data-vertical:h-5 data-vertical:self-center"
      />
      <p className="truncate text-sm font-medium">{section?.title ?? "ReleaseGuard"}</p>
      <div className="ml-auto flex items-center gap-2">
        {/* The signed-in user and workspace arrive with SCRUM-28 (login + auth guard). */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="size-9 rounded-full"
              aria-label="Account menu"
            >
              <Avatar className="size-8">
                <AvatarFallback>RG</AvatarFallback>
              </Avatar>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48">
            <DropdownMenuLabel>Account</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem disabled>Sign out</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
