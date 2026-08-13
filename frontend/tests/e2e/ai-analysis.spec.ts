import { expect, test } from "@playwright/test";

// Same dev-mode first-visit-compile latency rationale as test-runs.spec.ts.
const NAV_TIMEOUT = { timeout: 15_000 };

test.describe("AI failure analysis (Phase 13)", () => {
  test("request analysis on a failed result and see the explanation, then see the distinct unavailable state", async ({
    page,
  }) => {
    // A real test-run execution plus a real AI-analysis round trip (real
    // Redis-queued job, real worker, real fake-provider call) — well beyond
    // the 30s default budget.
    test.setTimeout(120_000);

    const email = `ai-analysis-e2e-${Date.now()}@example.com`;
    const password = "correct horse battery staple ai analysis";

    await page.goto("/signup");
    await page.getByLabel("Name").fill("AI Analysis E2E User");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByRole("button", { name: "Sign up" }).click();
    await expect(page).toHaveURL(/\/overview$/, NAV_TIMEOUT);

    await page.goto("/projects/new");
    await page.getByLabel("Name").fill("AI Analysis Project");
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

    // Real AI analysis: a real enqueue, a real worker, the real (fake, per
    // AI_PROVIDER=fake in this dev environment) provider producing a real
    // deterministic explanation — not mocked at the HTTP layer.
    await expect(page.getByRole("heading", { name: "AI Failure Analysis" })).toBeVisible();
    await page.getByRole("button", { name: "Request AI analysis" }).click();
    await expect(page.getByText("Analyzing this failure…")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Explanation" })).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole("heading", { name: "Root cause" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Expected vs. actual" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Suggested fix" })).toBeVisible();

    // The distinct "unavailable" state (FR-083): intercept only the
    // polling GET for the *next* analysis (the re-analyze POST itself
    // still hits the real backend, reserving real usage and enqueuing a
    // real job) and fulfill it as a failed analysis — the backend's own
    // genuine provider-failure path is already covered by
    // tests/integration/test_ai_analysis_failure.py; this verifies the
    // frontend renders that real response shape distinctly, without
    // needing to reconfigure a live worker process mid-test.
    await page.route("**/analyses/**", async (route) => {
      const url = route.request().url();
      const analysisId = url.split("/analyses/")[1];
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: analysisId,
          test_result_id: "00000000-0000-0000-0000-000000000000",
          status: "failed",
          explanation: null,
          root_cause: null,
          severity: null,
          suggested_fix: null,
          expected_vs_actual: "",
          failure_reason: "Simulated provider timeout",
          provider: "fake",
          model: "fake-deterministic",
          created_at: new Date().toISOString(),
        }),
      });
    });

    await page.getByRole("button", { name: "Re-analyze" }).click();
    await expect(page.getByText("Analysis unavailable", { exact: true })).toBeVisible(NAV_TIMEOUT);
    await expect(page.getByText("Simulated provider timeout")).toBeVisible();
    // Distinct from the empty "no analysis requested yet" state and from
    // the completed explanation view — never a fabricated result.
    await expect(page.getByRole("heading", { name: "Explanation" })).not.toBeVisible();
  });
});
