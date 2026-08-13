import { type LucideIcon } from "lucide-react";
import { type ReactNode } from "react";

export interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
}

/** First-time/no-data guidance — never a blank table (UX-005). */
export function EmptyState({ icon: Icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border p-12 text-center">
      <Icon className="h-10 w-10 text-muted-foreground" aria-hidden="true" />
      <div>
        <p className="text-subheading font-medium text-foreground">{title}</p>
        {description && <p className="mt-1 text-body text-muted-foreground">{description}</p>}
      </div>
      {action}
    </div>
  );
}
