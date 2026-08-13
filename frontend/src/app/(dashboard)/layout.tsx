"use client";

import { Bot, FolderKanban, LayoutDashboard, Settings } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/Button";
import { DropdownMenu } from "@/components/DropdownMenu";
import { NotificationBell } from "@/components/layout/NotificationBell";
import { SidebarNav, type SidebarNavItem } from "@/components/layout/SidebarNav";
import { Topbar } from "@/components/layout/Topbar";
import { LoadingState } from "@/components/states/LoadingState";
import { useRequireAuth } from "@/lib/auth";

const NAV_ITEMS: Omit<SidebarNavItem, "active">[] = [
  { key: "overview", label: "Overview", href: "/overview", icon: LayoutDashboard },
  { key: "projects", label: "Projects", href: "/projects", icon: FolderKanban },
  { key: "assistant", label: "AI Assistant", href: "/assistant", icon: Bot },
  { key: "settings", label: "Settings", href: "/settings/profile", icon: Settings },
];

/**
 * Authenticated app shell (FR-007, FR-020, FR-024): auth guard, org
 * context, sidebar + topbar wiring. Every page under (dashboard) mounts
 * inside this layout.
 */
export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { user, organization, isLoading, isAuthenticated, logout } = useRequireAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  const items: SidebarNavItem[] = NAV_ITEMS.map((item) => ({
    ...item,
    active: item.key === "settings" ? pathname.startsWith("/settings") : pathname.startsWith(item.href),
  }));

  if (isLoading || !isAuthenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <LoadingState variant="detail" />
      </div>
    );
  }

  async function handleLogout() {
    await logout();
    router.push("/login");
  }

  return (
    <div className="flex min-h-screen">
      <SidebarNav items={items} mobileOpen={mobileNavOpen} onMobileOpenChange={setMobileNavOpen} />
      <div className="flex flex-1 flex-col">
        <Topbar onMenuClick={() => setMobileNavOpen(true)}>
          <NotificationBell />
          <DropdownMenu
            trigger={
              <Button variant="ghost" size="sm">
                {organization?.name ?? "Organization"}
              </Button>
            }
            items={[
              { key: "profile", label: "Profile settings", onSelect: () => router.push("/settings/profile") },
              { key: "logout", label: `Log out (${user?.email ?? ""})`, onSelect: handleLogout },
            ]}
          />
        </Topbar>
        <main className="flex-1 p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}
