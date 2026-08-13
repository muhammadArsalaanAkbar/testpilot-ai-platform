import { AlertOctagon, AlertTriangle, Ban, Info } from "lucide-react";
import { cn } from "@/lib/cn";

export type Severity = "minor" | "major" | "critical" | "blocker";

const config: Record<Severity, { label: string; icon: typeof Info; classes: string }> = {
  minor: { label: "Minor", icon: Info, classes: "bg-severity-minor-bg text-severity-minor" },
  major: {
    label: "Major",
    icon: AlertTriangle,
    classes: "bg-severity-major-bg text-severity-major",
  },
  critical: {
    label: "Critical",
    icon: AlertOctagon,
    classes: "bg-severity-critical-bg text-severity-critical",
  },
  blocker: { label: "Blocker", icon: Ban, classes: "bg-severity-blocker-bg text-severity-blocker" },
};

export interface SeverityBadgeProps {
  severity: Severity;
  className?: string;
}

export function SeverityBadge({ severity, className }: SeverityBadgeProps) {
  const { label, icon: Icon, classes } = config[severity];
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
