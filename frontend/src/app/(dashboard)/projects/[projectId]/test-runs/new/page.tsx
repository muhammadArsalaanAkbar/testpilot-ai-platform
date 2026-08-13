"use client";

import { CheckSquare, Play } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button } from "@/components/Button";
import { Card, CardContent } from "@/components/Card";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { LoadingState } from "@/components/states/LoadingState";
import { useCreateTestRun } from "@/features/testruns/useTestRuns";
import { apiClient, ApiError } from "@/lib/api-client";
import { cn } from "@/lib/cn";
import { useProjectContext } from "../../project-context";

interface TestCase {
  id: string;
  title: string;
  priority: "low" | "medium" | "high" | "critical";
  status: "draft" | "approved" | "rejected";
}

function createErrorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.code === "plan_limit_exceeded") {
      return "You've reached your plan's test-execution limit for this billing period.";
    }
    if (err.code === "project_archived") {
      return "This project is archived. Unarchive it to start a test run.";
    }
    if (err.code === "no_approved_cases_selected") {
      return "One or more selected test cases are rejected and cannot be run.";
    }
  }
  return "Something went wrong. Please try again.";
}

export default function NewTestRunPage() {
  const router = useRouter();
  const { project } = useProjectContext();
  const create = useCreateTestRun(project.id);

  const [cases, setCases] = useState<TestCase[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  async function load() {
    setIsLoading(true);
    setLoadError(false);
    try {
      const data = await apiClient.get<{ items: TestCase[] }>(
        `/projects/${project.id}/test-cases?status_filter=approved`,
      );
      setCases(data.items);
    } catch {
      setLoadError(true);
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.id]);

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAll() {
    setSelected((prev) => (prev.size === cases.length ? new Set() : new Set(cases.map((c) => c.id))));
  }

  async function handleStart() {
    setCreateError(null);
    try {
      const run = await create.mutateAsync(Array.from(selected));
      router.push(`/projects/${project.id}/test-runs/${run.id}`);
    } catch (err) {
      setCreateError(createErrorMessage(err));
    }
  }

  if (isLoading) {
    return <LoadingState variant="cards" rows={4} />;
  }

  if (loadError) {
    return <ErrorState onRetry={load} />;
  }

  if (cases.length === 0) {
    return (
      <EmptyState
        icon={CheckSquare}
        title="No approved test cases"
        description="Approve at least one test case in the library before starting a run."
      />
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-subheading font-semibold text-foreground">Start a test run</h2>
          <p className="mt-1 text-body text-muted-foreground">
            Select approved test cases to run against {project.url}.
          </p>
        </div>
        <Button onClick={handleStart} loading={create.isPending} disabled={selected.size === 0}>
          <Play className="h-4 w-4" aria-hidden="true" />
          Start run ({selected.size})
        </Button>
      </div>

      {createError && (
        <p role="alert" className="text-caption text-destructive">
          {createError}
        </p>
      )}

      <Card>
        <CardContent className="flex flex-col gap-0 divide-y divide-border pt-4">
          <label className="flex items-center gap-3 pb-3">
            <input
              type="checkbox"
              checked={selected.size === cases.length}
              onChange={toggleAll}
              className="h-4 w-4 rounded border-border"
              aria-label="Select all approved test cases"
            />
            <span className="text-caption font-medium text-muted-foreground">
              Select all ({cases.length})
            </span>
          </label>
          {cases.map((testCase) => (
            <label key={testCase.id} className="flex cursor-pointer items-center gap-3 py-3">
              <input
                type="checkbox"
                checked={selected.has(testCase.id)}
                onChange={() => toggle(testCase.id)}
                className="h-4 w-4 rounded border-border"
              />
              <span className="flex-1 text-body text-foreground">{testCase.title}</span>
              <span
                className={cn(
                  "inline-flex items-center rounded-full px-2 py-0.5 text-caption font-medium capitalize",
                  "bg-priority-low-bg text-priority-low",
                  testCase.priority === "medium" && "bg-priority-medium-bg text-priority-medium",
                  testCase.priority === "high" && "bg-priority-high-bg text-priority-high",
                  testCase.priority === "critical" && "bg-priority-critical-bg text-priority-critical",
                )}
              >
                {testCase.priority}
              </span>
            </label>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
