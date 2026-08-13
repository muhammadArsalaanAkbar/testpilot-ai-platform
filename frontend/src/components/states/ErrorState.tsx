import { AlertTriangle, WifiOff } from "lucide-react";
import { Button } from "@/components/Button";

export interface ErrorStateProps {
  title?: string;
  description?: string;
  onRetry?: () => void;
  /** Use "unavailable" for a distinct AI/service-unavailable state (spec Edge
   * Cases: this must read differently from "nothing has happened yet"). */
  variant?: "error" | "unavailable";
}

/** Distinct from EmptyState — communicates something went wrong, not "no
 * data yet" (UX-005). */
export function ErrorState({
  title,
  description,
  onRetry,
  variant = "error",
}: ErrorStateProps) {
  const Icon = variant === "unavailable" ? WifiOff : AlertTriangle;
  const defaultTitle = variant === "unavailable" ? "Currently unavailable" : "Something went wrong";

  return (
    <div
      role="alert"
      className="flex flex-col items-center justify-center gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-12 text-center"
    >
      <Icon className="h-10 w-10 text-destructive" aria-hidden="true" />
      <div>
        <p className="text-subheading font-medium text-foreground">{title ?? defaultTitle}</p>
        {description && <p className="mt-1 text-body text-muted-foreground">{description}</p>}
      </div>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}
