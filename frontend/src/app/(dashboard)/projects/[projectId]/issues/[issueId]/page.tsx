"use client";

import { Paperclip, Pencil } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { IssueStatusBadge, type IssueStatus } from "@/components/badges/IssueStatusBadge";
import { PriorityBadge, type Priority } from "@/components/badges/PriorityBadge";
import { SeverityBadge, type Severity } from "@/components/badges/SeverityBadge";
import { Button } from "@/components/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/Card";
import { Select } from "@/components/form/Select";
import { TextField } from "@/components/form/TextField";
import { ScreenshotViewer, type Screenshot } from "@/components/ScreenshotViewer";
import { ErrorState } from "@/components/states/ErrorState";
import { LoadingState } from "@/components/states/LoadingState";
import { useToast } from "@/components/Toast";
import { apiClient } from "@/lib/api-client";
import { useProjectContext } from "../../project-context";

interface Attachment {
  id: string;
  type: "screenshot" | "log";
  url: string | null;
  created_at: string;
}

interface IssueDetail {
  issue: {
    id: string;
    project_id: string;
    title: string;
    description: string;
    severity: Severity;
    priority: Priority;
    status: IssueStatus;
    source_test_case_id: string | null;
    source_test_run_id: string | null;
    created_at: string;
    updated_at: string;
  };
  attachments: Attachment[];
  source_test_case: { id: string; title: string } | null;
  source_test_run: { id: string; status: string } | null;
}

const STATUS_OPTIONS = [
  { value: "open", label: "Open" },
  { value: "in_progress", label: "In Progress" },
  { value: "resolved", label: "Resolved" },
  { value: "closed", label: "Closed" },
  { value: "wont_fix", label: "Won't Fix" },
];

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

export default function IssueDetailPage() {
  const params = useParams<{ issueId: string }>();
  const { project } = useProjectContext();
  const { showToast } = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [data, setData] = useState<IssueDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [editing, setEditing] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");
  const [descriptionDraft, setDescriptionDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);

  const load = useCallback(async () => {
    setIsLoading(true);
    setLoadError(false);
    try {
      const result = await apiClient.get<IssueDetail>(`/projects/${project.id}/issues/${params.issueId}`);
      setData(result);
    } catch {
      setLoadError(true);
    } finally {
      setIsLoading(false);
    }
  }, [project.id, params.issueId]);

  useEffect(() => {
    load();
  }, [load]);

  async function patchIssue(payload: Record<string, unknown>) {
    setSaving(true);
    try {
      await apiClient.patch(`/projects/${project.id}/issues/${params.issueId}`, payload);
      await load();
      showToast({ variant: "success", title: "Issue updated" });
    } catch {
      showToast({ variant: "error", title: "Failed to update issue" });
    } finally {
      setSaving(false);
    }
  }

  function startEditing() {
    if (!data) return;
    setTitleDraft(data.issue.title);
    setDescriptionDraft(data.issue.description);
    setEditing(true);
  }

  async function saveEdits() {
    await patchIssue({ title: titleDraft, description: descriptionDraft });
    setEditing(false);
  }

  async function handleFileSelected(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("type", file.type.startsWith("image/") ? "screenshot" : "log");
      await apiClient.postMultipart(`/projects/${project.id}/issues/${params.issueId}/attachments`, formData);
      await load();
      showToast({ variant: "success", title: "Attachment added" });
    } catch {
      showToast({ variant: "error", title: "Failed to add attachment" });
    } finally {
      setUploading(false);
    }
  }

  if (isLoading) {
    return <LoadingState variant="detail" />;
  }

  if (loadError || !data) {
    return <ErrorState onRetry={load} />;
  }

  const { issue, attachments, source_test_case: sourceTestCase, source_test_run: sourceTestRun } = data;
  const screenshots: Screenshot[] = attachments
    .filter((a): a is Attachment & { url: string } => a.type === "screenshot" && a.url !== null)
    .map((a) => ({ id: a.id, url: a.url, capturedAt: a.created_at }));
  const logAttachments = attachments.filter((a) => a.type === "log");

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1">
          {editing ? (
            <TextField label="Title" value={titleDraft} onChange={(e) => setTitleDraft(e.target.value)} />
          ) : (
            <h2 className="text-subheading font-semibold text-foreground">{issue.title}</h2>
          )}
          <p className="mt-1 text-caption text-muted-foreground">
            Created {new Date(issue.created_at).toLocaleString()}
          </p>
        </div>
        {!editing && (
          <Button variant="outline" size="sm" onClick={startEditing}>
            <Pencil className="h-4 w-4" aria-hidden="true" />
            Edit
          </Button>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Details</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {editing ? (
            <>
              <TextField
                label="Description"
                value={descriptionDraft}
                onChange={(e) => setDescriptionDraft(e.target.value)}
              />
              <div className="flex gap-2">
                <Button size="sm" onClick={saveEdits} loading={saving}>
                  Save
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
                  Cancel
                </Button>
              </div>
            </>
          ) : (
            <p className="text-body text-foreground">{issue.description}</p>
          )}

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <Select
              label="Status"
              options={STATUS_OPTIONS}
              value={issue.status}
              disabled={saving}
              onChange={(e) => patchIssue({ status: e.target.value })}
            />
            <Select
              label="Severity"
              options={SEVERITY_OPTIONS}
              value={issue.severity}
              disabled={saving}
              onChange={(e) => patchIssue({ severity: e.target.value })}
            />
            <Select
              label="Priority"
              options={PRIORITY_OPTIONS}
              value={issue.priority}
              disabled={saving}
              onChange={(e) => patchIssue({ priority: e.target.value })}
            />
          </div>

          <div className="flex items-center gap-2">
            <IssueStatusBadge status={issue.status} />
            <SeverityBadge severity={issue.severity} />
            <PriorityBadge priority={issue.priority} />
          </div>
        </CardContent>
      </Card>

      {(sourceTestCase || sourceTestRun) && (
        <Card>
          <CardHeader>
            <CardTitle>Source</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            {sourceTestCase && (
              <Link
                href={`/projects/${project.id}/test-cases/${sourceTestCase.id}`}
                className="text-body text-primary hover:underline"
              >
                Test case: {sourceTestCase.title}
              </Link>
            )}
            {sourceTestRun && (
              <Link
                href={`/projects/${project.id}/test-runs/${sourceTestRun.id}`}
                className="text-body text-primary hover:underline"
              >
                Test run ({sourceTestRun.status})
              </Link>
            )}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Attachments</CardTitle>
          <div>
            <input ref={fileInputRef} type="file" className="hidden" onChange={handleFileSelected} />
            <Button variant="outline" size="sm" loading={uploading} onClick={() => fileInputRef.current?.click()}>
              <Paperclip className="h-4 w-4" aria-hidden="true" />
              Attach file
            </Button>
          </div>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {attachments.length === 0 && (
            <p className="text-body text-muted-foreground">No attachments yet.</p>
          )}
          {screenshots.length > 0 && <ScreenshotViewer screenshots={screenshots} />}
          {logAttachments.length > 0 && (
            <ul className="flex flex-col gap-1">
              {logAttachments.map((attachment) => (
                <li key={attachment.id}>
                  {attachment.url ? (
                    <a
                      href={attachment.url}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="text-body text-primary hover:underline"
                    >
                      Log excerpt · {new Date(attachment.created_at).toLocaleString()}
                    </a>
                  ) : (
                    <span className="text-body text-muted-foreground">
                      Log excerpt (no longer viewable) · {new Date(attachment.created_at).toLocaleString()}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
