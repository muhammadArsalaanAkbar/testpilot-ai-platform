import { AlertOctagon, CheckCircle2, CheckCircle, Clock, Loader2, MinusCircle, XCircle } from "lucide-react";
import { cn } from "@/lib/cn";

export type TestStatus = "passed" | "failed" | "skipped" | "running" | "queued" | "error" | "completed";

// Tailwind's content scanner needs literal class strings — it cannot see
// classes assembled via `${status}` template interpolation — so every
// variant's classes are spelled out in full here rather than built
// dynamically.
const config: Record<
  TestStatus,
  { label: string; icon: typeof CheckCircle2; spin?: boolean; classes: string }
> = {
  passed: { label: "Passed", icon: CheckCircle2, classes: "bg-status-passed-bg text-status-passed" },
  failed: { label: "Failed", icon: XCircle, classes: "bg-status-failed-bg text-status-failed" },
  skipped: {
    label: "Skipped",
    icon: MinusCircle,
    classes: "bg-status-skipped-bg text-status-skipped",
  },
  running: {
    label: "Running",
    icon: Loader2,
    spin: true,
    classes: "bg-status-running-bg text-status-running",
  },
  queued: { label: "Queued", icon: Clock, classes: "bg-status-queued-bg text-status-queued" },
  error: { label: "Error", icon: AlertOctagon, classes: "bg-status-error-bg text-status-error" },
  // A run-level "completed" only means the run finished, not that every
  // case passed (that breakdown is the summary counters) — deliberately
  // neutral styling, distinct from "passed".
  completed: { label: "Completed", icon: CheckCircle, classes: "bg-status-completed-bg text-status-completed" },
};

export interface StatusBadgeProps {
  status: TestStatus;
  className?: string;
}

/** Status is always shown via icon + text, never color alone (UX-003), so
 * the badge remains legible to colorblind users and in monochrome contexts
 * (e.g. printed reports). */
export function StatusBadge({ status, className }: StatusBadgeProps) {
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
