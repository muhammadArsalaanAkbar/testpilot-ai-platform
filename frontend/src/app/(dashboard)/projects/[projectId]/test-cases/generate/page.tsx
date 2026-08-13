"use client";

import { Sparkles } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/Card";
import { EmptyState } from "@/components/states/EmptyState";
import { LoadingState } from "@/components/states/LoadingState";
import { useToast } from "@/components/Toast";
import {
  useGenerationRunStatus,
  useRegenerateTestCase,
  useTriggerGeneration,
} from "@/features/testcases/useGeneration";
import { apiClient, ApiError } from "@/lib/api-client";
import { cn } from "@/lib/cn";
import { useProjectContext } from "../../project-context";

interface TestCase {
  id: string;
  title: string;
  description: string;
  priority: string;
  severity: string;
  status: "draft" | "approved" | "rejected";
  tags: string[];
}

function statusTone(status: TestCase["status"]) {
  if (status === "approved") return "bg-status-passed-bg text-status-passed";
  if (status === "rejected") return "bg-status-failed-bg text-status-failed";
  return "bg-muted text-muted-foreground";
}

function triggerErrorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.code === "plan_limit_exceeded") {
      return "You've reached your plan's AI operation limit for this billing period.";
    }
    if (err.code === "generation_in_progress") {
      return "A generation job is already in progress for this project.";
    }
    if (err.code === "project_archived") {
      return "This project is archived. Unarchive it to generate test cases.";
    }
  }
  return "Something went wrong. Please try again.";
}

interface ReviewCardProps {
  testCase: TestCase;
  projectId: string;
  onChange: (updated: TestCase) => void;
}

function ReviewCard({ testCase, projectId, onChange }: ReviewCardProps) {
  const { showToast } = useToast();
  const regenerate = useRegenerateTestCase(projectId);
  const [regenerateRunId, setRegenerateRunId] = useState<string | null>(null);
  const { data: regenerateRun } = useGenerationRunStatus(projectId, regenerateRunId);
  const regenerating = regenerateRunId !== null && regenerateRun?.status !== "completed" && regenerateRun?.status !== "failed";

  useEffect(() => {
    if (regenerateRun?.status === "completed") {
      apiClient.get<{ test_case: TestCase }>(`/projects/${projectId}/test-cases/${testCase.id}`).then((res) => {
        onChange(res.test_case);
        setRegenerateRunId(null);
        showToast({ variant: "success", title: "Test case regenerated" });
      });
    } else if (regenerateRun?.status === "failed") {
      setRegenerateRunId(null);
      showToast({ variant: "error", title: "Regeneration failed. Please try again." });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [regenerateRun?.status]);

  async function handleApprove() {
    const updated = await apiClient.post<TestCase>(`/projects/${projectId}/test-cases/${testCase.id}/approve`);
    onChange(updated);
  }

  async function handleReject() {
    const updated = await apiClient.post<TestCase>(`/projects/${projectId}/test-cases/${testCase.id}/reject`);
    onChange(updated);
  }

  async function handleRegenerate() {
    const run = await regenerate.mutateAsync(testCase.id);
    setRegenerateRunId(run.id);
  }

  return (
    <Card>
      <CardContent className="flex flex-col gap-3 pt-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <Link
              href={`/projects/${projectId}/test-cases/${testCase.id}`}
              className="text-body font-medium text-foreground hover:underline"
            >
              {testCase.title}
            </Link>
            <p className="mt-1 text-caption text-muted-foreground">{testCase.description}</p>
          </div>
          <span
            className={cn(
              "shrink-0 inline-flex items-center rounded-full px-2 py-0.5 text-caption font-medium capitalize",
              statusTone(testCase.status),
            )}
          >
            {testCase.status}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-caption text-muted-foreground">
          <span className="capitalize">Priority: {testCase.priority}</span>
          <span aria-hidden="true">·</span>
          <span className="capitalize">Severity: {testCase.severity}</span>
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" disabled={testCase.status === "approved"} onClick={handleApprove}>
            Approve
          </Button>
          <Button size="sm" variant="outline" disabled={testCase.status === "rejected"} onClick={handleReject}>
            Reject
          </Button>
          <Button size="sm" variant="ghost" loading={regenerating} onClick={handleRegenerate}>
            Regenerate
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export default function GenerationReviewPage() {
  const { project } = useProjectContext();
  const trigger = useTriggerGeneration(project.id);
  const [runId, setRunId] = useState<string | null>(null);
  const { data: run } = useGenerationRunStatus(project.id, runId);

  const [cases, setCases] = useState<TestCase[]>([]);
  const [casesLoading, setCasesLoading] = useState(false);
  const [triggerError, setTriggerError] = useState<string | null>(null);

  const inProgress = runId !== null && run?.status !== "completed" && run?.status !== "failed";

  useEffect(() => {
    if (run?.status === "completed" && run.created_test_case_ids.length > 0 && cases.length === 0) {
      setCasesLoading(true);
      Promise.all(
        run.created_test_case_ids.map((id) =>
          apiClient.get<{ test_case: TestCase }>(`/projects/${project.id}/test-cases/${id}`),
        ),
      )
        .then((results) => setCases(results.map((r) => r.test_case)))
        .finally(() => setCasesLoading(false));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run?.status]);

  async function handleTrigger() {
    setTriggerError(null);
    setCases([]);
    try {
      const result = await trigger.mutateAsync();
      setRunId(result.id);
    } catch (err) {
      setTriggerError(triggerErrorMessage(err));
    }
  }

  function updateCase(updated: TestCase) {
    setCases((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-subheading font-semibold text-foreground">Generate test cases</h2>
          <p className="mt-1 text-body text-muted-foreground">
            AI analyzes {project.url} and proposes test cases covering positive, negative, and edge-case flows for
            you to review.
          </p>
        </div>
        <Button onClick={handleTrigger} loading={trigger.isPending || inProgress}>
          <Sparkles className="h-4 w-4" aria-hidden="true" />
          {run ? "Generate again" : "Generate test cases"}
        </Button>
      </div>

      {triggerError && (
        <p role="alert" className="text-caption text-destructive">
          {triggerError}
        </p>
      )}

      {inProgress && (
        <Card>
          <CardHeader>
            <CardTitle>Analyzing {project.url}…</CardTitle>
          </CardHeader>
          <CardContent>
            <LoadingState variant="cards" rows={3} />
          </CardContent>
        </Card>
      )}

      {run?.status === "failed" && (
        <p role="alert" className="text-caption text-destructive">
          Generation failed: {run.failure_reason ?? "Unknown error."} No testable public content may have been
          found at this URL.
        </p>
      )}

      {run?.status === "completed" && casesLoading && <LoadingState variant="cards" rows={3} />}

      {run?.status === "completed" && !casesLoading && cases.length === 0 && (
        <EmptyState
          icon={Sparkles}
          title="No test cases were generated"
          description="The AI couldn't identify any testable flows for this project's URL."
        />
      )}

      {cases.length > 0 && (
        <div className="flex flex-col gap-3">
          {cases.map((testCase) => (
            <ReviewCard key={testCase.id} testCase={testCase} projectId={project.id} onChange={updateCase} />
          ))}
        </div>
      )}
    </div>
  );
}
