"use client";

import { X } from "lucide-react";
import { useId, useState, type KeyboardEvent } from "react";
import { cn } from "@/lib/cn";

export interface TagInputProps {
  label: string;
  value: string[];
  onChange: (tags: string[]) => void;
  placeholder?: string;
  error?: string;
}

/** Add/remove tags via Enter (add) and Backspace-on-empty (remove last),
 * fully keyboard operable (NFR-013). */
export function TagInput({ label, value, onChange, placeholder, error }: TagInputProps) {
  const [draft, setDraft] = useState("");
  const fieldId = useId();
  const errorId = error ? `${fieldId}-error` : undefined;

  function commitDraft() {
    const trimmed = draft.trim();
    if (trimmed && !value.includes(trimmed)) {
      onChange([...value, trimmed]);
    }
    setDraft("");
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter" || event.key === ",") {
      event.preventDefault();
      commitDraft();
    } else if (event.key === "Backspace" && draft === "" && value.length > 0) {
      onChange(value.slice(0, -1));
    }
  }

  function removeTag(tag: string) {
    onChange(value.filter((t) => t !== tag));
  }

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={fieldId} className="text-caption font-medium text-foreground">
        {label}
      </label>
      <div
        className={cn(
          "flex flex-wrap items-center gap-1.5 rounded-md border border-border bg-background p-2",
          "focus-within:ring-2 focus-within:ring-ring",
          error && "border-destructive",
        )}
      >
        {value.map((tag) => (
          <span
            key={tag}
            className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-caption text-foreground"
          >
            {tag}
            <button
              type="button"
              onClick={() => removeTag(tag)}
              aria-label={`Remove tag ${tag}`}
              className="rounded-full hover:bg-border"
            >
              <X className="h-3 w-3" aria-hidden="true" />
            </button>
          </span>
        ))}
        <input
          id={fieldId}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={commitDraft}
          placeholder={value.length === 0 ? placeholder : undefined}
          aria-describedby={errorId}
          className="min-w-[8ch] flex-1 bg-transparent text-body text-foreground outline-none"
        />
      </div>
      {error && (
        <p id={errorId} role="alert" className="text-caption text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
