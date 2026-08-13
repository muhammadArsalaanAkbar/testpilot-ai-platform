"use client";

import { useEffect, useState, type FormEvent } from "react";
import { Button } from "@/components/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/Card";
import { TextField } from "@/components/form/TextField";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";
import { useToast } from "@/components/Toast";
import { apiClient, ApiError } from "@/lib/api-client";

interface OrganizationDetail {
  id: string;
  name: string;
  slug: string;
  plan: string;
  created_at: string;
}

export default function OrganizationSettingsPage() {
  const { showToast } = useToast();
  const [organization, setOrganization] = useState<OrganizationDetail | null>(null);
  const [name, setName] = useState("");
  const [loadError, setLoadError] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function load() {
    setIsLoading(true);
    setLoadError(false);
    try {
      const data = await apiClient.get<OrganizationDetail>("/organizations/current");
      setOrganization(data);
      setName(data.name);
    } catch {
      setLoadError(true);
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSaveError(null);
    setSaving(true);
    try {
      const updated = await apiClient.patch<OrganizationDetail>("/organizations/current", { name });
      setOrganization(updated);
      showToast({ variant: "success", title: "Organization updated" });
    } catch (err) {
      if (err instanceof ApiError && err.code === "insufficient_role") {
        setSaveError("Only the Organization owner or an admin can update these settings.");
      } else {
        setSaveError("Something went wrong. Please try again.");
      }
    } finally {
      setSaving(false);
    }
  }

  if (isLoading) {
    return <LoadingState variant="detail" />;
  }

  if (loadError || !organization) {
    return <ErrorState onRetry={load} />;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Organization</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <TextField label="Workspace name" required value={name} onChange={(e) => setName(e.target.value)} />
          <TextField label="Slug" value={organization.slug} disabled hint="Slug cannot be changed." />
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
  );
}
