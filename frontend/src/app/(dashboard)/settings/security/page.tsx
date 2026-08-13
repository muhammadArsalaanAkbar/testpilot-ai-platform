"use client";

import { useCallback, useEffect, useState } from "react";
import { LogOut, Monitor } from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/Card";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { LoadingState } from "@/components/states/LoadingState";
import { useToast } from "@/components/Toast";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth";

interface SessionItem {
  id: string;
  created_at: string;
  last_used_at: string | null;
  is_current: boolean;
}

export default function SecuritySettingsPage() {
  const { logout } = useAuth();
  const { showToast } = useToast();
  const router = useRouter();
  const [sessions, setSessions] = useState<SessionItem[] | null>(null);
  const [error, setError] = useState(false);
  const [logoutAllOpen, setLogoutAllOpen] = useState(false);

  const loadSessions = useCallback(async () => {
    setError(false);
    try {
      const data = await apiClient.get<{ items: SessionItem[] }>("/auth/me/sessions");
      setSessions(data.items);
    } catch {
      setError(true);
    }
  }, []);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  async function handleRevoke(sessionId: string) {
    await apiClient.delete(`/auth/me/sessions/${sessionId}`);
    showToast({ variant: "success", title: "Session revoked" });
    await loadSessions();
  }

  async function handleLogoutAll() {
    await apiClient.post("/auth/logout-all");
    await logout();
    router.push("/login");
  }

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Active sessions</CardTitle>
        </CardHeader>
        <CardContent>
          {sessions === null && !error && <LoadingState variant="table" rows={2} />}
          {error && <ErrorState description="Could not load your sessions." onRetry={loadSessions} />}
          {sessions !== null && sessions.length === 0 && (
            <EmptyState icon={Monitor} title="No active sessions" />
          )}
          {sessions !== null && sessions.length > 0 && (
            <ul className="flex flex-col gap-2">
              {sessions.map((session) => (
                <li
                  key={session.id}
                  className="flex items-center justify-between rounded-md border border-border p-3"
                >
                  <div className="flex items-center gap-3">
                    <Monitor className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                    <div>
                      <p className="text-body text-foreground">
                        {session.is_current ? "This device" : "Other session"}
                      </p>
                      <p className="text-caption text-muted-foreground">
                        Signed in {new Date(session.created_at).toLocaleString()}
                      </p>
                    </div>
                  </div>
                  {!session.is_current && (
                    <Button variant="outline" size="sm" onClick={() => handleRevoke(session.id)}>
                      Revoke
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Log out everywhere</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-body text-muted-foreground">
            End every active session on every device, including this one.
          </p>
          <Button
            variant="destructive"
            className="mt-4"
            onClick={() => setLogoutAllOpen(true)}
          >
            <LogOut className="h-4 w-4" aria-hidden="true" />
            Log out everywhere
          </Button>
        </CardContent>
      </Card>

      <ConfirmDialog
        open={logoutAllOpen}
        onOpenChange={setLogoutAllOpen}
        title="Log out everywhere?"
        description="This will end every active session on every device, including this one. You'll need to log in again."
        confirmLabel="Log out everywhere"
        onConfirm={handleLogoutAll}
      />
    </div>
  );
}
