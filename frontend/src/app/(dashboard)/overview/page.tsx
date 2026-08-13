"use client";

import { AlertOctagon, CheckCircle2, FolderKanban, PlayCircle, Plus } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/Button";
import { EmptyState } from "@/components/states/EmptyState";
import { LoadingState } from "@/components/states/LoadingState";
import { StatCard } from "@/components/StatCard";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth";

interface Project {
  id: string;
  status: "active" | "archived";
}

/**
 * Overview (FR-021, FR-022): summarizes active projects, recent test run
 * activity, and outstanding critical issues at a glance. Test-run/pass-rate/
 * issue metrics stay at their placeholder "—"/0 shape until Phase 11+
 * builds those domains — only the active-project count reflects real data
 * so far, which is what FR-022 requires today (real data or an explicit
 * empty state, never sample content), not a claim that every metric here
 * is already live.
 */
export default function OverviewPage() {
  const { organization } = useAuth();
  const [projects, setProjects] = useState<Project[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiClient
      .get<{ items: Project[] }>("/projects")
      .then((data) => {
        if (!cancelled) setProjects(data.items);
      })
      .catch(() => {
        if (!cancelled) setProjects([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const activeCount = projects?.filter((p) => p.status === "active").length ?? 0;
  const hasProjects = (projects?.length ?? 0) > 0;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-heading font-semibold text-foreground">Overview</h1>
        <p className="mt-1 text-body text-muted-foreground">
          {organization ? `${organization.name}'s testing activity at a glance.` : "Loading..."}
        </p>
      </div>

      {projects === null ? (
        <LoadingState variant="cards" rows={4} />
      ) : hasProjects ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Active projects" value={activeCount} icon={FolderKanban} />
          <StatCard label="Test runs this week" value="—" icon={PlayCircle} />
          <StatCard label="Pass rate" value="—" icon={CheckCircle2} />
          <StatCard label="Critical issues" value="—" icon={AlertOctagon} />
        </div>
      ) : (
        <EmptyState
          icon={FolderKanban}
          title="No projects yet"
          description="Create your first project to get AI-generated test cases and start testing your website."
          action={
            <Button asChild>
              <Link href="/projects/new">
                <Plus className="h-4 w-4" aria-hidden="true" />
                Create your first project
              </Link>
            </Button>
          }
        />
      )}
    </div>
  );
}
