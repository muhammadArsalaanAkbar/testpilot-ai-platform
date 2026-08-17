import { expect, test } from "@playwright/test";

test.describe("AI QA Assistant chat (FR-097-FR-103)", () => {
  // Each test signs up a fresh user and immediately drives real chat
  // requests against the real (fake-provider) backend — running the two
  // tests in this file concurrently contends for the same dev-mode
  // Next.js/uvicorn processes and was observed to flake under the default
  // parallel workers; serial execution is cheap here (two short tests) and
  // trades a little wall-clock time for determinism.
  test.describe.configure({ mode: "serial" });

  test("sign up, open the assistant, and have a general (ungrounded) conversation", async ({ page }) => {
    const email = `assistant-e2e-${Date.now()}@example.com`;
    const password = "correct horse battery staple assistant";

    await page.goto("/signup");
    await page.getByLabel("Name").fill("Assistant E2E User");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByRole("button", { name: "Sign up" }).click();
    await expect(page).toHaveURL(/\/overview$/);

    await expect(page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "AI Assistant" })).toBeVisible();
    await page.goto("/assistant");

    await expect(page.getByText("Ask the AI QA Assistant anything")).toBeVisible();
    await expect(page.getByRole("button", { name: "Suggest regression tests" })).toBeVisible();

    await page.getByLabel("Message", { exact: true }).fill("What can you help me with?");
    await page.getByRole("button", { name: "Send message" }).click();

    await expect(page.getByText("What can you help me with?")).toBeVisible();
    await expect(page.getByLabel("Assistant is typing")).toBeVisible();
    await expect(page.getByText(/I received your message/)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByLabel("Assistant is typing")).toHaveCount(0);
  });

  test("a suggested prompt starts a project-grounded conversation", async ({ page }) => {
    const email = `assistant-grounded-e2e-${Date.now()}@example.com`;
    const password = "correct horse battery staple grounded";

    await page.goto("/signup");
    await page.getByLabel("Name").fill("Assistant Grounded E2E User");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByRole("button", { name: "Sign up" }).click();
    await expect(page).toHaveURL(/\/overview$/);

    await page.goto("/projects/new");
    await page.getByLabel("Name").fill("Assistant E2E Project");
    await page.getByLabel("Target URL").fill("https://example.com");
    await page.getByRole("button", { name: "Create project" }).click();
    await expect(page).toHaveURL(/\/projects\/[0-9a-f-]+$/);

    await page.goto("/assistant");

    // A single project auto-selects as context (no picker needed) —
    // reflected immediately in the "Grounded in" indicator. Matched by full
    // text (not a loose /Grounded in/ regex) since the empty state's own
    // description text also contains that phrase.
    const groundedIndicator = page.getByText(/^Grounded in Assistant E2E Project$/);
    await expect(groundedIndicator).toBeVisible();

    await page.getByRole("button", { name: "Suggest regression tests" }).click();

    await expect(page.getByText("Suggest regression tests").first()).toBeVisible();
    await expect(page.getByText(/I received your message/)).toBeVisible({ timeout: 15_000 });

    // Continuing the conversation keeps the same project — the picker (if
    // it were shown) would lock, but with a single project there is no
    // picker at all, so this is confirmed via the indicator persisting.
    await expect(groundedIndicator).toBeVisible();
  });
});
