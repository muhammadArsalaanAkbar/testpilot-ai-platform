import { expect, test } from "@playwright/test";

test.describe("Test case library (Phase 8)", () => {
  test("create a manual test case, filter by tag and priority, approve then reject it", async ({ page }) => {
    const email = `testcases-e2e-${Date.now()}@example.com`;
    const password = "correct horse battery staple testcases";

    await page.goto("/signup");
    await page.getByLabel("Name").fill("Test Cases E2E User");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByRole("button", { name: "Sign up" }).click();
    await expect(page).toHaveURL(/\/overview$/);

    await page.goto("/projects/new");
    await page.getByLabel("Name").fill("Library Project");
    await page.getByLabel("Target URL").fill("https://example.com");
    await page.getByRole("button", { name: "Create project" }).click();
    await expect(page).toHaveURL(/\/projects\/[0-9a-f-]+$/);

    await page.getByRole("navigation", { name: "Project" }).getByRole("link", { name: "Test cases" }).click();
    await expect(page).toHaveURL(/\/test-cases$/);
    await page.getByRole("link", { name: "Create a test case" }).click();
    await expect(page).toHaveURL(/\/test-cases\/new$/);

    await page.getByLabel("Title").fill("Checkout completes with valid card");
    await page.getByLabel("Description").fill("Verify checkout completes end to end with a valid card.");
    await page.getByLabel("Priority").selectOption("critical");
    await page.getByLabel("Severity").selectOption("blocker");
    await page.getByLabel("Tags").fill("checkout");
    await page.getByLabel("Tags").press("Enter");
    await page.getByRole("button", { name: "Create test case" }).click();

    await expect(page).toHaveURL(/\/test-cases\/[0-9a-f-]+$/);
    await expect(page.getByRole("heading", { name: "Checkout completes with valid card" })).toBeVisible();

    // Back to the library, filter by tag and priority.
    await page.getByRole("navigation", { name: "Project" }).getByRole("link", { name: "Test cases" }).click();
    await expect(page).toHaveURL(/\/test-cases$/);
    await expect(page.getByRole("cell", { name: "Checkout completes with valid card" })).toBeVisible();

    await page.getByLabel("Tag").fill("checkout");
    await expect(page.getByRole("cell", { name: "Checkout completes with valid card" })).toBeVisible();

    await page.getByLabel("Tag").fill("nonexistent-tag");
    await expect(page.getByText("No results match your search.")).toBeVisible();
    await page.getByLabel("Tag").fill("");

    await page.getByLabel("Priority").selectOption("critical");
    await expect(page.getByRole("cell", { name: "Checkout completes with valid card" })).toBeVisible();
    await page.getByLabel("Priority").selectOption("low");
    await expect(page.getByText("No results match your search.")).toBeVisible();
    await page.getByLabel("Priority").selectOption("");

    // Approve then reject from the detail page.
    await page.getByRole("cell", { name: "Checkout completes with valid card" }).click();
    await expect(page).toHaveURL(/\/test-cases\/[0-9a-f-]+$/);

    await page.getByRole("button", { name: "Approve" }).click();
    await expect(page.getByText("Test case approved", { exact: true })).toBeVisible();
    await expect(page.getByText("approved", { exact: true })).toBeVisible();

    await page.getByRole("button", { name: "Reject" }).click();
    await expect(page.getByText("Test case rejected", { exact: true })).toBeVisible();
    await expect(page.getByText("rejected", { exact: true })).toBeVisible();
  });
});
