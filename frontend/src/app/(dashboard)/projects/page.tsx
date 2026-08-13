"use client";

import { FolderKanban, Plus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button } from "@/components/Button";
import { DataTable, type DataTableColumn } from "@/components/DataTable";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { apiClient } from "@/lib/api-client";
import { cn } from "@/lib/cn";

interface Project {
  id: string;
  name: string;
  url: string;
  status: "active" | "archived";
  created_at: string;
}

function StatusPill({ status }: { status: Project["status"] }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-caption font-medium capitalize",
        status === "active" ? "bg-status-passed-bg text-status-passed" : "bg-muted text-muted-foreground",
      )}
    >
      {status}
    </span>
  );
}

const COLUMNS: DataTableColumn<Project>[] = [
  { key: "name", header: "Name", render: (p) => p.name, sortable: true, sortValue: (p) => p.name },
  {
    key: "url",
    header: "URL",
    render: (p) => p.url,
    hideOnMobile: true,
  },
  { key: "status", header: "Status", render: (p) => <StatusPill status={p.status} /> },
];

export default function ProjectsListPage() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loadError, setLoadError] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  async function load() {
    setIsLoading(true);
    setLoadError(false);
    try {
      const data = await apiClient.get<{ items: Project[] }>("/projects");
      setProjects(data.items);
    } catch {
      setLoadError(true);
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  if (loadError) {
    return <ErrorState onRetry={load} />;
  }

  if (!isLoading && projects.length === 0) {
    return (
      <div className="flex flex-col gap-6">
        <div className="flex items-center justify-between">
          <h1 className="text-heading font-semibold text-foreground">Projects</h1>
        </div>
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
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-heading font-semibold text-foreground">Projects</h1>
        <Button asChild>
          <Link href="/projects/new">
            <Plus className="h-4 w-4" aria-hidden="true" />
            New project
          </Link>
        </Button>
      </div>
      <DataTable
        columns={COLUMNS}
        data={projects}
        getRowKey={(p) => p.id}
        isLoading={isLoading}
        searchPlaceholder="Search projects..."
        searchValue={(p) => `${p.name} ${p.url}`}
        onRowClick={(p) => router.push(`/projects/${p.id}`)}
      />
    </div>
  );
}
