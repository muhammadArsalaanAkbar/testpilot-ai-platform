"use client";

import { usePathname, useParams } from "next/navigation";
import Link from "next/link";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { ErrorState } from "@/components/states/ErrorState";
import { LoadingState } from "@/components/states/LoadingState";
import { apiClient } from "@/lib/api-client";
import { cn } from "@/lib/cn";
import { ProjectContext, type ProjectDetail } from "./project-context";

export default function ProjectLayout({ children }: { children: ReactNode }) {
  const params = useParams<{ projectId: string }>();
  const pathname = usePathname();
  const projectId = params.projectId;

  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  const load = useCallback(async () => {
    setIsLoading(true);
    setLoadError(false);
    try {
      const data = await apiClient.get<{ project: ProjectDetail }>(`/projects/${projectId}`);
      setProject(data.project);
    } catch {
      setLoadError(true);
    } finally {
      setIsLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    load();
  }, [load]);

  if (isLoading) {
    return <LoadingState variant="detail" />;
  }

  if (loadError || !project) {
    return <ErrorState onRetry={load} />;
  }

  const tabs = [
    { href: `/projects/${projectId}`, label: "Overview" },
    { href: `/projects/${projectId}/test-cases`, label: "Test cases" },
    { href: `/projects/${projectId}/test-runs`, label: "Test runs" },
    { href: `/projects/${projectId}/issues`, label: "Issues" },
    { href: `/projects/${projectId}/reports`, label: "Reports" },
    { href: `/projects/${projectId}/settings`, label: "Settings" },
  ];

  return (
    <ProjectContext.Provider value={{ project, refresh: load }}>
      <div className="flex flex-col gap-6">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-heading font-semibold text-foreground">{project.name}</h1>
            <span
              className={cn(
                "inline-flex items-center rounded-full px-2 py-0.5 text-caption font-medium capitalize",
                project.status === "active"
                  ? "bg-status-passed-bg text-status-passed"
                  : "bg-muted text-muted-foreground",
              )}
            >
              {project.status}
            </span>
          </div>
          <a
            href={project.url}
            target="_blank"
            rel="noreferrer noopener"
            className="text-body text-muted-foreground hover:text-foreground hover:underline"
          >
            {project.url}
          </a>
          <nav aria-label="Project" className="mt-4 flex gap-1 border-b border-border">
            {tabs.map((tab) => {
              const active = tab.href === `/projects/${projectId}` ? pathname === tab.href : pathname.startsWith(tab.href);
              return (
                <Link
                  key={tab.href}
                  href={tab.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "-mb-px border-b-2 px-3 py-2 text-body font-medium",
                    active
                      ? "border-primary text-foreground"
                      : "border-transparent text-muted-foreground hover:text-foreground",
                  )}
                >
                  {tab.label}
                </Link>
              );
            })}
          </nav>
        </div>
        {children}
      </div>
    </ProjectContext.Provider>
  );
}
