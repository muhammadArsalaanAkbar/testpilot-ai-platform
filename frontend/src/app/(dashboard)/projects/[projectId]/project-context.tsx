"use client";

import { createContext, useContext } from "react";

export interface ProjectDetail {
  id: string;
  name: string;
  url: string;
  status: "active" | "archived";
  settings: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ProjectContextValue {
  project: ProjectDetail;
  refresh: () => Promise<void>;
}

// Not colocated in layout.tsx: Next.js App Router route files (layout.tsx/
// page.tsx) may only export a fixed whitelist of names (default, metadata,
// generateStaticParams, etc.) — its generated route types reject any other
// named export, which a shared hook/context living in layout.tsx would be.
export const ProjectContext = createContext<ProjectContextValue | null>(null);

/** Provides the current project (FR-024) to the detail/settings pages
 * nested under the project layout, so neither re-fetches it independently. */
export function useProjectContext(): ProjectContextValue {
  const ctx = useContext(ProjectContext);
  if (!ctx) throw new Error("useProjectContext must be used within the project layout");
  return ctx;
}
