import { type LucideIcon } from "lucide-react";
import { Card } from "@/components/Card";
import { cn } from "@/lib/cn";

export interface StatCardProps {
  label: string;
  value: string | number;
  icon?: LucideIcon;
  trend?: { direction: "up" | "down"; label: string };
  className?: string;
}

/** A single metric tile used on Overview/Reports (plan.md Component inventory). */
export function StatCard({ label, value, icon: Icon, trend, className }: StatCardProps) {
  return (
    <Card className={cn("flex flex-col gap-2 p-4", className)}>
      <div className="flex items-center justify-between">
        <span className="text-caption font-medium text-muted-foreground">{label}</span>
        {Icon && <Icon className="h-4 w-4 text-muted-foreground" aria-hidden="true" />}
      </div>
      <span className="text-display font-semibold text-foreground">{value}</span>
      {trend && (
        <span
          className={cn(
            "text-caption font-medium",
            trend.direction === "up" ? "text-status-passed" : "text-status-failed",
          )}
        >
          {trend.direction === "up" ? "↑" : "↓"} {trend.label}
        </span>
      )}
    </Card>
  );
}
