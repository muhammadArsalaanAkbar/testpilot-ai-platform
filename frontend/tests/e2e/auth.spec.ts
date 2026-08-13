import { expect, test } from "@playwright/test";

const MAILHOG_API = process.env.MAILHOG_API_URL ?? "http://localhost:8025/api/v2/messages";

interface MailhogMessage {
  To: Array<{ Mailbox: string; Domain: string }>;
  Content: { Body: string };
}

/** Polls Mailhog's HTTP API for the most recent email sent to `email`,
 * mirroring quickstart.md's "check your local mail catcher" flow — this is
 * what actually proves the password-reset email (and its token) exist,
 * rather than trusting the UI's "check your email" copy alone. */
async function getLatestEmailBodyFor(email: string): Promise<string> {
  const [mailbox] = email.split("@");
  for (let attempt = 0; attempt < 20; attempt++) {
    const response = await fetch(MAILHOG_API);
    const data = (await response.json()) as { items: MailhogMessage[] };
    const match = data.items.find((item) => item.To.some((to) => to.Mailbox === mailbox));
    if (match) return match.Content.Body;
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`No email found for ${email} after polling Mailhog`);
}

function extractResetLink(body: string): string {
  const match = body.match(/(\/reset-password\?token=[A-Za-z0-9_-]+)/);
  if (!match) throw new Error(`No reset link found in email body: ${body}`);
  return match[1]!;
}

test.describe("Authentication flow (quickstart.md Section 3)", () => {
  test("signup, logout, login, forgot-password, reset-password, login with new password", async ({
    page,
  }) => {
    const uniqueEmail = `e2e-${Date.now()}@example.com`;
    const originalPassword = "original strong e2e password";
    const newPassword = "brand new strong e2e password";

    // 1. Sign up
    await page.goto("/signup");
    await page.getByLabel("Name").fill("E2E Test User");
    await page.getByLabel("Email").fill(uniqueEmail);
    await page.getByLabel("Password", { exact: true }).fill(originalPassword);
    await page.getByRole("button", { name: "Sign up" }).click();
    await expect(page).toHaveURL(/\/overview$/);

    // 2. Log out — should land back on the login page when visiting a
    // protected route afterward.
    // (No dashboard shell yet at this point in the build — Overview is a
    // placeholder page reachable only because auth succeeded; logging out
    // is exercised via the auth context directly through a fresh page load
    // of a protected route once Phase 5 adds real logout UI. For now we
    // prove logout via the API-backed session ending: reloading after
    // clearing the browser context's cookies simulates the session ending.)
    await page.context().clearCookies();
    await page.goto("/overview");
    await expect(page).toHaveURL(/\/login$/);

    // 3. Log back in with the original password
    await page.goto("/login");
    await page.getByLabel("Email").fill(uniqueEmail);
    await page.getByLabel("Password").fill(originalPassword);
    await page.getByRole("button", { name: "Log in" }).click();
    await expect(page).toHaveURL(/\/overview$/);

    // 4. Forgot password
    await page.context().clearCookies();
    await page.goto("/forgot-password");
    await page.getByLabel("Email").fill(uniqueEmail);
    await page.getByRole("button", { name: "Send reset link" }).click();
    await expect(page.getByText("Check your email")).toBeVisible();

    // 5. Retrieve the reset link from Mailhog and follow it
    const emailBody = await getLatestEmailBodyFor(uniqueEmail);
    const resetPath = extractResetLink(emailBody);
    await page.goto(resetPath);
    await page.getByLabel("New password").fill(newPassword);
    await page.getByRole("button", { name: "Update password" }).click();
    await expect(page.getByText("Password updated")).toBeVisible();

    // 6. Log in with the new password
    await page.getByRole("link", { name: "Log in" }).click();
    await page.getByLabel("Email").fill(uniqueEmail);
    await page.getByLabel("Password").fill(newPassword);
    await page.getByRole("button", { name: "Log in" }).click();
    await expect(page).toHaveURL(/\/overview$/);
  });

  test("signup rejects a weak password with a visible error", async ({ page }) => {
    await page.goto("/signup");
    await page.getByLabel("Name").fill("Weak Password User");
    await page.getByLabel("Email").fill(`weak-${Date.now()}@example.com`);
    await page.getByLabel("Password", { exact: true }).fill("short");
    const submitButton = page.getByRole("button", { name: "Sign up" });
    await submitButton.click();
    // Wait for the in-flight submit (loading=true disables the button, see
    // Button.tsx) to resolve before asserting on its result — the request
    // is real (server-side password-strength validation), so a fixed short
    // timeout on the assertion below would be racy under dev-server latency.
    await expect(submitButton).toBeEnabled({ timeout: 15_000 });
    // Matches on the role element's text content directly (not accessible
    // name via getByRole's {name} regex option — Next.js also renders its
    // own empty role="alert" route-announcer on every page, and matching by
    // rendered text content is the more predictable way to disambiguate).
    await expect(page.locator('[role="alert"]', { hasText: "password must be at least 10 characters" })).toBeVisible();
    await expect(page).toHaveURL(/\/signup$/);
  });

  test("login rejects incorrect credentials with a visible error", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill("nonexistent-e2e-user@example.com");
    await page.getByLabel("Password").fill("whatever password");
    const submitButton = page.getByRole("button", { name: "Log in" });
    await submitButton.click();
    await expect(submitButton).toBeEnabled({ timeout: 15_000 });
    await expect(page.locator('[role="alert"]', { hasText: "Incorrect email or password" })).toBeVisible();
  });
});
