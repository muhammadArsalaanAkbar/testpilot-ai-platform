"use client";

import { RotateCcw } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { StatusBadge, type TestStatus } from "@/components/badges/StatusBadge";
import { Button } from "@/components/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/Card";
import { RunProgressRing } from "@/components/Progress";
import { ErrorState } from "@/components/states/ErrorState";
import { LoadingState } from "@/components/states/LoadingState";
import { useRetryFailed, useTestRunStatus } from "@/features/testruns/useTestRuns";
import { apiClient } from "@/lib/api-client";
import { useProjectContext } from "../../project-context";

interface TestCaseTitle {
  id: string;
  title: string;
}

export default function TestRunMonitorPage() {
  const params = useParams<{ testRunId: string }>();
  const router = useRouter();
  const { project } = useProjectContext();
  const runId = params.testRunId;

  const { data, isLoading, isError, refetch } = useTestRunStatus(project.id, runId);
  const retry = useRetryFailed(project.id);

  const [titlesById, setTitlesById] = useState<Map<string, string>>(new Map());

  useEffect(() => {
    apiClient
      .get<{ items: TestCaseTitle[] }>(`/projects/${project.id}/test-cases`)
      .then((res) => setTitlesById(new Map(res.items.map((c) => [c.id, c.title]))))
      .catch(() => undefined);
  }, [project.id]);

  if (isLoading) {
    return <LoadingState variant="detail" />;
  }

  if (isError || !data) {
    return <ErrorState onRetry={() => refetch()} />;
  }

  const { test_run: run, results } = data;
  const running = run.status === "queued" || run.status === "running";
  const canRetry = run.status === "completed" && run.summary_failed > 0;

  async function handleRetry() {
    const newRun = await retry.mutateAsync(runId);
    router.push(`/projects/${project.id}/test-runs/${newRun.id}`);
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-subheading font-semibold text-foreground">Test run</h2>
          <p className="mt-1 text-caption text-muted-foreground">
            Started {run.started_at ? new Date(run.started_at).toLocaleString() : "—"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={run.status as TestStatus} />
          {canRetry && (
            <Button variant="outline" size="sm" onClick={handleRetry} loading={retry.isPending}>
              <RotateCcw className="h-4 w-4" aria-hidden="true" />
              Retry failed
            </Button>
          )}
        </div>
      </div>

      <Card>
        <CardContent className="flex flex-col items-center gap-4 pt-6 sm:flex-row sm:justify-around">
          <RunProgressRing
            total={run.summary_total}
            passed={run.summary_passed}
            failed={run.summary_failed}
            skipped={run.summary_skipped}
            running={running ? run.summary_total - run.summary_passed - run.summary_failed - run.summary_skipped : 0}
          />
          <dl className="grid grid-cols-2 gap-x-8 gap-y-2 text-body">
            <dt className="text-muted-foreground">Total</dt>
            <dd className="font-medium text-foreground">{run.summary_total}</dd>
            <dt className="text-status-passed">Passed</dt>
            <dd className="font-medium text-status-passed">{run.summary_passed}</dd>
            <dt className="text-status-failed">Failed</dt>
            <dd className="font-medium text-status-failed">{run.summary_failed}</dd>
            <dt className="text-status-skipped">Skipped</dt>
            <dd className="font-medium text-status-skipped">{run.summary_skipped}</dd>
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Results</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col divide-y divide-border pt-0">
          {results.length === 0 && running && (
            <p className="py-6 text-center text-body text-muted-foreground">Waiting for results…</p>
          )}
          {results.map((result) => (
            <Link
              key={result.id}
              href={`/projects/${project.id}/test-runs/${runId}/results/${result.id}`}
              className="flex flex-col gap-1 py-3 hover:bg-muted"
            >
              <div className="flex items-center justify-between gap-3">
                <span className="text-body text-foreground">
                  {titlesById.get(result.test_case_id) ?? result.test_case_id}
                </span>
                <div className="flex items-center gap-3">
                  <span className="text-caption text-muted-foreground">{result.duration_ms}ms</span>
                  <StatusBadge status={result.status as TestStatus} />
                </div>
              </div>
              {result.error_message && (
                <p className="text-caption text-destructive">{result.error_message}</p>
              )}
            </Link>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
