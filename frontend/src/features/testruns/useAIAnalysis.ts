"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient, ApiError } from "@/lib/api-client";

export interface AIAnalysis {
  id: string;
  test_result_id: string;
  status: "queued" | "completed" | "failed";
  explanation: string | null;
  root_cause: string | null;
  severity: "minor" | "major" | "critical" | "blocker" | null;
  suggested_fix: string | null;
  expected_vs_actual: string;
  failure_reason: string | null;
  provider: string | null;
  model: string | null;
  created_at: string | null;
}

function analysisKey(projectId: string, testRunId: string, testResultId: string, analysisId: string) {
  return ["ai-analysis", projectId, testRunId, testResultId, analysisId] as const;
}

/**
 * Polls an analysis's status every 2s until it reaches a terminal state
 * (same short-interval-polling pattern as useTestRuns.ts). A 404 means the
 * worker hasn't created the row yet — that is "still queued," not an error
 * (ai_analysis/models.py's module docstring: no row exists until the job
 * concludes), so it is folded into the queued state rather than surfaced.
 */
export function useAnalysisStatus(
  projectId: string,
  testRunId: string,
  testResultId: string,
  analysisId: string | null,
) {
  return useQuery({
    queryKey: analysisId
      ? analysisKey(projectId, testRunId, testResultId, analysisId)
      : (["ai-analysis", projectId, testRunId, testResultId, "none"] as const),
    queryFn: async (): Promise<AIAnalysis> => {
      try {
        return await apiClient.get<AIAnalysis>(
          `/projects/${projectId}/test-runs/${testRunId}/results/${testResultId}/analyses/${analysisId}`,
        );
      } catch (err) {
        if (err instanceof ApiError && err.status === 404 && analysisId) {
          return {
            id: analysisId,
            test_result_id: testResultId,
            status: "queued",
            explanation: null,
            root_cause: null,
            severity: null,
            suggested_fix: null,
            expected_vs_actual: "",
            failure_reason: null,
            provider: null,
            model: null,
            created_at: null,
          };
        }
        throw err;
      }
    },
    enabled: analysisId !== null,
    refetchInterval: (query) => (query.state.data?.status === "queued" ? 2000 : false),
  });
}

/** Requests (or re-requests, FR-085) AI analysis of a failed result. */
export function useRequestAnalysis(projectId: string, testRunId: string, testResultId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiClient.post<AIAnalysis>(`/projects/${projectId}/test-runs/${testRunId}/results/${testResultId}/analyze`),
    onSuccess: (analysis) => {
      queryClient.setQueryData(analysisKey(projectId, testRunId, testResultId, analysis.id), analysis);
    },
  });
}
