import { cn } from "@/lib/cn";

export interface ProgressBarProps {
  value: number;
  max: number;
  label?: string;
  className?: string;
}

/** Linear progress, e.g. AI generation percentage complete. */
export function ProgressBar({ value, max, label, className }: ProgressBarProps) {
  const percent = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0;
  return (
    <div className={cn("flex flex-col gap-1", className)}>
      {label && <span className="text-caption text-muted-foreground">{label}</span>}
      <div
        role="progressbar"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
        className="h-2 w-full overflow-hidden rounded-full bg-muted"
      >
        <div
          className="h-full rounded-full bg-primary transition-[width]"
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}

export interface RunProgressRingProps {
  total: number;
  passed: number;
  failed: number;
  skipped: number;
  running: number;
  size?: number;
}

/** Circular multi-segment progress for a live test run (UX-004): shows real
 * proportion completed, not just a static "running" label. */
export function RunProgressRing({
  total,
  passed,
  failed,
  skipped,
  running,
  size = 96,
}: RunProgressRingProps) {
  const radius = (size - 12) / 2;
  const circumference = 2 * Math.PI * radius;
  const completed = passed + failed + skipped;
  const segments = [
    { value: passed, colorVar: "--color-status-passed" },
    { value: failed, colorVar: "--color-status-failed" },
    { value: skipped, colorVar: "--color-status-skipped" },
  ];

  let offset = 0;
  const center = size / 2;

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={center}
          cy={center}
          r={radius}
          strokeWidth={8}
          className="fill-none stroke-muted"
        />
        {total > 0 &&
          segments.map((segment, i) => {
            if (segment.value === 0) return null;
            const fraction = segment.value / total;
            const dash = fraction * circumference;
            const circle = (
              <circle
                key={i}
                cx={center}
                cy={center}
                r={radius}
                strokeWidth={8}
                strokeDasharray={`${dash} ${circumference - dash}`}
                strokeDashoffset={-offset}
                stroke={`hsl(var(${segment.colorVar}))`}
                className="fill-none transition-all"
                strokeLinecap="butt"
              />
            );
            offset += dash;
            return circle;
          })}
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="text-heading font-semibold text-foreground">
          {total > 0 ? Math.round((completed / total) * 100) : 0}%
        </span>
        <span className="text-caption text-muted-foreground">
          {running > 0 ? "Running" : completed === total ? "Complete" : "Queued"}
        </span>
      </div>
    </div>
  );
}
