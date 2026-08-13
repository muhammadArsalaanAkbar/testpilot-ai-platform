"use client";

import { PlayCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/Card";
import { EmptyState } from "@/components/states/EmptyState";
import { useProjectContext } from "./project-context";

/** Testing history (FR-030) — an explicit empty state until Phase 11 (test
 * runs) exists, not placeholder/sample data (FR-022). */
export default function ProjectDetailPage() {
  const { project } = useProjectContext();

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Project info</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-4 text-body sm:grid-cols-2">
          <div>
            <p className="text-caption text-muted-foreground">Name</p>
            <p className="text-foreground">{project.name}</p>
          </div>
          <div>
            <p className="text-caption text-muted-foreground">Target URL</p>
            <p className="text-foreground">{project.url}</p>
          </div>
          <div>
            <p className="text-caption text-muted-foreground">Status</p>
            <p className="capitalize text-foreground">{project.status}</p>
          </div>
          <div>
            <p className="text-caption text-muted-foreground">Created</p>
            <p className="text-foreground">{new Date(project.created_at).toLocaleDateString()}</p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Testing history</CardTitle>
        </CardHeader>
        <CardContent>
          <EmptyState
            icon={PlayCircle}
            title="No test runs yet"
            description="Test runs and their outcomes will appear here once you generate and execute test cases."
          />
        </CardContent>
      </Card>
    </div>
  );
}
