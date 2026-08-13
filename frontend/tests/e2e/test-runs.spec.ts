import { expect, test } from "@playwright/test";

// Next.js dev-mode compiles each route on first visit — this test visits an
// unusually large number of distinct routes in one run (more than any other
// spec), so client-side RSC navigations right after a first visit need a
// longer timeout than the 5s default to absorb that first-compile latency;
// the production build (already verified separately) has no such delay.
const NAV_TIMEOUT = { timeout: 15_000 };

test.describe("Test execution (Phase 11)", () => {
  test("select cases, start a run, watch it complete, retry the failed ones", async ({ page }) => {
    // Two full real test-run executions (real browser navigation, real
    // Redis-queued jobs, real worker processing) plus two full manual
    // test-case creation flows — well beyond the 30s default budget.
    test.setTimeout(180_000);

    const email = `test-runs-e2e-${Date.now()}@example.com`;
    const password = "correct horse battery staple test runs";

    await page.goto("/signup");
    await page.getByLabel("Name").fill("Test Runs E2E User");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByRole("button", { name: "Sign up" }).click();
    await expect(page).toHaveURL(/\/overview$/, NAV_TIMEOUT);

    await page.goto("/projects/new");
    await page.getByLabel("Name").fill("Test Runs Project");
    await page.getByLabel("Target URL").fill("https://example.com");
    await page.getByRole("button", { name: "Create project" }).click();
    await expect(page).toHaveURL(/\/projects\/[0-9a-f-]+$/, NAV_TIMEOUT);

    await page.getByRole("navigation", { name: "Project" }).getByRole("link", { name: "Test cases" }).click();
    await expect(page).toHaveURL(/\/test-cases$/, NAV_TIMEOUT);

    // A case that will genuinely pass against the real target site.
    await page.getByRole("link", { name: "Create a test case" }).click();
    await page.getByLabel("Title").fill("Passing case");
    await page.getByLabel("Description").fill("Navigates and asserts real page content.");
    await page.getByRole("button", { name: "Add step" }).click();
    await page.getByLabel("URL or path").last().fill("https://example.com");
    await page.getByRole("button", { name: "Add step" }).click();
    await page.getByLabel("Action").last().selectOption("assert_content");
    await page.getByLabel("Expected text").last().fill("Example Domain");
    await page.getByRole("button", { name: "Create test case" }).click();
    await expect(page).toHaveURL(/\/test-cases\/[0-9a-f-]+$/, NAV_TIMEOUT);
    await page.getByRole("button", { name: "Approve" }).click();
    await expect(page.getByText("approved", { exact: true })).toBeVisible(NAV_TIMEOUT);

    // A case that will genuinely fail against the real target site. The
    // library is no longer empty at this point, so the create-a-case entry
    // point is now the header's "New test case" button, not the empty
    // state's "Create a test case" action.
    await page.getByRole("navigation", { name: "Project" }).getByRole("link", { name: "Test cases" }).click();
    await expect(page).toHaveURL(/\/test-cases$/, NAV_TIMEOUT);
    await page.getByRole("link", { name: "New test case" }).click();
    await page.getByLabel("Title").fill("Failing case");
    await page.getByLabel("Description").fill("Navigates and asserts content that is not present.");
    await page.getByRole("button", { name: "Add step" }).click();
    await page.getByLabel("URL or path").last().fill("https://example.com");
    await page.getByRole("button", { name: "Add step" }).click();
    await page.getByLabel("Action").last().selectOption("assert_content");
    await page.getByLabel("Expected text").last().fill("This text is definitely not on the page");
    await page.getByRole("button", { name: "Create test case" }).click();
    await expect(page).toHaveURL(/\/test-cases\/[0-9a-f-]+$/, NAV_TIMEOUT);
    await page.getByRole("button", { name: "Approve" }).click();
    await expect(page.getByText("approved", { exact: true })).toBeVisible(NAV_TIMEOUT);

    // Start a run against both cases.
    await page.getByRole("navigation", { name: "Project" }).getByRole("link", { name: "Test runs" }).click();
    await expect(page).toHaveURL(/\/test-runs$/, NAV_TIMEOUT);
    await page.getByRole("link", { name: "Start a test run" }).click();
    await expect(page).toHaveURL(/\/test-runs\/new$/, NAV_TIMEOUT);
    await page.getByLabel("Select all").check();
    await page.getByRole("button", { name: /Start run \(2\)/ }).click();
    await expect(page).toHaveURL(/\/test-runs\/[0-9a-f-]+$/, NAV_TIMEOUT);

    // Real execution: a real Chromium browser driven through Playwright,
    // via a real Redis-queued job a real worker process consumes — not
    // mocked, so this takes real seconds, not milliseconds (same
    // real-execution note as ai-generation.spec.ts).
    await expect(page.getByText("Completed", { exact: true }).first()).toBeVisible({ timeout: 45_000 });
    await expect(page.getByText("Passed", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Failed", { exact: true }).first()).toBeVisible();

    const retryButton = page.getByRole("button", { name: "Retry failed" });
    await expect(retryButton).toBeVisible();
    await retryButton.click();

    // A brand-new run, scoped to only the one failed case.
    await expect(page).toHaveURL(/\/test-runs\/[0-9a-f-]+$/, NAV_TIMEOUT);
    await expect(page.getByText("Completed", { exact: true }).first()).toBeVisible({ timeout: 45_000 });
    await expect(page.getByText("Failing case")).toBeVisible();
    await expect(page.getByText("Passing case")).not.toBeVisible();

    // History shows both runs, and the original run's own result is unchanged.
    await page.getByRole("navigation", { name: "Project" }).getByRole("link", { name: "Test runs" }).click();
    await expect(page).toHaveURL(/\/test-runs$/, NAV_TIMEOUT);
    const rows = page.locator("table tbody tr");
    await expect(rows).toHaveCount(2);
  });
});
