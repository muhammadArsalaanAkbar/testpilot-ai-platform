"use client";

import { type LucideIcon, X } from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/cn";

export interface SidebarNavItem {
  key: string;
  label: string;
  href: string;
  icon: LucideIcon;
  active?: boolean;
}

export interface SidebarNavProps {
  items: SidebarNavItem[];
  mobileOpen: boolean;
  onMobileOpenChange: (open: boolean) => void;
}

/**
 * Primary navigation (FR-020, UX-002): persistent on desktop, a slide-over
 * drawer below the tablet breakpoint (NFR-015), with clear active-state
 * indication.
 */
export function SidebarNav({ items, mobileOpen, onMobileOpenChange }: SidebarNavProps) {
  return (
    <>
      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/40 md:hidden"
          onClick={() => onMobileOpenChange(false)}
          aria-hidden="true"
        />
      )}

      <nav
        aria-label="Primary"
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-border bg-card p-4",
          "transition-transform md:static md:z-auto md:translate-x-0",
          mobileOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="mb-4 flex items-center justify-between">
          <Link href="/overview" className="text-subheading font-semibold text-foreground">
            TestPilot AI
          </Link>
          <button
            type="button"
            onClick={() => onMobileOpenChange(false)}
            aria-label="Close menu"
            className="rounded-md p-1 hover:bg-muted md:hidden"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>

        <ul className="flex flex-col gap-1">
          {items.map((item) => {
            const Icon = item.icon;
            return (
              <li key={item.key}>
                <Link
                  href={item.href}
                  aria-current={item.active ? "page" : undefined}
                  onClick={() => onMobileOpenChange(false)}
                  className={cn(
                    "flex items-center gap-3 rounded-md px-3 py-2 text-body font-medium",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    item.active
                      ? "bg-primary/10 text-primary"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground",
                  )}
                >
                  <Icon className="h-4 w-4" aria-hidden="true" />
                  {item.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </>
  );
}
