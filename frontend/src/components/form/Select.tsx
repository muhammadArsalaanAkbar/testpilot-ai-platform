import { forwardRef, useId, type SelectHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

export interface SelectOption {
  value: string;
  label: string;
}

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string;
  options: SelectOption[];
  error?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ label, options, error, id, className, required, ...props }, ref) => {
    const generatedId = useId();
    const fieldId = id ?? generatedId;
    const errorId = error ? `${fieldId}-error` : undefined;

    return (
      <div className="flex flex-col gap-1.5">
        {/* See TextField.tsx for why the asterisk is a sibling, not a child, of <label>. */}
        <span className="flex items-center gap-0.5">
          <label htmlFor={fieldId} className="text-caption font-medium text-foreground">
            {label}
          </label>
          {required && (
            <span aria-hidden="true" className="text-caption text-muted-foreground">
              *
            </span>
          )}
        </span>
        <select
          ref={ref}
          id={fieldId}
          required={required}
          aria-invalid={Boolean(error)}
          aria-describedby={errorId}
          className={cn(
            "h-10 rounded-md border border-border bg-background px-3 text-body text-foreground",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            error && "border-destructive",
            className,
          )}
          {...props}
        >
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        {error && (
          <p id={errorId} role="alert" className="text-caption text-destructive">
            {error}
          </p>
        )}
      </div>
    );
  },
);
Select.displayName = "Select";
