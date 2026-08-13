"use client";

import { Play, TestTube2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { StatusBadge, type TestStatus } from "@/components/badges/StatusBadge";
import { Button } from "@/components/Button";
import { DataTable, type DataTableColumn } from "@/components/DataTable";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { apiClient } from "@/lib/api-client";
import { useProjectContext } from "../project-context";

interface TestRun {
  id: string;
  status: "queued" | "running" | "completed" | "error";
  summary_total: number;
  summary_passed: number;
  summary_failed: number;
  summary_skipped: number;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

const COLUMNS: DataTableColumn<TestRun>[] = [
  {
    key: "status",
    header: "Status",
    render: (r) => <StatusBadge status={r.status as TestStatus} />,
  },
  {
    key: "results",
    header: "Results",
    render: (r) => (
      <span className="text-body text-muted-foreground">
        <span className="text-status-passed">{r.summary_passed} passed</span>
        {" · "}
        <span className="text-status-failed">{r.summary_failed} failed</span>
        {" · "}
        <span className="text-status-skipped">{r.summary_skipped} skipped</span>
        {" / "}
        {r.summary_total} total
      </span>
    ),
  },
  {
    key: "created_at",
    header: "Started",
    render: (r) => (r.created_at ? new Date(r.created_at).toLocaleString() : "—"),
    sortable: true,
    sortValue: (r) => r.created_at,
    hideOnMobile: true,
  },
];

export default function TestRunHistoryPage() {
  const router = useRouter();
  const { project } = useProjectContext();

  const [runs, setRuns] = useState<TestRun[]>([]);
  const [hasAnyRuns, setHasAnyRuns] = useState<boolean | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  async function load() {
    setIsLoading(true);
    setLoadError(false);
    try {
      const data = await apiClient.get<{ items: TestRun[] }>(`/projects/${project.id}/test-runs`);
      setRuns(data.items);
      if (hasAnyRuns === null) {
        setHasAnyRuns(data.items.length > 0);
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
  }, [project.id]);

  if (loadError) {
    return <ErrorState onRetry={load} />;
  }

  if (!isLoading && hasAnyRuns === false) {
    return (
      <div className="flex flex-col gap-6">
        <div className="flex items-center justify-between">
          <h2 className="text-subheading font-semibold text-foreground">Test runs</h2>
        </div>
        <EmptyState
          icon={TestTube2}
          title="No test runs yet"
          description="Start a run against your approved test cases to see live progress and results here."
          action={
            <Button asChild>
              <Link href={`/projects/${project.id}/test-runs/new`}>
                <Play className="h-4 w-4" aria-hidden="true" />
                Start a test run
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
        <h2 className="text-subheading font-semibold text-foreground">Test runs</h2>
        <Button asChild>
          <Link href={`/projects/${project.id}/test-runs/new`}>
            <Play className="h-4 w-4" aria-hidden="true" />
            Start a test run
          </Link>
        </Button>
      </div>

      <DataTable
        columns={COLUMNS}
        data={runs}
        getRowKey={(r) => r.id}
        isLoading={isLoading}
        onRowClick={(r) => router.push(`/projects/${project.id}/test-runs/${r.id}`)}
      />
    </div>
  );
}
