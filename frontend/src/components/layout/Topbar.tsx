"use client";

import { Menu } from "lucide-react";
import { type ReactNode } from "react";

export interface TopbarProps {
  onMenuClick: () => void;
  /** Right-aligned slot — org switcher, notification bell (Phase 5), user menu. */
  children?: ReactNode;
}

export function Topbar({ onMenuClick, children }: TopbarProps) {
  return (
    <header className="flex h-14 items-center justify-between border-b border-border bg-card px-4">
      <button
        type="button"
        onClick={onMenuClick}
        aria-label="Open menu"
        className="rounded-md p-2 hover:bg-muted md:hidden"
      >
        <Menu className="h-5 w-5" aria-hidden="true" />
      </button>
      <div className="hidden md:block" />
      <div className="flex items-center gap-2">{children}</div>
    </header>
  );
}
