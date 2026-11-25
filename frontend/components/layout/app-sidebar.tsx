"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ShieldCheck } from "lucide-react";

import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  useSidebar,
} from "@/components/ui/sidebar";
import { isActivePath, mainNav } from "@/lib/navigation";

export function AppSidebar() {
  const pathname = usePathname();
  const { isMobile, setOpenMobile } = useSidebar();
  // On mobile the sidebar is a sheet over the page: close it once a link is followed.
  const closeOnMobile = () => {
    if (isMobile) setOpenMobile(false);
  };

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild tooltip="ReleaseGuard">
              <Link href="/dashboard" onClick={closeOnMobile}>
                <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-sidebar-primary text-sidebar-primary-foreground">
                  <ShieldCheck aria-hidden="true" />
                </span>
                <span className="font-semibold tracking-tight">ReleaseGuard</span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <nav aria-label="Main">
              <SidebarMenu>
                {mainNav.map((item) => {
                  const active = isActivePath(pathname, item.href);
                  return (
                    <SidebarMenuItem key={item.href}>
                      <SidebarMenuButton asChild isActive={active} tooltip={item.title}>
                        <Link
                          href={item.href}
                          aria-current={active ? "page" : undefined}
                          onClick={closeOnMobile}
                        >
                          <item.icon aria-hidden="true" />
                          <span>{item.title}</span>
                        </Link>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  );
                })}
              </SidebarMenu>
            </nav>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarRail />
    </Sidebar>
  );
}
