import { expect, test } from "@playwright/test";

test.describe("Projects (Phase 7)", () => {
  test("private-IP URL is rejected, then a valid URL is accepted and appears in the list", async ({ page }) => {
    const email = `projects-e2e-${Date.now()}@example.com`;
    const password = "correct horse battery staple projects";

    await page.goto("/signup");
    await page.getByLabel("Name").fill("Projects E2E User");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByRole("button", { name: "Sign up" }).click();
    await expect(page).toHaveURL(/\/overview$/);

    await page.goto("/projects/new");
    await page.getByLabel("Name").fill("Internal Tool");
    await page.getByLabel("Target URL").fill("http://127.0.0.1/admin");
    await page.getByRole("button", { name: "Create project" }).click();

    await expect(page.locator('[role="alert"]', { hasText: "private or internal address" })).toBeVisible();
    await expect(page).toHaveURL(/\/projects\/new$/);

    await page.getByLabel("Target URL").fill("https://example.com");
    await page.getByRole("button", { name: "Create project" }).click();

    await expect(page).toHaveURL(/\/projects\/[0-9a-f-]+$/);
    await expect(page.getByRole("heading", { name: "Internal Tool" })).toBeVisible();
    await expect(page.getByRole("link", { name: "https://example.com" })).toBeVisible();

    await page.goto("/projects");
    await expect(page.getByRole("cell", { name: "Internal Tool" })).toBeVisible();
  });

  test("second project is blocked by the free plan's project limit", async ({ page }) => {
    const email = `projects-limit-${Date.now()}@example.com`;
    const password = "correct horse battery staple limit";

    await page.goto("/signup");
    await page.getByLabel("Name").fill("Plan Limit E2E User");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByRole("button", { name: "Sign up" }).click();
    await expect(page).toHaveURL(/\/overview$/);

    await page.goto("/projects/new");
    await page.getByLabel("Name").fill("First Project");
    await page.getByLabel("Target URL").fill("https://example.com");
    await page.getByRole("button", { name: "Create project" }).click();
    await expect(page).toHaveURL(/\/projects\/[0-9a-f-]+$/);

    await page.goto("/projects/new");
    await page.getByLabel("Name").fill("Second Project");
    await page.getByLabel("Target URL").fill("https://example.com");
    await page.getByRole("button", { name: "Create project" }).click();

    await expect(page.locator('[role="alert"]', { hasText: "plan's project limit" })).toBeVisible();
  });

  test("archiving a project from its settings page updates its status", async ({ page }) => {
    const email = `projects-archive-${Date.now()}@example.com`;
    const password = "correct horse battery staple archive";

    await page.goto("/signup");
    await page.getByLabel("Name").fill("Archive E2E User");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByRole("button", { name: "Sign up" }).click();
    await expect(page).toHaveURL(/\/overview$/);

    await page.goto("/projects/new");
    await page.getByLabel("Name").fill("Archivable Project");
    await page.getByLabel("Target URL").fill("https://example.com");
    await page.getByRole("button", { name: "Create project" }).click();
    await expect(page).toHaveURL(/\/projects\/[0-9a-f-]+$/);

    await page.getByRole("navigation", { name: "Project" }).getByRole("link", { name: "Settings" }).click();
    await expect(page).toHaveURL(/\/settings$/);

    await page.getByRole("button", { name: "Archive", exact: true }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Archive", exact: true }).click();

    await expect(page.getByText("Project archived", { exact: true })).toBeVisible();
    await expect(page.getByText("archived", { exact: true })).toBeVisible();
  });
});
