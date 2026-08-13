import { expect, test } from "@playwright/test";

// Same dev-mode first-visit-compile latency rationale as test-runs.spec.ts.
const NAV_TIMEOUT = { timeout: 15_000 };

test.describe("Reports and analytics (Phase 16)", () => {
  test("the Reports page totals match the runs and issues created in earlier E2E flows", async ({ page }) => {
    // Two real test-run executions plus an issue-creation round trip.
    test.setTimeout(120_000);

    const email = `reports-e2e-${Date.now()}@example.com`;
    const password = "correct horse battery staple reports";

    await page.goto("/signup");
    await page.getByLabel("Name").fill("Reports E2E User");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByRole("button", { name: "Sign up" }).click();
    await expect(page).toHaveURL(/\/overview$/, NAV_TIMEOUT);

    await page.goto("/projects/new");
    await page.getByLabel("Name").fill("Reports Project");
    await page.getByLabel("Target URL").fill("https://example.com");
    await page.getByRole("button", { name: "Create project" }).click();
    await expect(page).toHaveURL(/\/projects\/[0-9a-f-]+$/, NAV_TIMEOUT);

    await page.getByRole("navigation", { name: "Project" }).getByRole("link", { name: "Test cases" }).click();
    await expect(page).toHaveURL(/\/test-cases$/, NAV_TIMEOUT);

    // A case guaranteed to pass against the real target site.
    await page.getByRole("link", { name: "Create a test case" }).click();
    await page.getByLabel("Title").fill("Passing case");
    await page.getByLabel("Description").fill("Asserts content that is actually present.");
    await page.getByRole("button", { name: "Add step" }).click();
    await page.getByLabel("URL or path").last().fill("https://example.com");
    await page.getByRole("button", { name: "Add step" }).click();
    await page.getByLabel("Action").last().selectOption("assert_content");
    await page.getByLabel("Expected text").last().fill("Example Domain");
    await page.getByRole("button", { name: "Create test case" }).click();
    await expect(page).toHaveURL(/\/test-cases\/[0-9a-f-]+$/, NAV_TIMEOUT);
    await page.getByRole("button", { name: "Approve" }).click();
    await expect(page.getByText("approved", { exact: true })).toBeVisible(NAV_TIMEOUT);

    // A case guaranteed to fail against the real target site. The list
    // already has one case at this point, so the create link reads "New
    // test case" here rather than the empty-state's "Create a test case".
    await page.getByRole("navigation", { name: "Project" }).getByRole("link", { name: "Test cases" }).click();
    await expect(page).toHaveURL(/\/test-cases$/, NAV_TIMEOUT);
    await page.getByRole("link", { name: "New test case" }).click();
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

    // Run 1: both cases -> 1 passed, 1 failed.
    await page.getByRole("navigation", { name: "Project" }).getByRole("link", { name: "Test runs" }).click();
    await expect(page).toHaveURL(/\/test-runs$/, NAV_TIMEOUT);
    await page.getByRole("link", { name: "Start a test run" }).click();
    await expect(page).toHaveURL(/\/test-runs\/new$/, NAV_TIMEOUT);
    await page.getByLabel("Select all").check();
    await page.getByRole("button", { name: /Start run \(2\)/ }).click();
    await expect(page).toHaveURL(/\/test-runs\/[0-9a-f-]+$/, NAV_TIMEOUT);
    await expect(page.getByText("Completed", { exact: true }).first()).toBeVisible({ timeout: 45_000 });

    // Create an issue from the failed result (Story 7 dependency for FR-106).
    await page.getByText("Failing case").click();
    await expect(page).toHaveURL(/\/test-runs\/[0-9a-f-]+\/results\/[0-9a-f-]+$/, NAV_TIMEOUT);
    await page.getByRole("button", { name: "Create issue" }).click();
    await expect(page.getByRole("heading", { name: "Create issue from this failure" })).toBeVisible();
    await page.getByLabel("Severity").selectOption("major");
    await page.getByLabel("Priority").selectOption("high");
    await page.getByRole("dialog").getByRole("button", { name: "Create issue" }).click();
    await expect(page).toHaveURL(/\/projects\/[0-9a-f-]+\/issues\/[0-9a-f-]+$/, NAV_TIMEOUT);

    // Run 2: just the passing case -> 1 passed.
    await page.getByRole("navigation", { name: "Project" }).getByRole("link", { name: "Test runs" }).click();
    await expect(page).toHaveURL(/\/test-runs$/, NAV_TIMEOUT);
    await page.getByRole("link", { name: "Start a test run" }).click();
    await expect(page).toHaveURL(/\/test-runs\/new$/, NAV_TIMEOUT);
    // Each case row is a <label> wrapping its own checkbox plus the title
    // text -- clicking the title toggles that row's checkbox natively.
    await page.getByText("Passing case", { exact: true }).click();
    await page.getByRole("button", { name: /Start run \(1\)/ }).click();
    await expect(page).toHaveURL(/\/test-runs\/[0-9a-f-]+$/, NAV_TIMEOUT);
    await expect(page.getByText("Completed", { exact: true }).first()).toBeVisible({ timeout: 45_000 });

    // FR-104-FR-107: the Reports page totals must match what the two runs
    // and the one issue above actually produced -- 3 results total across
    // both runs (2 passed, 1 failed), 1 major-severity issue.
    await page.getByRole("navigation", { name: "Project" }).getByRole("link", { name: "Reports" }).click();
    await expect(page).toHaveURL(/\/reports$/, NAV_TIMEOUT);

    // Each StatCard is a label span followed by a sibling value span, both
    // direct children of the same Card div -- ".." from the label reaches
    // the flex wrapper, ".." again reaches the Card that also holds the
    // value span.
    const statCard = (label: string) => page.getByText(label, { exact: true }).locator("../..");

    await expect(statCard("Total results").getByText("3", { exact: true })).toBeVisible();
    await expect(statCard("Passed").getByText("2", { exact: true })).toBeVisible();
    await expect(statCard("Failed").getByText("1", { exact: true })).toBeVisible();
    await expect(statCard("Skipped").getByText("0", { exact: true })).toBeVisible();
    await expect(statCard("Pass rate").getByText("66.7%", { exact: true })).toBeVisible();

    await expect(page.getByRole("heading", { name: "Issues by severity" })).toBeVisible();
    await expect(page.getByText("Major: 1")).toBeVisible();
    await expect(page.getByText("Minor: 0")).toBeVisible();

    await expect(page.getByRole("heading", { name: "Run history" })).toBeVisible();
    const runRows = page.getByRole("row").filter({ hasText: "passed" });
    await expect(runRows).toHaveCount(2);
  });
});
