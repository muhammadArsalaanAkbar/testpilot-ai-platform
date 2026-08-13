import { expect, test } from "@playwright/test";

test.describe("AI test-case generation (Phase 9)", () => {
  test("trigger generation, poll to completion, review queue shows generated cases, approve one", async ({
    page,
  }) => {
    const email = `ai-gen-e2e-${Date.now()}@example.com`;
    const password = "correct horse battery staple ai gen";

    await page.goto("/signup");
    await page.getByLabel("Name").fill("AI Gen E2E User");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByRole("button", { name: "Sign up" }).click();
    await expect(page).toHaveURL(/\/overview$/);

    await page.goto("/projects/new");
    await page.getByLabel("Name").fill("AI Gen Project");
    await page.getByLabel("Target URL").fill("https://example.com");
    await page.getByRole("button", { name: "Create project" }).click();
    await expect(page).toHaveURL(/\/projects\/[0-9a-f-]+$/);

    await page.getByRole("navigation", { name: "Project" }).getByRole("link", { name: "Test cases" }).click();
    await expect(page).toHaveURL(/\/test-cases$/);
    await page.getByRole("link", { name: "Generate with AI" }).click();
    await expect(page).toHaveURL(/\/test-cases\/generate$/);

    await page.getByRole("button", { name: "Generate test cases" }).click();

    // Real generation: a real Playwright crawl of the project URL, a real
    // enqueue onto Redis, and a real worker process consuming it — this is
    // not mocked, so it takes real seconds, not milliseconds.
    await expect(page.getByRole("heading", { name: /Analyzing/ })).toBeVisible();
    await expect(page.getByRole("button", { name: "Approve" }).first()).toBeVisible({ timeout: 45_000 });
    await expect(page.getByText("draft", { exact: true }).first()).toBeVisible();

    await page.getByRole("button", { name: "Approve" }).first().click();
    await expect(page.getByText("approved", { exact: true }).first()).toBeVisible();
  });
});
