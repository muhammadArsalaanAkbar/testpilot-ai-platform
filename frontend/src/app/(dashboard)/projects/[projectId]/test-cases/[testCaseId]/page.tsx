"use client";

import { PlayCircle } from "lucide-react";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Button } from "@/components/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/Card";
import { Select } from "@/components/form/Select";
import { TagInput } from "@/components/form/TagInput";
import { TextField } from "@/components/form/TextField";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { LoadingState } from "@/components/states/LoadingState";
import { TestStepEditor, type TestStepDraft } from "@/components/TestStepEditor";
import { useToast } from "@/components/Toast";
import { apiClient } from "@/lib/api-client";
import { cn } from "@/lib/cn";
import { useProjectContext } from "../../project-context";

interface TestStep {
  order_index: number;
  action_type: TestStepDraft["action_type"];
  target_descriptor: string | null;
  input_value: string | null;
  expected_assertion: string | null;
}

interface TestCase {
  id: string;
  title: string;
  description: string;
  priority: "low" | "medium" | "high" | "critical";
  severity: "minor" | "major" | "critical" | "blocker";
  status: "draft" | "approved" | "rejected";
  source: "ai_generated" | "manual";
  tags: string[];
  last_result: "passed" | "failed" | "skipped" | "not_run";
}

interface TestCaseDetail {
  test_case: TestCase;
  steps: TestStep[];
  recent_results: unknown[];
}

const PRIORITY_OPTIONS = [
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
  { value: "critical", label: "Critical" },
];

const SEVERITY_OPTIONS = [
  { value: "minor", label: "Minor" },
  { value: "major", label: "Major" },
  { value: "critical", label: "Critical" },
  { value: "blocker", label: "Blocker" },
];

function statusTone(status: TestCase["status"]) {
  if (status === "approved") return "bg-status-passed-bg text-status-passed";
  if (status === "rejected") return "bg-status-failed-bg text-status-failed";
  return "bg-muted text-muted-foreground";
}

export default function TestCaseDetailPage() {
  const params = useParams<{ testCaseId: string }>();
  const { project } = useProjectContext();
  const { showToast } = useToast();
  const testCaseId = params.testCaseId;

  const [detail, setDetail] = useState<TestCaseDetail | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState("medium");
  const [severity, setSeverity] = useState("major");
  const [tags, setTags] = useState<string[]>([]);
  const [steps, setSteps] = useState<TestStepDraft[]>([]);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [reviewing, setReviewing] = useState(false);

  const load = useCallback(async () => {
    setIsLoading(true);
    setLoadError(false);
    try {
      const data = await apiClient.get<TestCaseDetail>(`/projects/${project.id}/test-cases/${testCaseId}`);
      setDetail(data);
      setTitle(data.test_case.title);
      setDescription(data.test_case.description);
      setPriority(data.test_case.priority);
      setSeverity(data.test_case.severity);
      setTags(data.test_case.tags);
      setSteps(
        data.steps.map((step) => ({
          action_type: step.action_type,
          target_descriptor: step.target_descriptor ?? "",
          input_value: step.input_value ?? "",
          expected_assertion: step.expected_assertion ?? "",
        })),
      );
    } catch {
      setLoadError(true);
    } finally {
      setIsLoading(false);
    }
  }, [project.id, testCaseId]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSaveError(null);
    setSaving(true);
    try {
      await apiClient.patch(`/projects/${project.id}/test-cases/${testCaseId}`, {
        title,
        description,
        priority,
        severity,
        tags,
        steps: steps.map((step) => ({
          action_type: step.action_type,
          target_descriptor: step.target_descriptor || null,
          input_value: step.input_value || null,
          expected_assertion: step.expected_assertion || null,
        })),
      });
      await load();
      showToast({ variant: "success", title: "Test case updated" });
    } catch {
      setSaveError("Something went wrong. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  async function handleReview(action: "approve" | "reject") {
    setReviewing(true);
    try {
      await apiClient.post(`/projects/${project.id}/test-cases/${testCaseId}/${action}`);
      await load();
      showToast({ variant: "success", title: action === "approve" ? "Test case approved" : "Test case rejected" });
    } catch {
      showToast({ variant: "error", title: "Something went wrong. Please try again." });
    } finally {
      setReviewing(false);
    }
  }

  if (isLoading) {
    return <LoadingState variant="detail" />;
  }

  if (loadError || !detail) {
    return <ErrorState onRetry={load} />;
  }

  const { test_case: testCase } = detail;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h2 className="text-subheading font-semibold text-foreground">{testCase.title}</h2>
          <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-caption font-medium capitalize", statusTone(testCase.status))}>
            {testCase.status}
          </span>
          <span className="text-caption text-muted-foreground capitalize">{testCase.source.replace("_", " ")}</span>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            loading={reviewing}
            disabled={testCase.status === "approved"}
            onClick={() => handleReview("approve")}
          >
            Approve
          </Button>
          <Button
            variant="outline"
            loading={reviewing}
            disabled={testCase.status === "rejected"}
            onClick={() => handleReview("reject")}
          >
            Reject
          </Button>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Details</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <TextField label="Title" required value={title} onChange={(e) => setTitle(e.target.value)} />
            <TextField label="Description" required value={description} onChange={(e) => setDescription(e.target.value)} />
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Select label="Priority" options={PRIORITY_OPTIONS} value={priority} onChange={(e) => setPriority(e.target.value)} />
              <Select label="Severity" options={SEVERITY_OPTIONS} value={severity} onChange={(e) => setSeverity(e.target.value)} />
            </div>
            <TagInput label="Tags" value={tags} onChange={setTags} placeholder="Add a tag and press Enter" />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Steps</CardTitle>
          </CardHeader>
          <CardContent>
            <TestStepEditor value={steps} onChange={setSteps} />
          </CardContent>
        </Card>

        {saveError && (
          <p role="alert" className="text-caption text-destructive">
            {saveError}
          </p>
        )}

        <Button type="submit" loading={saving} className="self-start">
          Save changes
        </Button>
      </form>

      <Card>
        <CardHeader>
          <CardTitle>Recent results</CardTitle>
        </CardHeader>
        <CardContent>
          <EmptyState
            icon={PlayCircle}
            title="No results yet"
            description="This test case hasn't been executed in a run yet."
          />
        </CardContent>
      </Card>
    </div>
  );
}
