"use client";

import { useId, useState } from "react";
import { cn } from "@/lib/cn";

export interface URLFieldProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  onValidityChange?: (isValid: boolean) => void;
  required?: boolean;
  error?: string;
  hint?: string;
}

/** Client-side well-formedness + http(s)-only check, mirroring the first half
 * of FR-026 (the server still re-validates and additionally rejects
 * private/internal addresses per FR-035/SEC-006 — this is a fast-feedback
 * convenience, not the source of truth). */
function validateUrl(value: string): string | null {
  if (!value) return null;
  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    return "Enter a full URL, including https://";
  }
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    return "URL must start with http:// or https://";
  }
  return null;
}

export function URLField({
  label,
  value,
  onChange,
  onValidityChange,
  required,
  error: externalError,
  hint,
}: URLFieldProps) {
  const [touched, setTouched] = useState(false);
  const fieldId = useId();
  const clientError = touched ? validateUrl(value) : null;
  const error = externalError ?? clientError ?? undefined;
  const hintId = hint ? `${fieldId}-hint` : undefined;
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
      <input
        id={fieldId}
        type="url"
        inputMode="url"
        required={required}
        value={value}
        placeholder="https://example.com"
        onChange={(e) => onChange(e.target.value)}
        onBlur={() => {
          setTouched(true);
          onValidityChange?.(validateUrl(value) === null);
        }}
        aria-invalid={Boolean(error)}
        aria-describedby={cn(hintId, errorId) || undefined}
        className={cn(
          "h-10 rounded-md border border-border bg-background px-3 text-body text-foreground",
          "placeholder:text-muted-foreground",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          error && "border-destructive",
        )}
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
}
