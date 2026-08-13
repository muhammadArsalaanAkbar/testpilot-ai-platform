import { cn } from "@/lib/cn";

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-md bg-muted", className)} aria-hidden="true" />;
}

/** Content-shaped loading placeholders (UX-005) — never a bare spinner for a
 * content-bearing view. Pick the variant matching what the view will render. */
export interface LoadingStateProps {
  variant?: "table" | "cards" | "detail";
  rows?: number;
}

export function LoadingState({ variant = "table", rows = 5 }: LoadingStateProps) {
  if (variant === "cards") {
    return (
      <div
        role="status"
        aria-label="Loading"
        className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4"
      >
        {Array.from({ length: rows }).map((_, i) => (
          <Skeleton key={i} className="h-24 w-full" />
        ))}
      </div>
    );
  }

  if (variant === "detail") {
    return (
      <div role="status" aria-label="Loading" className="flex flex-col gap-3">
        <Skeleton className="h-8 w-1/3" />
        <Skeleton className="h-4 w-2/3" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  return (
    <div role="status" aria-label="Loading" className="flex flex-col gap-2">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  );
}
