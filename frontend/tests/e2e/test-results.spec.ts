import { expect, test } from "@playwright/test";

// Same dev-mode first-visit-compile latency rationale as test-runs.spec.ts.
const NAV_TIMEOUT = { timeout: 15_000 };

test.describe("Test result evidence (Phase 12)", () => {
  test("open a failed result and view its screenshot in the lightbox", async ({ page }) => {
    // A real test-run execution (real browser navigation, real Redis-queued
    // job, real worker, real MinIO upload) plus manual test-case creation —
    // well beyond the 30s default budget.
    test.setTimeout(120_000);

    const email = `test-results-e2e-${Date.now()}@example.com`;
    const password = "correct horse battery staple test results";

    await page.goto("/signup");
    await page.getByLabel("Name").fill("Test Results E2E User");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByRole("button", { name: "Sign up" }).click();
    await expect(page).toHaveURL(/\/overview$/, NAV_TIMEOUT);

    await page.goto("/projects/new");
    await page.getByLabel("Name").fill("Test Results Project");
    await page.getByLabel("Target URL").fill("https://example.com");
    await page.getByRole("button", { name: "Create project" }).click();
    await expect(page).toHaveURL(/\/projects\/[0-9a-f-]+$/, NAV_TIMEOUT);

    await page.getByRole("navigation", { name: "Project" }).getByRole("link", { name: "Test cases" }).click();
    await expect(page).toHaveURL(/\/test-cases$/, NAV_TIMEOUT);

    // A case guaranteed to fail against the real target site, so it
    // genuinely captures a failure screenshot (FR-064).
    await page.getByRole("link", { name: "Create a test case" }).click();
    await page.getByLabel("Title").fill("Failing case");
    await page.getByLabel("Description").fill("Asserts content that is not present, to capture a real failure screenshot.");
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

    // Real execution: a real Chromium browser driven through Playwright,
    // via a real Redis-queued job a real worker process consumes, uploading
    // the failure screenshot to real local MinIO — not mocked at any layer.
    await expect(page.getByText("Completed", { exact: true }).first()).toBeVisible({ timeout: 45_000 });
    await expect(page.getByText("Failed", { exact: true }).first()).toBeVisible();

    await page.getByText("Failing case").click();
    await expect(page).toHaveURL(/\/test-runs\/[0-9a-f-]+\/results\/[0-9a-f-]+$/, NAV_TIMEOUT);

    await expect(page.getByRole("heading", { name: "Execution log" })).toBeVisible();
    await expect(page.getByText(/assert content/i)).toBeVisible();
    await expect(page.getByRole("heading", { name: "Evidence" })).toBeVisible();

    const thumbnail = page.getByRole("button").filter({ has: page.locator("img") }).first();
    await expect(thumbnail).toBeVisible(NAV_TIMEOUT);
    await thumbnail.click();

    // The lightbox: a dedicated dialog with the full-size image, closable.
    const lightbox = page.getByRole("dialog");
    await expect(lightbox).toBeVisible();
    await expect(lightbox.locator("img")).toBeVisible();
    await page.getByRole("button", { name: "Close screenshot viewer" }).click();
    await expect(lightbox).not.toBeVisible();
  });
});
