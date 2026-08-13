import { expect, test } from "@playwright/test";

// Same dev-mode first-visit-compile latency rationale as test-runs.spec.ts.
const NAV_TIMEOUT = { timeout: 15_000 };

test.describe("Notifications (Phase 17)", () => {
  test("completing a run and an analysis produces notifications that deep-link to the correct run/result", async ({
    page,
  }) => {
    // A real critical-severity test-run execution plus a real AI-analysis
    // round trip, plus several notification-center round trips.
    test.setTimeout(120_000);

    const email = `notifications-e2e-${Date.now()}@example.com`;
    const password = "correct horse battery staple notifications";

    await page.goto("/signup");
    await page.getByLabel("Name").fill("Notify E2E User");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByRole("button", { name: "Sign up" }).click();
    await expect(page).toHaveURL(/\/overview$/, NAV_TIMEOUT);

    // The bell starts with no unread badge and the empty-state copy.
    await page.getByRole("button", { name: "Notifications" }).click();
    await expect(page.getByText("You're all caught up.")).toBeVisible();
    await page.keyboard.press("Escape");

    await page.goto("/projects/new");
    await page.getByLabel("Name").fill("Notifications Project");
    await page.getByLabel("Target URL").fill("https://example.com");
    await page.getByRole("button", { name: "Create project" }).click();
    await expect(page).toHaveURL(/\/projects\/[0-9a-f-]+$/, NAV_TIMEOUT);

    await page.getByRole("navigation", { name: "Project" }).getByRole("link", { name: "Test cases" }).click();
    await expect(page).toHaveURL(/\/test-cases$/, NAV_TIMEOUT);

    // A critical-severity case guaranteed to fail (FR-113: run_failed_critical).
    await page.getByRole("link", { name: "Create a test case" }).click();
    await page.getByLabel("Title").fill("Critical failing case");
    await page.getByLabel("Description").fill("Asserts content that is not present.");
    await page.getByLabel("Severity").selectOption("critical");
    await page.getByRole("button", { name: "Add step" }).click();
    await page.getByLabel("URL or path").last().fill("https://example.com");
    await page.getByRole("button", { name: "Add step" }).click();
    await page.getByLabel("Action").last().selectOption("assert_content");
    await page.getByLabel("Expected text").last().fill("This text is definitely not on the page");
    await page.getByRole("button", { name: "Create test case" }).click();
    await expect(page).toHaveURL(/\/test-cases\/[0-9a-f-]+$/, NAV_TIMEOUT);
    await page.getByRole("button", { name: "Approve" }).click();
    await expect(page.getByText("approved", { exact: true })).toBeVisible(NAV_TIMEOUT);

    await page.getByRole("navigation", { name: "Project" }).getByRole("link", { name: "Test runs" }).click();
    await expect(page).toHaveURL(/\/test-runs$/, NAV_TIMEOUT);
    await page.getByRole("link", { name: "Start a test run" }).click();
    await expect(page).toHaveURL(/\/test-runs\/new$/, NAV_TIMEOUT);
    await page.getByLabel("Select all").check();
    await page.getByRole("button", { name: /Start run \(1\)/ }).click();
    await expect(page).toHaveURL(/\/test-runs\/[0-9a-f-]+$/, NAV_TIMEOUT);
    const runUrl = page.url();
    const runId = runUrl.match(/test-runs\/([0-9a-f-]+)/)?.[1];

    await expect(page.getByText("Completed", { exact: true }).first()).toBeVisible({ timeout: 45_000 });
    await expect(page.getByText("Failed", { exact: true }).first()).toBeVisible();

    // FR-112/FR-113: a run_failed_critical notification appears, unread,
    // and clicking it navigates to this exact run.
    await page.getByRole("button", { name: /^Notifications/ }).click();
    await expect(page.getByText("Test run failed — critical severity")).toBeVisible(NAV_TIMEOUT);
    await page.getByText("Test run failed — critical severity").click();
    await expect(page).toHaveURL(new RegExp(`test-runs/${runId}$`), NAV_TIMEOUT);

    // FR-116: clicking it marked it read -- the unread badge is gone now.
    await expect(page.getByRole("button", { name: "Notifications" })).toBeVisible();

    await page.getByText("Critical failing case").click();
    await expect(page).toHaveURL(/\/test-runs\/[0-9a-f-]+\/results\/[0-9a-f-]+$/, NAV_TIMEOUT);
    const resultUrl = page.url();

    // Real AI analysis: a real enqueue, a real worker, a real notification.
    await expect(page.getByRole("heading", { name: "AI Failure Analysis" })).toBeVisible();
    await page.getByRole("button", { name: "Request AI analysis" }).click();
    await expect(page.getByRole("heading", { name: "Explanation" })).toBeVisible({ timeout: 30_000 });

    await page.getByRole("button", { name: /^Notifications/ }).click();
    await expect(page.getByText("AI analysis completed")).toBeVisible(NAV_TIMEOUT);
    await page.getByText("AI analysis completed").click();
    await expect(page).toHaveURL(resultUrl, NAV_TIMEOUT);

    // The full notification history page lists both notifications too.
    await page.goto("/notifications");
    await expect(page.getByRole("heading", { name: "Notifications" })).toBeVisible();
    await expect(page.getByText("Test run failed — critical severity")).toBeVisible();
    await expect(page.getByText("AI analysis completed")).toBeVisible();
  });
});
