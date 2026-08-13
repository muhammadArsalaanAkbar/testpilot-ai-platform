import { expect, test } from "@playwright/test";

// Same dev-mode first-visit-compile latency rationale as test-runs.spec.ts.
const NAV_TIMEOUT = { timeout: 15_000 };

test.describe("Bug/issue management (Phase 14)", () => {
  test("create an issue from a failed result, verify its links, move it through the status lifecycle", async ({
    page,
  }) => {
    // A real test-run execution plus several real issue-lifecycle round
    // trips — well beyond the 30s default budget.
    test.setTimeout(120_000);

    const email = `issues-e2e-${Date.now()}@example.com`;
    const password = "correct horse battery staple issues";

    await page.goto("/signup");
    await page.getByLabel("Name").fill("Issues E2E User");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByRole("button", { name: "Sign up" }).click();
    await expect(page).toHaveURL(/\/overview$/, NAV_TIMEOUT);

    await page.goto("/projects/new");
    await page.getByLabel("Name").fill("Issues Project");
    await page.getByLabel("Target URL").fill("https://example.com");
    await page.getByRole("button", { name: "Create project" }).click();
    await expect(page).toHaveURL(/\/projects\/[0-9a-f-]+$/, NAV_TIMEOUT);

    await page.getByRole("navigation", { name: "Project" }).getByRole("link", { name: "Test cases" }).click();
    await expect(page).toHaveURL(/\/test-cases$/, NAV_TIMEOUT);

    // A case guaranteed to fail against the real target site.
    await page.getByRole("link", { name: "Create a test case" }).click();
    await page.getByLabel("Title").fill("Failing case");
    await page.getByLabel("Description").fill("Asserts content that is not present.");
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

    // Real execution: a real Chromium browser driven through Playwright.
    await expect(page.getByText("Completed", { exact: true }).first()).toBeVisible({ timeout: 45_000 });
    await expect(page.getByText("Failed", { exact: true }).first()).toBeVisible();

    await page.getByText("Failing case").click();
    await expect(page).toHaveURL(/\/test-runs\/[0-9a-f-]+\/results\/[0-9a-f-]+$/, NAV_TIMEOUT);

    // FR-087: create an issue from this failed result, pre-filled and
    // pre-linked (FR-091).
    await page.getByRole("button", { name: "Create issue" }).click();
    await expect(page.getByRole("heading", { name: "Create issue from this failure" })).toBeVisible();
    await page.getByLabel("Severity").selectOption("critical");
    await page.getByLabel("Priority").selectOption("high");
    await page.getByRole("dialog").getByRole("button", { name: "Create issue" }).click();

    await expect(page).toHaveURL(/\/projects\/[0-9a-f-]+\/issues\/[0-9a-f-]+$/, NAV_TIMEOUT);
    await expect(page.getByRole("heading", { name: "Failing case failed" })).toBeVisible();

    // FR-091: linked back to its source test case and run.
    await expect(page.getByRole("link", { name: "Test case: Failing case" })).toBeVisible();
    await expect(page.getByRole("link", { name: /Test run \(/ })).toBeVisible();

    // FR-090: the status lifecycle — open -> in_progress -> resolved -> closed.
    // Asserted against the Status <select>'s own value (unambiguous — the
    // status is also mirrored in a visible IssueStatusBadge elsewhere on
    // the page, but "Open"/"Closed" etc. also appear as the <select>'s own
    // <option> text, which getByText would ambiguously match too).
    const statusSelect = page.getByLabel("Status");
    await expect(statusSelect).toHaveValue("open");

    await statusSelect.selectOption("in_progress");
    await expect(page.getByText("Issue updated").first()).toBeVisible();
    await expect(statusSelect).toHaveValue("in_progress");

    await statusSelect.selectOption("resolved");
    await expect(statusSelect).toHaveValue("resolved");

    await statusSelect.selectOption("closed");
    await expect(statusSelect).toHaveValue("closed");

    // A terminal status can only go back to "open" (contracts/issues-api.md)
    // — attempting a direct closed -> in_progress transition must be
    // rejected, leaving the status unchanged.
    await statusSelect.selectOption("in_progress");
    await expect(page.getByText("Failed to update issue").first()).toBeVisible();
    await expect(statusSelect).toHaveValue("closed");

    await statusSelect.selectOption("open");
    await expect(page.getByText("Issue updated").first()).toBeVisible();
    await expect(statusSelect).toHaveValue("open");

    // The issue also shows up in the project's issue list.
    await page.getByRole("navigation", { name: "Project" }).getByRole("link", { name: "Issues" }).click();
    await expect(page).toHaveURL(/\/issues$/, NAV_TIMEOUT);
    await expect(page.getByRole("cell", { name: "Failing case failed" })).toBeVisible();
  });

  test("create a manual issue independent of any test result", async ({ page }) => {
    test.setTimeout(60_000);

    const email = `issues-manual-e2e-${Date.now()}@example.com`;
    const password = "correct horse battery staple manual issue";

    await page.goto("/signup");
    await page.getByLabel("Name").fill("Manual Issue E2E User");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByRole("button", { name: "Sign up" }).click();
    await expect(page).toHaveURL(/\/overview$/, NAV_TIMEOUT);

    await page.goto("/projects/new");
    await page.getByLabel("Name").fill("Manual Issue Project");
    await page.getByLabel("Target URL").fill("https://example.com");
    await page.getByRole("button", { name: "Create project" }).click();
    await expect(page).toHaveURL(/\/projects\/[0-9a-f-]+$/, NAV_TIMEOUT);

    await page.getByRole("navigation", { name: "Project" }).getByRole("link", { name: "Issues" }).click();
    await expect(page).toHaveURL(/\/issues$/, NAV_TIMEOUT);
    await page.getByRole("link", { name: "New issue" }).click();
    await expect(page).toHaveURL(/\/issues\/new$/, NAV_TIMEOUT);

    await page.getByLabel("Title").fill("Login button misaligned on mobile");
    await page.getByLabel("Description").fill("The primary CTA is offset by a few pixels on narrow viewports.");
    await page.getByLabel("Severity").selectOption("minor");
    await page.getByLabel("Priority").selectOption("low");
    await page.getByRole("button", { name: "Create issue" }).click();

    await expect(page).toHaveURL(/\/projects\/[0-9a-f-]+\/issues\/[0-9a-f-]+$/, NAV_TIMEOUT);
    await expect(page.getByRole("heading", { name: "Login button misaligned on mobile" })).toBeVisible();
    // FR-088: no source links for a manually created issue.
    await expect(page.getByRole("heading", { name: "Source" })).not.toBeVisible();
  });
});
