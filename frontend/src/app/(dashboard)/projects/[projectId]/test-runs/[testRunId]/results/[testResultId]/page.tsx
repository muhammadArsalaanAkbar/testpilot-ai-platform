"use client";

import { AlertCircle, Bug, CheckCircle2, XCircle } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { StatusBadge, type TestStatus } from "@/components/badges/StatusBadge";
import { Button } from "@/components/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/Card";
import { Dialog } from "@/components/Dialog";
import { Select } from "@/components/form/Select";
import { TextField } from "@/components/form/TextField";
import { ScreenshotViewer, type Screenshot } from "@/components/ScreenshotViewer";
import { ErrorState } from "@/components/states/ErrorState";
import { LoadingState } from "@/components/states/LoadingState";
import { AIAnalysisPanel } from "@/features/testruns/AIAnalysisPanel";
import { type AIAnalysis } from "@/features/testruns/useAIAnalysis";
import { apiClient } from "@/lib/api-client";
import { cn } from "@/lib/cn";
import { useProjectContext } from "../../../../project-context";

const SEVERITY_OPTIONS = [
  { value: "minor", label: "Minor" },
  { value: "major", label: "Major" },
  { value: "critical", label: "Critical" },
  { value: "blocker", label: "Blocker" },
];

const PRIORITY_OPTIONS = [
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
  { value: "critical", label: "Critical" },
];

interface StepLogEntry {
  step_index: number;
  action_type: string;
  status: "passed" | "failed";
  message: string | null;
  timestamp: string;
}

interface ArtifactEntry {
  id: string;
  type: "screenshot" | "log";
  url: string | null;
  captured_at: string;
}

interface TestResultDetail {
  test_result: {
    id: string;
    test_run_id: string;
    test_case_id: string;
    status: "passed" | "failed" | "skipped" | "error";
    failure_step_index: number | null;
    error_message: string | null;
    started_at: string;
    completed_at: string;
    duration_ms: number;
  };
  execution_log: StepLogEntry[];
  artifacts: ArtifactEntry[];
  ai_analyses: AIAnalysis[];
}

interface CreatedIssue {
  id: string;
}

export default function TestResultDetailPage() {
  const params = useParams<{ testRunId: string; testResultId: string }>();
  const router = useRouter();
  const { project } = useProjectContext();

  const [data, setData] = useState<TestResultDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [issueDialogOpen, setIssueDialogOpen] = useState(false);
  const [issueSeverity, setIssueSeverity] = useState("major");
  const [issuePriority, setIssuePriority] = useState("high");
  const [issueTitle, setIssueTitle] = useState("");
  const [creatingIssue, setCreatingIssue] = useState(false);
  const [createIssueError, setCreateIssueError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setIsLoading(true);
    setLoadError(false);
    try {
      const result = await apiClient.get<TestResultDetail>(
        `/projects/${project.id}/test-runs/${params.testRunId}/results/${params.testResultId}`,
      );
      setData(result);
    } catch {
      setLoadError(true);
    } finally {
      setIsLoading(false);
    }
  }, [project.id, params.testRunId, params.testResultId]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleCreateIssue() {
    setCreatingIssue(true);
    setCreateIssueError(null);
    try {
      const issue = await apiClient.post<CreatedIssue>(
        `/projects/${project.id}/issues/from-result/${params.testResultId}`,
        {
          severity: issueSeverity,
          priority: issuePriority,
          ...(issueTitle ? { title: issueTitle } : {}),
        },
      );
      router.push(`/projects/${project.id}/issues/${issue.id}`);
    } catch {
      setCreateIssueError("Something went wrong. Please try again.");
    } finally {
      setCreatingIssue(false);
    }
  }

  if (isLoading) {
    return <LoadingState variant="detail" />;
  }

  if (loadError || !data) {
    return <ErrorState onRetry={load} />;
  }

  const { test_result: result, execution_log: executionLog, artifacts } = data;
  const screenshots: Screenshot[] = artifacts
    .filter((a): a is ArtifactEntry & { url: string } => a.type === "screenshot" && a.url !== null)
    .map((a) => ({ id: a.id, url: a.url, capturedAt: a.captured_at }));
  const purgedArtifactCount = artifacts.filter((a) => a.url === null).length;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-subheading font-semibold text-foreground">Test result</h2>
          <p className="mt-1 text-caption text-muted-foreground">
            {new Date(result.started_at).toLocaleString()} · {result.duration_ms}ms
          </p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={result.status as TestStatus} />
          {result.status === "failed" && (
            <Button variant="outline" size="sm" onClick={() => setIssueDialogOpen(true)}>
              <Bug className="h-4 w-4" aria-hidden="true" />
              Create issue
            </Button>
          )}
        </div>
      </div>

      {result.error_message && (
        <Card>
          <CardContent className="flex items-start gap-3 pt-4">
            <AlertCircle className="h-5 w-5 shrink-0 text-destructive" aria-hidden="true" />
            <p className="text-body text-foreground">{result.error_message}</p>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Execution log</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col divide-y divide-border pt-0">
          {executionLog.length === 0 && (
            <p className="py-6 text-center text-body text-muted-foreground">No steps were executed.</p>
          )}
          {executionLog.map((step) => (
            <div
              key={step.step_index}
              className={cn(
                "flex items-start gap-3 py-3",
                step.step_index === result.failure_step_index && "bg-status-failed-bg/40",
              )}
            >
              {step.status === "passed" ? (
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-status-passed" aria-hidden="true" />
              ) : (
                <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-status-failed" aria-hidden="true" />
              )}
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-caption font-medium text-muted-foreground">Step {step.step_index + 1}</span>
                  <span className="text-body capitalize text-foreground">{step.action_type.replace("_", " ")}</span>
                </div>
                {step.message && <p className="mt-0.5 text-caption text-muted-foreground">{step.message}</p>}
              </div>
              <span className="text-caption text-muted-foreground">
                {new Date(step.timestamp).toLocaleTimeString()}
              </span>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Evidence</CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          {screenshots.length === 0 && purgedArtifactCount === 0 && (
            <p className="text-body text-muted-foreground">No screenshots were captured for this result.</p>
          )}
          {purgedArtifactCount > 0 && (
            <p className="mb-3 text-caption text-muted-foreground">
              {purgedArtifactCount} screenshot{purgedArtifactCount > 1 ? "s" : ""} past the retention window{" "}
              {screenshots.length > 0 ? "(no longer viewable)" : "and no longer viewable"}.
            </p>
          )}
          <ScreenshotViewer screenshots={screenshots} />
        </CardContent>
      </Card>

      {result.status === "failed" && (
        <AIAnalysisPanel
          projectId={project.id}
          testRunId={params.testRunId}
          testResultId={params.testResultId}
          initialAnalyses={data.ai_analyses}
        />
      )}

      <Dialog
        open={issueDialogOpen}
        onOpenChange={setIssueDialogOpen}
        title="Create issue from this failure"
        description="Pre-filled from the failure; you can override the title and must set a severity and priority."
        footer={
          <Button onClick={handleCreateIssue} loading={creatingIssue}>
            Create issue
          </Button>
        }
      >
        <div className="flex flex-col gap-4">
          <TextField
            label="Title"
            placeholder="Defaults to a summary of the failure"
            value={issueTitle}
            onChange={(e) => setIssueTitle(e.target.value)}
          />
          <div className="grid grid-cols-2 gap-4">
            <Select
              label="Severity"
              options={SEVERITY_OPTIONS}
              value={issueSeverity}
              onChange={(e) => setIssueSeverity(e.target.value)}
            />
            <Select
              label="Priority"
              options={PRIORITY_OPTIONS}
              value={issuePriority}
              onChange={(e) => setIssuePriority(e.target.value)}
            />
          </div>
          {createIssueError && (
            <p role="alert" className="text-caption text-destructive">
              {createIssueError}
            </p>
          )}
        </div>
      </Dialog>
    </div>
  );
}
