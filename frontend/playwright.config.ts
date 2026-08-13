import { defineConfig, devices } from "@playwright/test";

/**
 * E2E tests for the TestPilot AI *dashboard itself* — distinct from the
 * product's own Playwright-powered test execution engine (backend/src/testpilot/execution/),
 * which drives arbitrary user-supplied target sites, not this codebase's UI.
 */
export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? "dot" : "list",
  use: {
    // Deliberately not port 3000: this machine already runs an unrelated
    // dev server there (a different project). 3200 is TestPilot-specific to
    // avoid ever colliding with it.
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3200",
    trace: "on-first-retry",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: {
    command: "npm run dev",
    url: "http://localhost:3200",
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
