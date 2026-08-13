import { forwardRef, useId, type InputHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

export interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
  hint?: string;
}

/** Labeled text input with associated error/hint text, wired for screen readers
 * via aria-describedby and aria-invalid (NFR-013/NFR-014). */
export const TextField = forwardRef<HTMLInputElement, TextFieldProps>(
  ({ label, error, hint, id, className, required, ...props }, ref) => {
    const generatedId = useId();
    const fieldId = id ?? generatedId;
    const hintId = hint ? `${fieldId}-hint` : undefined;
    const errorId = error ? `${fieldId}-error` : undefined;

    return (
      <div className="flex flex-col gap-1.5">
        {/* The required-indicator asterisk is a SIBLING of <label>, not a
            child: a browser's accessible-name computation for a <label>
            walks all of its descendant text content regardless of
            aria-hidden on those descendants (unlike name-from-content
            elsewhere), so an asterisk nested inside the label silently
            leaks into the field's accessible name (e.g. "Password *"),
            breaking exact-match label queries/screen-reader announcements. */}
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
        <input
          ref={ref}
          id={fieldId}
          required={required}
          aria-invalid={Boolean(error)}
          aria-describedby={cn(hintId, errorId) || undefined}
          className={cn(
            "h-10 rounded-md border border-border bg-background px-3 text-body text-foreground",
            "placeholder:text-muted-foreground",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            error && "border-destructive",
            className,
          )}
          {...props}
        />
        {hint && !error && (
          <p id={hintId} className="text-caption text-muted-foreground">
            {hint}
          </p>
        )}
        {error && (
          <p id={errorId} role="alert" className="text-caption text-destructive">
            {error}
          </p>
        )}
      </div>
    );
  },
);
TextField.displayName = "TextField";
