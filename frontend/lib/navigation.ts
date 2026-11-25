import {
  CheckCircle2,
  LayoutDashboard,
  Layers,
  type LucideIcon,
  Package,
  Settings,
} from "lucide-react";

export type NavItem = {
  title: string;
  href: string;
  icon: LucideIcon;
};

/** Main sidebar navigation (routes from guide §5.6). The pages land sprint by sprint. */
export const mainNav: readonly NavItem[] = [
  { title: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { title: "Applications", href: "/applications", icon: Package },
  { title: "Approvals", href: "/approvals", icon: CheckCircle2 },
  { title: "Environments", href: "/environments", icon: Layers },
  { title: "Settings", href: "/settings", icon: Settings },
];

/** True when `pathname` is `href` itself or a page below it. */
export function isActivePath(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function findNavItem(pathname: string): NavItem | undefined {
  return mainNav.find((item) => isActivePath(pathname, item.href));
}
