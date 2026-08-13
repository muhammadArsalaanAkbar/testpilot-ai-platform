"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Button } from "@/components/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/Card";
import { TextField } from "@/components/form/TextField";
import { URLField } from "@/components/form/URLField";
import { apiClient, ApiError } from "@/lib/api-client";

interface Project {
  id: string;
}

export default function NewProjectPage() {
  const router = useRouter();

  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const project = await apiClient.post<Project>("/projects", { name, url });
      router.push(`/projects/${project.id}`);
    } catch (err) {
      if (err instanceof ApiError && err.code === "invalid_url") {
        setError("Enter a valid http:// or https:// URL.");
      } else if (err instanceof ApiError && err.code === "url_not_public") {
        setError("That URL resolves to a private or internal address and can't be used.");
      } else if (err instanceof ApiError && err.code === "plan_limit_exceeded") {
        setError("You've reached your plan's project limit. Archive a project or upgrade to add another.");
      } else {
        setError("Something went wrong. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-xl flex-col gap-6">
      <h1 className="text-heading font-semibold text-foreground">New project</h1>
      <Card>
        <CardHeader>
          <CardTitle>Project details</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <TextField label="Name" required value={name} onChange={(e) => setName(e.target.value)} />
            <URLField
              label="Target URL"
              required
              value={url}
              onChange={setUrl}
              hint="The public website you want to test."
            />
            {error && (
              <p role="alert" className="text-caption text-destructive">
                {error}
              </p>
            )}
            <Button type="submit" loading={submitting} disabled={!name || !url} className="self-start">
              Create project
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
