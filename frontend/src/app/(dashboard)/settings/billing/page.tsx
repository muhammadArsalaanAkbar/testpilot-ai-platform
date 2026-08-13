"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/Card";
import { ProgressBar } from "@/components/Progress";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";
import { apiClient } from "@/lib/api-client";
import { cn } from "@/lib/cn";

interface PlanLimits {
  max_projects: number | null;
  max_test_executions_per_period: number | null;
  max_ai_operations_per_period: number | null;
  max_members: number | null;
}

interface UsageSummary {
  projects: number;
  test_executions: number;
  ai_operations: number;
  members: number;
}

interface BillingDetail {
  plan: { tier: string; limits: PlanLimits };
  usage: UsageSummary;
  period: { start: string; end: string };
}

const METRICS: { key: keyof UsageSummary; limitKey: keyof PlanLimits; label: string }[] = [
  { key: "projects", limitKey: "max_projects", label: "Projects" },
  { key: "test_executions", limitKey: "max_test_executions_per_period", label: "Test executions this period" },
  { key: "ai_operations", limitKey: "max_ai_operations_per_period", label: "AI operations this period" },
  { key: "members", limitKey: "max_members", label: "Members" },
];

export default function BillingSettingsPage() {
  const [billing, setBilling] = useState<BillingDetail | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  async function load() {
    setIsLoading(true);
    setLoadError(false);
    try {
      const data = await apiClient.get<BillingDetail>("/organizations/current/billing");
      setBilling(data);
    } catch {
      setLoadError(true);
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  if (isLoading) {
    return <LoadingState variant="detail" />;
  }

  if (loadError || !billing) {
    return <ErrorState onRetry={load} />;
  }

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Plan</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center gap-3">
          <span
            className={cn(
              "inline-flex items-center rounded-full bg-primary/10 px-3 py-1 text-body font-medium capitalize text-primary",
            )}
          >
            {billing.plan.tier}
          </span>
          <span className="text-caption text-muted-foreground">
            Billing period {billing.period.start} – {billing.period.end}
          </span>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Usage vs. limits</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-5">
          {METRICS.map((metric) => {
            const used = billing.usage[metric.key];
            const limit = billing.plan.limits[metric.limitKey];
            return (
              <div key={metric.key} className="flex flex-col gap-1.5">
                <div className="flex items-center justify-between text-body">
                  <span className="text-foreground">{metric.label}</span>
                  <span className="text-muted-foreground">{limit === null ? `${used} / unlimited` : `${used} / ${limit}`}</span>
                </div>
                {limit !== null && <ProgressBar value={used} max={limit} />}
              </div>
            );
          })}
        </CardContent>
      </Card>
    </div>
  );
}
