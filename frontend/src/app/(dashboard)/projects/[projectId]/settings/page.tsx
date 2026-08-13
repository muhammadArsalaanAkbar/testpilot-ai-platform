"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Button } from "@/components/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/Card";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { TextField } from "@/components/form/TextField";
import { URLField } from "@/components/form/URLField";
import { useToast } from "@/components/Toast";
import { apiClient, ApiError } from "@/lib/api-client";
import { useProjectContext } from "../project-context";

export default function ProjectSettingsPage() {
  const router = useRouter();
  const { showToast } = useToast();
  const { project, refresh } = useProjectContext();

  const [name, setName] = useState(project.name);
  const [url, setUrl] = useState(project.url);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [archiving, setArchiving] = useState(false);
  const [archiveDialogOpen, setArchiveDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSaveError(null);
    setSaving(true);
    try {
      await apiClient.patch(`/projects/${project.id}`, { name, url });
      await refresh();
      showToast({ variant: "success", title: "Project updated" });
    } catch (err) {
      if (err instanceof ApiError && err.code === "invalid_url") {
        setSaveError("Enter a valid http:// or https:// URL.");
      } else if (err instanceof ApiError && err.code === "url_not_public") {
        setSaveError("That URL resolves to a private or internal address and can't be used.");
      } else {
        setSaveError("Something went wrong. Please try again.");
      }
    } finally {
      setSaving(false);
    }
  }

  async function handleToggleArchive() {
    setArchiving(true);
    try {
      const endpoint = project.status === "active" ? "archive" : "unarchive";
      await apiClient.post(`/projects/${project.id}/${endpoint}`);
      await refresh();
      showToast({
        variant: "success",
        title: project.status === "active" ? "Project archived" : "Project unarchived",
      });
    } catch {
      showToast({ variant: "error", title: "Something went wrong. Please try again." });
    } finally {
      setArchiving(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Project details</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <TextField label="Name" required value={name} onChange={(e) => setName(e.target.value)} />
            <URLField label="Target URL" required value={url} onChange={setUrl} />
            {saveError && (
              <p role="alert" className="text-caption text-destructive">
                {saveError}
              </p>
            )}
            <Button type="submit" loading={saving} className="self-start">
              Save changes
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card className="border-destructive/30">
        <CardHeader>
          <CardTitle>Danger zone</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-body font-medium text-foreground">
                {project.status === "active" ? "Archive this project" : "Unarchive this project"}
              </p>
              <p className="text-caption text-muted-foreground">
                {project.status === "active"
                  ? "Removes it from the active list while preserving its full history."
                  : "Restores it to the active list."}
              </p>
            </div>
            <Button variant="outline" loading={archiving} onClick={() => setArchiveDialogOpen(true)}>
              {project.status === "active" ? "Archive" : "Unarchive"}
            </Button>
          </div>
          <div className="flex items-center justify-between gap-4 border-t border-border pt-4">
            <div>
              <p className="text-body font-medium text-foreground">Delete this project</p>
              <p className="text-caption text-muted-foreground">
                Permanently deletes the project and all its test data. This cannot be undone.
              </p>
            </div>
            <Button variant="destructive" onClick={() => setDeleteDialogOpen(true)}>
              Delete
            </Button>
          </div>
          {deleteError && (
            <p role="alert" className="text-caption text-destructive">
              {deleteError}
            </p>
          )}
        </CardContent>
      </Card>

      <ConfirmDialog
        open={archiveDialogOpen}
        onOpenChange={setArchiveDialogOpen}
        title={project.status === "active" ? "Archive project?" : "Unarchive project?"}
        description={
          project.status === "active"
            ? `"${project.name}" will be removed from your active project list. Its history is preserved and it remains reachable from the archived view.`
            : `"${project.name}" will be restored to your active project list.`
        }
        confirmLabel={project.status === "active" ? "Archive" : "Unarchive"}
        destructive={project.status === "active"}
        onConfirm={handleToggleArchive}
      />

      <ConfirmDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        title="Delete project?"
        description={`"${project.name}" and all of its test data will be permanently deleted. This action cannot be undone.`}
        confirmLabel="Delete permanently"
        destructive
        onConfirm={async () => {
          setDeleteError(null);
          try {
            await apiClient.deleteWithBody(`/projects/${project.id}`, { confirm: true });
            router.push("/projects");
          } catch {
            // Swallowed (not rethrown): ConfirmDialog closes the dialog once
            // onConfirm resolves either way, and the error below is only
            // visible on the underlying page once the dialog is gone.
            setDeleteError("Something went wrong. Please try again.");
          }
        }}
      />
    </div>
  );
}
