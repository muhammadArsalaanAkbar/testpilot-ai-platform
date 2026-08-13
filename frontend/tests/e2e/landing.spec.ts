import { expect, test } from "@playwright/test";

test.describe("Landing page", () => {
  test("loads without authentication and shows the value proposition", async ({ page }) => {
    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: "Test your web app with AI, not automation scripts" }),
    ).toBeVisible();
  });

  test("primary CTA navigates to /signup", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("link", { name: "Start testing free" }).click();
    await expect(page).toHaveURL(/\/signup$/);
  });

  test("nav CTA also reaches /signup, and /login is reachable from the header", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("link", { name: "Log in" }).first()).toHaveAttribute(
      "href",
      "/login",
    );
    await page.getByRole("link", { name: "Sign up" }).first().click();
    await expect(page).toHaveURL(/\/signup$/);
  });

  test("pricing page is reachable and renders without authentication", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("link", { name: "See pricing" }).click();
    await expect(page).toHaveURL(/\/pricing$/);
    await expect(page.getByRole("heading", { name: /Plans that grow with your team/ })).toBeVisible();
  });
});
