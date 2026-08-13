import type { Notification, NotificationType } from "./useNotifications";

const LABELS: Record<NotificationType, string> = {
  run_completed: "Test run completed",
  run_failed_critical: "Test run failed — critical severity",
  ai_analysis_completed: "AI analysis completed",
  ai_analysis_failed: "AI analysis failed",
};

export function notificationLabel(notification: Notification): string {
  return LABELS[notification.type];
}

/**
 * FR-115: navigate from a notification to its related test run or result.
 * `project_id`/`test_run_id` are resolved server-side at read time
 * (contracts/notifications-api.md's documented client-side "lookup table" —
 * this is that table) since the persisted row itself only carries
 * `related_entity_type`/`related_entity_id`.
 */
export function notificationHref(notification: Notification): string | null {
  if (notification.related_entity_type === "test_run" && notification.project_id) {
    return `/projects/${notification.project_id}/test-runs/${notification.related_entity_id}`;
  }
  if (notification.related_entity_type === "test_result" && notification.project_id && notification.test_run_id) {
    return `/projects/${notification.project_id}/test-runs/${notification.test_run_id}/results/${notification.related_entity_id}`;
  }
  return null;
}
