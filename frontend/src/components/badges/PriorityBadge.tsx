import { ArrowDown, ArrowUp, ChevronsUp, Minus } from "lucide-react";
import { cn } from "@/lib/cn";

export type Priority = "low" | "medium" | "high" | "critical";

const config: Record<Priority, { label: string; icon: typeof Minus; classes: string }> = {
  low: { label: "Low", icon: ArrowDown, classes: "bg-priority-low-bg text-priority-low" },
  medium: { label: "Medium", icon: Minus, classes: "bg-priority-medium-bg text-priority-medium" },
  high: { label: "High", icon: ArrowUp, classes: "bg-priority-high-bg text-priority-high" },
  critical: {
    label: "Critical",
    icon: ChevronsUp,
    classes: "bg-priority-critical-bg text-priority-critical",
  },
};

export interface PriorityBadgeProps {
  priority: Priority;
  className?: string;
}

export function PriorityBadge({ priority, className }: PriorityBadgeProps) {
  const { label, icon: Icon, classes } = config[priority];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-caption font-medium",
        classes,
        className,
      )}
    >
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      {label}
    </span>
  );
}
