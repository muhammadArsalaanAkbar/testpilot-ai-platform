"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

/**
 * Query key convention (research.md #10): namespaced by Organization then
 * entity, so a mutation only needs to invalidate the precise keys it
 * affects rather than refetching everything.
 *
 *   queryKeys.org(orgId).projects.list()
 *   queryKeys.org(orgId).projects.detail(projectId)
 *   queryKeys.org(orgId).project(projectId).testCases.list(filters)
 */
export const queryKeys = {
  org: (orgId: string) => ({
    all: [orgId] as const,
    self: () => [orgId, "organization"] as const,
    billing: () => [orgId, "billing"] as const,
    notifications: () => [orgId, "notifications"] as const,
    projects: {
      list: () => [orgId, "projects"] as const,
      detail: (projectId: string) => [orgId, "projects", projectId] as const,
    },
    project: (projectId: string) => ({
      testCases: {
        list: (filters?: Record<string, unknown>) =>
          [orgId, "projects", projectId, "test-cases", filters ?? {}] as const,
        detail: (testCaseId: string) =>
          [orgId, "projects", projectId, "test-cases", testCaseId] as const,
      },
      testRuns: {
        list: () => [orgId, "projects", projectId, "test-runs"] as const,
        detail: (testRunId: string) =>
          [orgId, "projects", projectId, "test-runs", testRunId] as const,
      },
      issues: {
        list: (filters?: Record<string, unknown>) =>
          [orgId, "projects", projectId, "issues", filters ?? {}] as const,
        detail: (issueId: string) => [orgId, "projects", projectId, "issues", issueId] as const,
      },
      reports: {
        summary: () => [orgId, "projects", projectId, "reports", "summary"] as const,
      },
    }),
  }),
};

export function AppQueryProvider({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            retry: 1,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );

  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
