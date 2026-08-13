"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth";
import { queryKeys } from "@/lib/query-client";

export type NotificationType =
  | "run_completed"
  | "run_failed_critical"
  | "ai_analysis_completed"
  | "ai_analysis_failed";

export interface Notification {
  id: string;
  type: NotificationType;
  related_entity_type: string;
  related_entity_id: string;
  project_id: string | null;
  test_run_id: string | null;
  read_at: string | null;
  created_at: string;
}

interface NotificationListResponse {
  items: Notification[];
  unread_count: number;
}

/** Polled every 30s in the background, or every 3s while `active` (the bell
 * dialog or the full notifications page is open) — plan.md's Notifications
 * Architecture: "the frontend polls/queries notifications the same way it
 * queries any other resource." No push channel exists at MVP, so this is
 * how a run/analysis that just completed becomes visible without a manual
 * page refresh, and the faster active interval means opening the panel
 * shows genuinely current data within a couple of seconds rather than
 * whatever the last 30s-old background poll happened to catch. */
export function useNotifications(active = false) {
  const { organization } = useAuth();
  const orgId = organization?.id ?? "";
  return useQuery({
    queryKey: queryKeys.org(orgId).notifications(),
    queryFn: () => apiClient.get<NotificationListResponse>("/notifications"),
    refetchInterval: active ? 3_000 : 30_000,
  });
}

export function useMarkNotificationRead() {
  const queryClient = useQueryClient();
  const { organization } = useAuth();
  const orgId = organization?.id ?? "";
  return useMutation({
    mutationFn: (notificationId: string) =>
      apiClient.post<{ notification: Notification }>(`/notifications/${notificationId}/read`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.org(orgId).notifications() });
    },
  });
}

export function useMarkAllNotificationsRead() {
  const queryClient = useQueryClient();
  const { organization } = useAuth();
  const orgId = organization?.id ?? "";
  return useMutation({
    mutationFn: () => apiClient.post("/notifications/read-all"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.org(orgId).notifications() });
    },
  });
}
