"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export interface GenerationRun {
  id: string;
  project_id: string;
  scope: "full_batch" | "single_case";
  status: "queued" | "running" | "completed" | "failed";
  failure_reason: string | null;
  created_test_case_ids: string[];
  created_at: string;
  completed_at: string | null;
}

const TERMINAL_STATUSES = new Set<GenerationRun["status"]>(["completed", "failed"]);

function generationRunKey(projectId: string, runId: string) {
  return ["generation-run", projectId, runId] as const;
}

/**
 * Polls a generation run's status every 2s (research.md #11: short-interval
 * polling, not WebSockets, for MVP) until it reaches a terminal state, then
 * stops automatically.
 */
export function useGenerationRunStatus(projectId: string, runId: string | null) {
  return useQuery({
    queryKey: runId ? generationRunKey(projectId, runId) : (["generation-run", projectId, "none"] as const),
    queryFn: () => apiClient.get<GenerationRun>(`/projects/${projectId}/test-cases/generate/${runId}`),
    enabled: runId !== null,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data || TERMINAL_STATUSES.has(data.status)) return false;
      return 2000;
    },
  });
}

/** Triggers a full-batch generation for a project (FR-036). */
export function useTriggerGeneration(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.post<GenerationRun>(`/projects/${projectId}/test-cases/generate`),
    onSuccess: (run) => {
      queryClient.setQueryData(generationRunKey(projectId, run.id), run);
    },
  });
}

/** Requests regeneration of a single test case (FR-043). */
export function useRegenerateTestCase(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (testCaseId: string) =>
      apiClient.post<GenerationRun>(`/projects/${projectId}/test-cases/${testCaseId}/regenerate`),
    onSuccess: (run) => {
      queryClient.setQueryData(generationRunKey(projectId, run.id), run);
    },
  });
}
