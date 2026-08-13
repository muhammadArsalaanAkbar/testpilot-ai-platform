"use client";

import { ClipboardList, Plus, Sparkles } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button } from "@/components/Button";
import { DataTable, type DataTableColumn } from "@/components/DataTable";
import { Select } from "@/components/form/Select";
import { TextField } from "@/components/form/TextField";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { apiClient } from "@/lib/api-client";
import { cn } from "@/lib/cn";
import { useProjectContext } from "../project-context";

interface TestCase {
  id: string;
  title: string;
  priority: "low" | "medium" | "high" | "critical";
  severity: "minor" | "major" | "critical" | "blocker";
  status: "draft" | "approved" | "rejected";
  source: "ai_generated" | "manual";
  tags: string[];
  last_result: "passed" | "failed" | "skipped" | "not_run";
  updated_at: string;
}

const STATUS_OPTIONS = [
  { value: "", label: "Any status" },
  { value: "draft", label: "Draft" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
];

const PRIORITY_OPTIONS = [
  { value: "", label: "Any priority" },
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
  { value: "critical", label: "Critical" },
];

const SEVERITY_OPTIONS = [
  { value: "", label: "Any severity" },
  { value: "minor", label: "Minor" },
  { value: "major", label: "Major" },
  { value: "critical", label: "Critical" },
  { value: "blocker", label: "Blocker" },
];

const SOURCE_OPTIONS = [
  { value: "", label: "Any source" },
  { value: "manual", label: "Manual" },
  { value: "ai_generated", label: "AI-generated" },
];

const SORT_OPTIONS = [
  { value: "-updated_at", label: "Last updated (newest)" },
  { value: "updated_at", label: "Last updated (oldest)" },
  { value: "-priority", label: "Priority (high to low)" },
  { value: "priority", label: "Priority (low to high)" },
  { value: "-severity", label: "Severity (high to low)" },
  { value: "severity", label: "Severity (low to high)" },
  { value: "status", label: "Status" },
];

function Pill({ text, tone }: { text: string; tone: "neutral" | "positive" | "negative" }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-caption font-medium capitalize",
        tone === "positive" && "bg-status-passed-bg text-status-passed",
        tone === "negative" && "bg-status-failed-bg text-status-failed",
        tone === "neutral" && "bg-muted text-muted-foreground",
      )}
    >
      {text}
    </span>
  );
}

const COLUMNS: DataTableColumn<TestCase>[] = [
  { key: "title", header: "Title", render: (c) => c.title, sortable: true, sortValue: (c) => c.title },
  { key: "priority", header: "Priority", render: (c) => <span className="capitalize">{c.priority}</span> },
  { key: "severity", header: "Severity", render: (c) => <span className="capitalize">{c.severity}</span>, hideOnMobile: true },
  {
    key: "status",
    header: "Status",
    render: (c) => (
      <Pill text={c.status} tone={c.status === "approved" ? "positive" : c.status === "rejected" ? "negative" : "neutral"} />
    ),
  },
  { key: "source", header: "Source", render: (c) => <span className="capitalize">{c.source.replace("_", " ")}</span>, hideOnMobile: true },
  {
    key: "tags",
    header: "Tags",
    render: (c) => (c.tags.length > 0 ? c.tags.join(", ") : "—"),
    hideOnMobile: true,
  },
];

export default function TestCaseLibraryPage() {
  const router = useRouter();
  const { project } = useProjectContext();

  const [status, setStatus] = useState("");
  const [priority, setPriority] = useState("");
  const [severity, setSeverity] = useState("");
  const [source, setSource] = useState("");
  const [tag, setTag] = useState("");
  const [q, setQ] = useState("");
  const [sort, setSort] = useState("-updated_at");

  const [cases, setCases] = useState<TestCase[]>([]);
  const [hasAnyCases, setHasAnyCases] = useState<boolean | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  async function load() {
    setIsLoading(true);
    setLoadError(false);
    try {
      const params = new URLSearchParams();
      if (status) params.set("status_filter", status);
      if (priority) params.set("priority", priority);
      if (severity) params.set("severity", severity);
      if (source) params.set("source", source);
      if (tag) params.set("tag", tag);
      if (q) params.set("q", q);
      if (sort) params.set("sort", sort);

      const data = await apiClient.get<{ items: TestCase[] }>(
        `/projects/${project.id}/test-cases?${params.toString()}`,
      );
      setCases(data.items);
      if (hasAnyCases === null) {
        setHasAnyCases(data.items.length > 0);
      }
    } catch {
      setLoadError(true);
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    const timeout = setTimeout(load, q ? 300 : 0);
    return () => clearTimeout(timeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, priority, severity, source, tag, q, sort]);

  if (loadError) {
    return <ErrorState onRetry={load} />;
  }

  if (!isLoading && hasAnyCases === false) {
    return (
      <div className="flex flex-col gap-6">
        <div className="flex items-center justify-between">
          <h2 className="text-subheading font-semibold text-foreground">Test cases</h2>
        </div>
        <EmptyState
          icon={ClipboardList}
          title="No test cases yet"
          description="Manually create a test case, or let AI generate a set for you to review."
          action={
            <div className="flex gap-2">
              <Button asChild variant="outline">
                <Link href={`/projects/${project.id}/test-cases/new`}>
                  <Plus className="h-4 w-4" aria-hidden="true" />
                  Create a test case
                </Link>
              </Button>
              <Button asChild>
                <Link href={`/projects/${project.id}/test-cases/generate`}>
                  <Sparkles className="h-4 w-4" aria-hidden="true" />
                  Generate with AI
                </Link>
              </Button>
            </div>
          }
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h2 className="text-subheading font-semibold text-foreground">Test cases</h2>
        <div className="flex gap-2">
          <Button asChild variant="outline">
            <Link href={`/projects/${project.id}/test-cases/new`}>
              <Plus className="h-4 w-4" aria-hidden="true" />
              New test case
            </Link>
          </Button>
          <Button asChild>
            <Link href={`/projects/${project.id}/test-cases/generate`}>
              <Sparkles className="h-4 w-4" aria-hidden="true" />
              Generate with AI
            </Link>
          </Button>
        </div>
      </div>

      <DataTable
        columns={COLUMNS}
        data={cases}
        getRowKey={(c) => c.id}
        isLoading={isLoading}
        onRowClick={(c) => router.push(`/projects/${project.id}/test-cases/${c.id}`)}
        filters={
          <div className="flex flex-wrap items-end gap-2">
            <TextField label="Search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search title, description, steps..." />
            <TextField label="Tag" value={tag} onChange={(e) => setTag(e.target.value)} placeholder="e.g. checkout" />
            <Select label="Status" options={STATUS_OPTIONS} value={status} onChange={(e) => setStatus(e.target.value)} />
            <Select label="Priority" options={PRIORITY_OPTIONS} value={priority} onChange={(e) => setPriority(e.target.value)} />
            <Select label="Severity" options={SEVERITY_OPTIONS} value={severity} onChange={(e) => setSeverity(e.target.value)} />
            <Select label="Source" options={SOURCE_OPTIONS} value={source} onChange={(e) => setSource(e.target.value)} />
            <Select label="Sort" options={SORT_OPTIONS} value={sort} onChange={(e) => setSort(e.target.value)} />
          </div>
        }
      />
    </div>
  );
}
