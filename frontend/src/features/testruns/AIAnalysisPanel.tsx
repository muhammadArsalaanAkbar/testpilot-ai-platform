"use client";

import { RotateCcw, Sparkles } from "lucide-react";
import { useState } from "react";
import { SeverityBadge } from "@/components/badges/SeverityBadge";
import { Button } from "@/components/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/Card";
import { ErrorState } from "@/components/states/ErrorState";
import { LoadingState } from "@/components/states/LoadingState";
import { type AIAnalysis, useAnalysisStatus, useRequestAnalysis } from "./useAIAnalysis";

export interface AIAnalysisPanelProps {
  projectId: string;
  testRunId: string;
  testResultId: string;
  /** History for this result, most recent first (from the result-detail
   * response's `ai_analyses` field) — the panel starts from this, and
   * switches to live polling only once a new request is made. */
  initialAnalyses: AIAnalysis[];
}

/** AI failure analysis: explanation/root-cause/severity/fix plus the
 * expected-vs-actual comparison (FR-081/FR-082), with request/re-request
 * (FR-085) and a distinct "unavailable" state on provider failure (FR-083)
 * — never a fabricated result. T164/T165. */
export function AIAnalysisPanel({ projectId, testRunId, testResultId, initialAnalyses }: AIAnalysisPanelProps) {
  const request = useRequestAnalysis(projectId, testRunId, testResultId);
  const [liveAnalysisId, setLiveAnalysisId] = useState<string | null>(null);
  const { data: liveAnalysis } = useAnalysisStatus(projectId, testRunId, testResultId, liveAnalysisId);

  const mostRecentPersisted = initialAnalyses[0] ?? null;
  const current = liveAnalysis ?? mostRecentPersisted;

  async function handleRequest() {
    const result = await request.mutateAsync();
    setLiveAnalysisId(result.id);
  }

  if (!current) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>AI Failure Analysis</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col items-center gap-3 pb-8 pt-0 text-center">
          <p className="text-body text-muted-foreground">No analysis has been requested for this failure yet.</p>
          <Button onClick={handleRequest} loading={request.isPending}>
            <Sparkles className="h-4 w-4" aria-hidden="true" />
            Request AI analysis
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (current.status === "queued") {
    return (
      <Card>
        <CardHeader>
          <CardTitle>AI Failure Analysis</CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <p className="mb-3 text-caption text-muted-foreground">Analyzing this failure…</p>
          <LoadingState variant="cards" rows={2} />
        </CardContent>
      </Card>
    );
  }

  if (current.status === "failed") {
    return (
      <Card>
        <CardHeader>
          <CardTitle>AI Failure Analysis</CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <ErrorState
            variant="unavailable"
            title="Analysis unavailable"
            description={current.failure_reason ?? "The AI provider could not complete this analysis."}
            onRetry={handleRequest}
          />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-3">
        <CardTitle>AI Failure Analysis</CardTitle>
        <div className="flex items-center gap-2">
          {current.severity && <SeverityBadge severity={current.severity} />}
          <Button variant="outline" size="sm" onClick={handleRequest} loading={request.isPending}>
            <RotateCcw className="h-4 w-4" aria-hidden="true" />
            Re-analyze
          </Button>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-4 pt-0">
        <div>
          <h4 className="text-caption font-medium text-muted-foreground">Explanation</h4>
          <p className="mt-1 text-body text-foreground">{current.explanation}</p>
        </div>
        <div>
          <h4 className="text-caption font-medium text-muted-foreground">Root cause</h4>
          <p className="mt-1 text-body text-foreground">{current.root_cause}</p>
        </div>
        {current.expected_vs_actual && (
          <div>
            <h4 className="text-caption font-medium text-muted-foreground">Expected vs. actual</h4>
            <pre className="mt-1 whitespace-pre-wrap rounded-md bg-muted p-3 text-caption text-foreground">
              {current.expected_vs_actual}
            </pre>
          </div>
        )}
        <div>
          <h4 className="text-caption font-medium text-muted-foreground">Suggested fix</h4>
          <p className="mt-1 text-body text-foreground">{current.suggested_fix}</p>
        </div>
      </CardContent>
    </Card>
  );
}
