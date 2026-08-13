"use client";

import { Bug, Plus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { IssueStatusBadge, type IssueStatus } from "@/components/badges/IssueStatusBadge";
import { PriorityBadge, type Priority } from "@/components/badges/PriorityBadge";
import { SeverityBadge, type Severity } from "@/components/badges/SeverityBadge";
import { Button } from "@/components/Button";
import { DataTable, type DataTableColumn } from "@/components/DataTable";
import { Select } from "@/components/form/Select";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { apiClient } from "@/lib/api-client";
import { useProjectContext } from "../project-context";

interface Issue {
  id: string;
  title: string;
  severity: Severity;
  priority: Priority;
  status: IssueStatus;
  created_at: string;
}

const STATUS_OPTIONS = [
  { value: "", label: "Any status" },
  { value: "open", label: "Open" },
  { value: "in_progress", label: "In Progress" },
  { value: "resolved", label: "Resolved" },
  { value: "closed", label: "Closed" },
  { value: "wont_fix", label: "Won't Fix" },
];

const SEVERITY_OPTIONS = [
  { value: "", label: "Any severity" },
  { value: "minor", label: "Minor" },
  { value: "major", label: "Major" },
  { value: "critical", label: "Critical" },
  { value: "blocker", label: "Blocker" },
];

const PRIORITY_OPTIONS = [
  { value: "", label: "Any priority" },
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
  { value: "critical", label: "Critical" },
];

const COLUMNS: DataTableColumn<Issue>[] = [
  { key: "title", header: "Title", render: (i) => i.title, sortable: true, sortValue: (i) => i.title },
  { key: "status", header: "Status", render: (i) => <IssueStatusBadge status={i.status} /> },
  { key: "severity", header: "Severity", render: (i) => <SeverityBadge severity={i.severity} />, hideOnMobile: true },
  { key: "priority", header: "Priority", render: (i) => <PriorityBadge priority={i.priority} />, hideOnMobile: true },
  {
    key: "created_at",
    header: "Created",
    render: (i) => new Date(i.created_at).toLocaleDateString(),
    sortable: true,
    sortValue: (i) => i.created_at,
    hideOnMobile: true,
  },
];

export default function IssuesListPage() {
  const router = useRouter();
  const { project } = useProjectContext();

  const [status, setStatus] = useState("");
  const [severity, setSeverity] = useState("");
  const [priority, setPriority] = useState("");

  const [issues, setIssues] = useState<Issue[]>([]);
  const [hasAnyIssues, setHasAnyIssues] = useState<boolean | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  async function load() {
    setIsLoading(true);
    setLoadError(false);
    try {
      const params = new URLSearchParams();
      if (status) params.set("status", status);
      if (severity) params.set("severity", severity);
      if (priority) params.set("priority", priority);

      const data = await apiClient.get<{ items: Issue[] }>(`/projects/${project.id}/issues?${params.toString()}`);
      setIssues(data.items);
      if (hasAnyIssues === null) {
        setHasAnyIssues(data.items.length > 0);
      }
    } catch {
      setLoadError(true);
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, severity, priority]);

  if (loadError) {
    return <ErrorState onRetry={load} />;
  }

  if (!isLoading && hasAnyIssues === false) {
    return (
      <div className="flex flex-col gap-6">
        <div className="flex items-center justify-between">
          <h2 className="text-subheading font-semibold text-foreground">Issues</h2>
        </div>
        <EmptyState
          icon={Bug}
          title="No issues yet"
          description="File an issue manually, or create one from a failed test result."
          action={
            <Button asChild>
              <Link href={`/projects/${project.id}/issues/new`}>
                <Plus className="h-4 w-4" aria-hidden="true" />
                New issue
              </Link>
            </Button>
          }
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h2 className="text-subheading font-semibold text-foreground">Issues</h2>
        <Button asChild>
          <Link href={`/projects/${project.id}/issues/new`}>
            <Plus className="h-4 w-4" aria-hidden="true" />
            New issue
          </Link>
        </Button>
      </div>

      <DataTable
        columns={COLUMNS}
        data={issues}
        getRowKey={(i) => i.id}
        isLoading={isLoading}
        onRowClick={(i) => router.push(`/projects/${project.id}/issues/${i.id}`)}
        filters={
          <div className="flex flex-wrap items-end gap-2">
            <Select label="Status" options={STATUS_OPTIONS} value={status} onChange={(e) => setStatus(e.target.value)} />
            <Select
              label="Severity"
              options={SEVERITY_OPTIONS}
              value={severity}
              onChange={(e) => setSeverity(e.target.value)}
            />
            <Select
              label="Priority"
              options={PRIORITY_OPTIONS}
              value={priority}
              onChange={(e) => setPriority(e.target.value)}
            />
          </div>
        }
      />
    </div>
  );
}
