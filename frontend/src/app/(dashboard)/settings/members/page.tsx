"use client";

import { useEffect, useState } from "react";
import { Sparkles } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/Card";
import { DataTable, type DataTableColumn } from "@/components/DataTable";
import { ErrorState } from "@/components/states/ErrorState";
import { apiClient } from "@/lib/api-client";

interface MemberPublic {
  user_id: string;
  name: string;
  email: string;
  role: string;
}

const COLUMNS: DataTableColumn<MemberPublic>[] = [
  { key: "name", header: "Name", render: (m) => m.name, sortable: true, sortValue: (m) => m.name },
  { key: "email", header: "Email", render: (m) => m.email, sortable: true, sortValue: (m) => m.email },
  { key: "role", header: "Role", render: (m) => <span className="capitalize">{m.role}</span> },
];

export default function MembersSettingsPage() {
  const [members, setMembers] = useState<MemberPublic[]>([]);
  const [loadError, setLoadError] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  async function load() {
    setIsLoading(true);
    setLoadError(false);
    try {
      const data = await apiClient.get<{ items: MemberPublic[] }>("/organizations/current/members");
      setMembers(data.items);
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

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Members</CardTitle>
        </CardHeader>
        <CardContent>
          <DataTable
            columns={COLUMNS}
            data={members}
            getRowKey={(m) => m.user_id}
            isLoading={isLoading}
            searchPlaceholder="Search members..."
            searchValue={(m) => `${m.name} ${m.email}`}
          />
        </CardContent>
      </Card>

      <Card className="border-dashed">
        <CardContent className="flex items-center gap-3 py-6">
          <Sparkles className="h-5 w-5 shrink-0 text-muted-foreground" aria-hidden="true" />
          <div>
            <p className="text-body font-medium text-foreground">Team invites are coming soon</p>
            <p className="text-caption text-muted-foreground">
              Inviting teammates and assigning roles will be available in a future release.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
