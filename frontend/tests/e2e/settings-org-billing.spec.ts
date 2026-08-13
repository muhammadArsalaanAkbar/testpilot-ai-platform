import { expect, test } from "@playwright/test";

test.describe("Settings: Organization, Billing, Members (Phase 6)", () => {
  test("owner can rename the workspace from Settings > Organization", async ({ page }) => {
    const email = `settings-org-${Date.now()}@example.com`;
    const password = "correct horse battery staple org";

    await page.goto("/signup");
    await page.getByLabel("Name").fill("Org Settings User");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByRole("button", { name: "Sign up" }).click();
    await expect(page).toHaveURL(/\/overview$/);

    await page.goto("/settings/organization");
    const nameField = page.getByLabel("Workspace name");
    await expect(nameField).toBeVisible();
    await nameField.fill("Renamed Workspace E2E");
    await page.getByRole("button", { name: "Save changes" }).click();

    await expect(page.getByText("Organization updated", { exact: true })).toBeVisible();

    await page.reload();
    await expect(page.getByLabel("Workspace name")).toHaveValue("Renamed Workspace E2E");
  });

  test("Settings > Billing shows the free plan and usage vs. limits", async ({ page }) => {
    const email = `settings-billing-${Date.now()}@example.com`;
    const password = "correct horse battery staple billing";

    await page.goto("/signup");
    await page.getByLabel("Name").fill("Billing Settings User");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByRole("button", { name: "Sign up" }).click();
    await expect(page).toHaveURL(/\/overview$/);

    await page.goto("/settings/billing");
    const main = page.getByRole("main");
    await expect(main.getByText("free", { exact: true })).toBeVisible();
    await expect(main.getByText("Projects")).toBeVisible();
    await expect(main.getByRole("progressbar").first()).toBeVisible();
  });

  test("Settings > Members lists the signed-up owner and shows the coming-soon invite notice", async ({ page }) => {
    const email = `settings-members-${Date.now()}@example.com`;
    const password = "correct horse battery staple members";

    await page.goto("/signup");
    await page.getByLabel("Name").fill("Members Settings User");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByRole("button", { name: "Sign up" }).click();
    await expect(page).toHaveURL(/\/overview$/);

    await page.goto("/settings/members");
    await expect(page.getByRole("cell", { name: email })).toBeVisible();
    await expect(page.getByRole("cell", { name: "owner" })).toBeVisible();
    await expect(page.getByText("Team invites are coming soon")).toBeVisible();
  });
});
