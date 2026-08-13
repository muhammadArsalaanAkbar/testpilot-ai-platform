"use client";

import { Bell, CheckCheck } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Button } from "@/components/Button";
import { Dialog } from "@/components/Dialog";
import {
  useMarkAllNotificationsRead,
  useMarkNotificationRead,
  useNotifications,
} from "@/features/notifications/useNotifications";
import { notificationHref, notificationLabel } from "@/features/notifications/notification-utils";
import { cn } from "@/lib/cn";

/** Topbar notification entry point (FR-115, FR-116) — wired to real data. */
export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const { data, refetch } = useNotifications(open);
  const markRead = useMarkNotificationRead();
  const markAllRead = useMarkAllNotificationsRead();

  const items = data?.items ?? [];
  const unreadCount = data?.unread_count ?? 0;

  return (
    <>
      <button
        type="button"
        onClick={() => {
          setOpen(true);
          // Always show current data on open rather than waiting for the
          // next 30s poll -- a run/analysis may have just completed.
          refetch();
        }}
        aria-label={unreadCount > 0 ? `Notifications, ${unreadCount} unread` : "Notifications"}
        className="relative rounded-md p-2 text-muted-foreground hover:bg-muted hover:text-foreground"
      >
        <Bell className="h-5 w-5" aria-hidden="true" />
        {unreadCount > 0 && (
          <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-semibold leading-none text-destructive-foreground">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>
      <Dialog
        open={open}
        onOpenChange={setOpen}
        title="Notifications"
        footer={
          items.length > 0 ? (
            <div className="flex w-full items-center justify-between">
              <Link
                href="/notifications"
                onClick={() => setOpen(false)}
                className="text-caption text-primary hover:underline"
              >
                View all
              </Link>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => markAllRead.mutate()}
                disabled={unreadCount === 0 || markAllRead.isPending}
              >
                <CheckCheck className="h-4 w-4" aria-hidden="true" />
                Mark all read
              </Button>
            </div>
          ) : undefined
        }
      >
        {items.length === 0 ? (
          <p className="text-body text-muted-foreground">
            You&apos;re all caught up. Notifications will appear here once test runs and AI analyses start
            completing.
          </p>
        ) : (
          <ul className="flex max-h-80 flex-col divide-y divide-border overflow-y-auto">
            {items.map((notification) => {
              const href = notificationHref(notification);
              const content = (
                <div
                  className={cn(
                    "flex items-start gap-2 py-3",
                    href && "cursor-pointer",
                    !notification.read_at && "font-medium text-foreground",
                  )}
                >
                  {!notification.read_at && (
                    <span
                      className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-primary"
                      aria-hidden="true"
                    />
                  )}
                  <div className={cn("flex-1", notification.read_at && "pl-4 text-muted-foreground")}>
                    <p className="text-body">{notificationLabel(notification)}</p>
                    <p className="text-caption text-muted-foreground">
                      {new Date(notification.created_at).toLocaleString()}
                    </p>
                  </div>
                </div>
              );

              return (
                <li key={notification.id}>
                  {href ? (
                    <Link
                      href={href}
                      onClick={() => {
                        if (!notification.read_at) markRead.mutate(notification.id);
                        setOpen(false);
                      }}
                      className="block"
                    >
                      {content}
                    </Link>
                  ) : (
                    <button
                      type="button"
                      className="block w-full text-left"
                      onClick={() => {
                        if (!notification.read_at) markRead.mutate(notification.id);
                      }}
                    >
                      {content}
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </Dialog>
    </>
  );
}
