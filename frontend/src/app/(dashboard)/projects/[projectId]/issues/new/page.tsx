"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Button } from "@/components/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/Card";
import { Select } from "@/components/form/Select";
import { TextField } from "@/components/form/TextField";
import { apiClient } from "@/lib/api-client";
import { useProjectContext } from "../../project-context";

interface Issue {
  id: string;
}

const SEVERITY_OPTIONS = [
  { value: "minor", label: "Minor" },
  { value: "major", label: "Major" },
  { value: "critical", label: "Critical" },
  { value: "blocker", label: "Blocker" },
];

const PRIORITY_OPTIONS = [
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
  { value: "critical", label: "Critical" },
];

export default function NewIssuePage() {
  const router = useRouter();
  const { project } = useProjectContext();

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [severity, setSeverity] = useState("major");
  const [priority, setPriority] = useState("medium");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const issue = await apiClient.post<Issue>(`/projects/${project.id}/issues`, {
        title,
        description,
        severity,
        priority,
      });
      router.push(`/projects/${project.id}/issues/${issue.id}`);
    } catch {
      setError("Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6">
      <h2 className="text-subheading font-semibold text-foreground">New issue</h2>
      <form onSubmit={handleSubmit} className="flex flex-col gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Details</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <TextField label="Title" required value={title} onChange={(e) => setTitle(e.target.value)} />
            <TextField
              label="Description"
              required
              hint="What went wrong, and how to reproduce it?"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Select label="Severity" options={SEVERITY_OPTIONS} value={severity} onChange={(e) => setSeverity(e.target.value)} />
              <Select label="Priority" options={PRIORITY_OPTIONS} value={priority} onChange={(e) => setPriority(e.target.value)} />
            </div>
          </CardContent>
        </Card>

        {error && (
          <p role="alert" className="text-caption text-destructive">
            {error}
          </p>
        )}

        <Button type="submit" loading={submitting} disabled={!title || !description} className="self-start">
          Create issue
        </Button>
      </form>
    </div>
  );
}
