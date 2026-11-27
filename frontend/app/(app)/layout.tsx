import { AuthGuard } from "@/components/auth/auth-guard";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { TopBar } from "@/components/layout/top-bar";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";

/**
 * App shell for signed-in pages: sidebar, top bar and the page content. The shell itself is static;
 * `AuthGuard` shows the page only once `/auth/me` confirms the session (`proxy.ts` has already sent
 * visitors without a session cookie to the login page).
 */
export default function AppLayout({ children }: LayoutProps<"/">) {
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <TopBar />
        <div className="flex flex-1 flex-col gap-6 p-4 md:p-6">
          <AuthGuard>{children}</AuthGuard>
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}
