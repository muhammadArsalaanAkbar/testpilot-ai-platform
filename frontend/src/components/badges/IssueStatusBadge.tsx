import { Archive, Ban, CheckCircle2, CircleDot, Loader2 } from "lucide-react";
import { cn } from "@/lib/cn";

export type IssueStatus = "open" | "in_progress" | "resolved" | "closed" | "wont_fix";

// Reuses the existing status design tokens (no new colors introduced,
// UX-001[a]) — mapped by semantic association: open~queued (pending),
// in_progress~running (active), resolved~passed (done well), closed~a
// neutral "finished" tone, wont_fix~skipped (a deliberate non-outcome).
const config: Record<
  IssueStatus,
  { label: string; icon: typeof CircleDot; spin?: boolean; classes: string }
> = {
  open: { label: "Open", icon: CircleDot, classes: "bg-status-queued-bg text-status-queued" },
  in_progress: {
    label: "In Progress",
    icon: Loader2,
    spin: true,
    classes: "bg-status-running-bg text-status-running",
  },
  resolved: { label: "Resolved", icon: CheckCircle2, classes: "bg-status-passed-bg text-status-passed" },
  closed: { label: "Closed", icon: Archive, classes: "bg-status-completed-bg text-status-completed" },
  wont_fix: { label: "Won't Fix", icon: Ban, classes: "bg-status-skipped-bg text-status-skipped" },
};

export interface IssueStatusBadgeProps {
  status: IssueStatus;
  className?: string;
}

/** Status is always shown via icon + text, never color alone (UX-003). */
export function IssueStatusBadge({ status, className }: IssueStatusBadgeProps) {
  const { label, icon: Icon, spin, classes } = config[status];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-caption font-medium",
        classes,
        className,
      )}
    >
      <Icon className={cn("h-3.5 w-3.5", spin && "animate-spin")} aria-hidden="true" />
      {label}
    </span>
  );
}
