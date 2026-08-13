"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Button } from "@/components/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/Card";
import { Select } from "@/components/form/Select";
import { TagInput } from "@/components/form/TagInput";
import { TextField } from "@/components/form/TextField";
import { TestStepEditor, type TestStepDraft } from "@/components/TestStepEditor";
import { apiClient, ApiError } from "@/lib/api-client";
import { useProjectContext } from "../../project-context";

interface TestCase {
  id: string;
}

const PRIORITY_OPTIONS = [
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
  { value: "critical", label: "Critical" },
];

const SEVERITY_OPTIONS = [
  { value: "minor", label: "Minor" },
  { value: "major", label: "Major" },
  { value: "critical", label: "Critical" },
  { value: "blocker", label: "Blocker" },
];

export default function NewTestCasePage() {
  const router = useRouter();
  const { project } = useProjectContext();

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState("medium");
  const [severity, setSeverity] = useState("major");
  const [tags, setTags] = useState<string[]>([]);
  const [steps, setSteps] = useState<TestStepDraft[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const testCase = await apiClient.post<TestCase>(`/projects/${project.id}/test-cases`, {
        title,
        description,
        priority,
        severity,
        tags,
        steps: steps.map((step) => ({
          action_type: step.action_type,
          target_descriptor: step.target_descriptor || null,
          input_value: step.input_value || null,
          expected_assertion: step.expected_assertion || null,
        })),
      });
      router.push(`/projects/${project.id}/test-cases/${testCase.id}`);
    } catch (err) {
      if (err instanceof ApiError && err.code === "project_archived") {
        setError("This project is archived. Unarchive it to add test cases.");
      } else {
        setError("Something went wrong. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6">
      <h2 className="text-subheading font-semibold text-foreground">New test case</h2>
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
              hint="What is this test case verifying?"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Select label="Priority" options={PRIORITY_OPTIONS} value={priority} onChange={(e) => setPriority(e.target.value)} />
              <Select label="Severity" options={SEVERITY_OPTIONS} value={severity} onChange={(e) => setSeverity(e.target.value)} />
            </div>
            <TagInput label="Tags" value={tags} onChange={setTags} placeholder="Add a tag and press Enter" />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Steps</CardTitle>
          </CardHeader>
          <CardContent>
            <TestStepEditor value={steps} onChange={setSteps} />
          </CardContent>
        </Card>

        {error && (
          <p role="alert" className="text-caption text-destructive">
            {error}
          </p>
        )}

        <Button type="submit" loading={submitting} disabled={!title || !description} className="self-start">
          Create test case
        </Button>
      </form>
    </div>
  );
}
