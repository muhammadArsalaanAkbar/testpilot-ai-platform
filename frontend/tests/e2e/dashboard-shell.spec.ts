import { expect, test } from "@playwright/test";

test.describe("Dashboard shell (Phase 5)", () => {
  test("authenticated user lands on Overview after login and sees sidebar nav", async ({ page }) => {
    const email = `dashboard-shell-${Date.now()}@example.com`;
    const password = "correct horse battery staple shell";

    await page.goto("/signup");
    await page.getByLabel("Name").fill("Dashboard Shell User");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByRole("button", { name: "Sign up" }).click();

    await expect(page).toHaveURL(/\/overview$/);
    await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();

    // Sidebar nav (FR-020): every MVP top-level section is present and reachable.
    const nav = page.getByRole("navigation", { name: "Primary" });
    await expect(nav.getByRole("link", { name: "Overview" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Projects" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "AI Assistant" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Settings" })).toBeVisible();

    // Active-state indication (UX-002): the current route is marked.
    await expect(nav.getByRole("link", { name: "Overview" })).toHaveAttribute("aria-current", "page");
  });

  test("unauthenticated visitor is redirected away from a protected route", async ({ page }) => {
    await page.goto("/overview");
    await expect(page).toHaveURL(/\/login$/);
  });

  test("logging out returns the user to the login page and ends the session", async ({ page }) => {
    const email = `dashboard-logout-${Date.now()}@example.com`;
    const password = "correct horse battery staple logout";

    await page.goto("/signup");
    await page.getByLabel("Name").fill("Logout Test User");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByRole("button", { name: "Sign up" }).click();
    await expect(page).toHaveURL(/\/overview$/);

    await page.getByRole("button", { name: /Organization/ }).click();
    await page.getByRole("menuitem", { name: /Log out/ }).click();
    await expect(page).toHaveURL(/\/login$/);

    // The session is actually ended server-side, not just client-navigated away.
    await page.goto("/overview");
    await expect(page).toHaveURL(/\/login$/);
  });
});
