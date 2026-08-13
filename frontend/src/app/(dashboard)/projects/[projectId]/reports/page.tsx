"use client";

import { AlertTriangle, CheckCircle2, ListChecks, Percent, XCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { StatusBadge, type TestStatus } from "@/components/badges/StatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/Card";
import { DataTable, type DataTableColumn } from "@/components/DataTable";
import { StatCard } from "@/components/StatCard";
import { ErrorState } from "@/components/states/ErrorState";
import { LoadingState } from "@/components/states/LoadingState";
import { apiClient } from "@/lib/api-client";
import { useProjectContext } from "../project-context";

interface ReportSummary {
  total: number;
  passed: number;
  failed: number;
  skipped: number;
  pass_percentage: number;
  failure_percentage: number;
  coverage_percentage: number;
}

interface IssuesBySeverity {
  minor: number;
  major: number;
  critical: number;
  blocker: number;
}

interface TestRunSummary {
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

const SEVERITY_COLORS: Record<keyof IssuesBySeverity, string> = {
  minor: "hsl(var(--color-severity-minor))",
  major: "hsl(var(--color-severity-major))",
  critical: "hsl(var(--color-severity-critical))",
  blocker: "hsl(var(--color-severity-blocker))",
};

const RUN_HISTORY_COLUMNS: DataTableColumn<TestRunSummary>[] = [
  { key: "status", header: "Status", render: (r) => <StatusBadge status={r.status as TestStatus} /> },
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

/**
 * Project Reports page (FR-104-FR-107, FR-110, UX-009): StatCards for the
 * headline numbers, a severity breakdown chart, and a run-history table —
 * everything computed on-read by reports/service.py from the project's
 * actual test_runs/test_results/issues, never sample data.
 */
export default function ReportsPage() {
  const router = useRouter();
  const { project } = useProjectContext();

  const [summary, setSummary] = useState<ReportSummary | null>(null);
  const [bySeverity, setBySeverity] = useState<IssuesBySeverity | null>(null);
  const [runHistory, setRunHistory] = useState<TestRunSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  async function load() {
    setIsLoading(true);
    setLoadError(false);
    try {
      const [summaryData, severityData, runHistoryData] = await Promise.all([
        apiClient.get<ReportSummary>(`/projects/${project.id}/reports/summary`),
        apiClient.get<IssuesBySeverity>(`/projects/${project.id}/reports/issues-by-severity`),
        apiClient.get<{ items: TestRunSummary[] }>(`/projects/${project.id}/reports/run-history`),
      ]);
      setSummary(summaryData);
      setBySeverity(severityData);
      setRunHistory(runHistoryData.items);
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

  if (isLoading) {
    return <LoadingState variant="detail" />;
  }

  if (loadError || !summary || !bySeverity) {
    return <ErrorState onRetry={load} />;
  }

  const severityData = (Object.keys(SEVERITY_COLORS) as (keyof IssuesBySeverity)[]).map((severity) => ({
    severity: severity.charAt(0).toUpperCase() + severity.slice(1),
    count: bySeverity[severity],
    color: SEVERITY_COLORS[severity],
  }));

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-subheading font-semibold text-foreground">Reports</h2>
        <p className="mt-1 text-caption text-muted-foreground">
          Testing health for the last 30 days: totals, pass rate, coverage, and open issues.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
        <StatCard label="Total results" value={summary.total} icon={ListChecks} />
        <StatCard label="Passed" value={summary.passed} icon={CheckCircle2} />
        <StatCard label="Failed" value={summary.failed} icon={XCircle} />
        <StatCard label="Skipped" value={summary.skipped} icon={AlertTriangle} />
        <StatCard label="Pass rate" value={`${summary.pass_percentage.toFixed(1)}%`} icon={Percent} />
        <StatCard label="Coverage" value={`${summary.coverage_percentage.toFixed(1)}%`} icon={Percent} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Issues by severity</CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={severityData}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                <XAxis dataKey="severity" tick={{ fontSize: 12 }} stroke="currentColor" className="text-muted-foreground" />
                <YAxis allowDecimals={false} tick={{ fontSize: 12 }} stroke="currentColor" className="text-muted-foreground" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "hsl(var(--color-card))",
                    border: "1px solid hsl(var(--color-border))",
                    borderRadius: "var(--radius-md, 6px)",
                  }}
                />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {severityData.map((entry) => (
                    <Cell key={entry.severity} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          {/* The chart's counts aren't otherwise exposed as text (SVG bars
              carry no accessible content) — this list makes them available
              to screen readers and gives an unambiguous DOM assertion
              target, without duplicating anything visually. */}
          <ul className="sr-only">
            {severityData.map((entry) => (
              <li key={entry.severity}>
                {entry.severity}: {entry.count}
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Run history</CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <DataTable
            columns={RUN_HISTORY_COLUMNS}
            data={runHistory}
            getRowKey={(r) => r.id}
            onRowClick={(r) => router.push(`/projects/${project.id}/test-runs/${r.id}`)}
          />
        </CardContent>
      </Card>
    </div>
  );
}
