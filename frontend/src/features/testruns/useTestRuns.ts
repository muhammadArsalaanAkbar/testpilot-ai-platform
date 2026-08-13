"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export interface TestRun {
  id: string;
  project_id: string;
  status: "queued" | "running" | "completed" | "error";
  summary_total: number;
  summary_passed: number;
  summary_failed: number;
  summary_skipped: number;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface TestResultSummary {
  id: string;
  test_run_id: string;
  test_case_id: string;
  status: "passed" | "failed" | "skipped" | "error";
  failure_step_index: number | null;
  error_message: string | null;
  started_at: string;
  completed_at: string;
  duration_ms: number;
}

export interface TestRunDetail {
  test_run: TestRun;
  results: TestResultSummary[];
}

const TERMINAL_STATUSES = new Set<TestRun["status"]>(["completed", "error"]);

function testRunKey(projectId: string, runId: string) {
  return ["test-run", projectId, runId] as const;
}

/**
 * Polls a test run's status every 2s (same short-interval-polling pattern as
 * useGeneration.ts's useGenerationRunStatus, research.md #11) until it
 * reaches a terminal state, then stops automatically.
 */
export function useTestRunStatus(projectId: string, runId: string | null) {
  return useQuery({
    queryKey: runId ? testRunKey(projectId, runId) : (["test-run", projectId, "none"] as const),
    queryFn: () => apiClient.get<TestRunDetail>(`/projects/${projectId}/test-runs/${runId}`),
    enabled: runId !== null,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data || TERMINAL_STATUSES.has(data.test_run.status)) return false;
      return 2000;
    },
  });
}

/** Starts a run against the given approved test case IDs (FR-069). */
export function useCreateTestRun(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (testCaseIds: string[]) =>
      apiClient.post<TestRun>(`/projects/${projectId}/test-runs`, { test_case_ids: testCaseIds }),
    onSuccess: (run) => {
      queryClient.setQueryData(testRunKey(projectId, run.id), { test_run: run, results: [] } satisfies TestRunDetail);
    },
  });
}

/** Retries only the failed cases from a completed run (FR-073). */
export function useRetryFailed(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (testRunId: string) =>
      apiClient.post<TestRun>(`/projects/${projectId}/test-runs/${testRunId}/retry-failed`),
    onSuccess: (run) => {
      queryClient.setQueryData(testRunKey(projectId, run.id), { test_run: run, results: [] } satisfies TestRunDetail);
    },
  });
}
