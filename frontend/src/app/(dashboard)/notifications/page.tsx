"use client";

import { Bell, CheckCheck } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/Button";
import { Card, CardContent } from "@/components/Card";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { LoadingState } from "@/components/states/LoadingState";
import { notificationHref, notificationLabel } from "@/features/notifications/notification-utils";
import {
  useMarkAllNotificationsRead,
  useMarkNotificationRead,
  useNotifications,
} from "@/features/notifications/useNotifications";
import { cn } from "@/lib/cn";

/** Full notification history (FR-115, plan.md's notifications/page.tsx note)
 * — the topbar bell's slide-over uses the same data for quick access. */
export default function NotificationsPage() {
  const { data, isLoading, isError, refetch } = useNotifications(true);
  const markRead = useMarkNotificationRead();
  const markAllRead = useMarkAllNotificationsRead();

  if (isLoading) {
    return <LoadingState variant="cards" />;
  }

  if (isError || !data) {
    return <ErrorState onRetry={() => refetch()} />;
  }

  const { items, unread_count: unreadCount } = data;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h2 className="text-subheading font-semibold text-foreground">Notifications</h2>
        <Button
          variant="outline"
          size="sm"
          onClick={() => markAllRead.mutate()}
          disabled={unreadCount === 0 || markAllRead.isPending}
        >
          <CheckCheck className="h-4 w-4" aria-hidden="true" />
          Mark all read
        </Button>
      </div>

      {items.length === 0 ? (
        <EmptyState
          icon={Bell}
          title="No notifications yet"
          description="Test run completions and AI analysis results will appear here."
        />
      ) : (
        <Card>
          <CardContent className="flex flex-col divide-y divide-border p-0">
            {items.map((notification) => {
              const href = notificationHref(notification);
              const row = (
                <div
                  className={cn(
                    "flex items-start gap-3 px-4 py-4",
                    href && "cursor-pointer hover:bg-muted",
                    !notification.read_at && "font-medium text-foreground",
                  )}
                >
                  <span
                    className={cn(
                      "mt-1.5 h-2 w-2 shrink-0 rounded-full",
                      notification.read_at ? "bg-transparent" : "bg-primary",
                    )}
                    aria-hidden="true"
                  />
                  <div className={cn("flex-1", notification.read_at && "text-muted-foreground")}>
                    <p className="text-body">{notificationLabel(notification)}</p>
                    <p className="text-caption text-muted-foreground">
                      {new Date(notification.created_at).toLocaleString()}
                    </p>
                  </div>
                </div>
              );

              return (
                <div key={notification.id}>
                  {href ? (
                    <Link
                      href={href}
                      onClick={() => {
                        if (!notification.read_at) markRead.mutate(notification.id);
                      }}
                      className="block"
                    >
                      {row}
                    </Link>
                  ) : (
                    <button
                      type="button"
                      className="block w-full text-left"
                      onClick={() => {
                        if (!notification.read_at) markRead.mutate(notification.id);
                      }}
                    >
                      {row}
                    </button>
                  )}
                </div>
              );
            })}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
