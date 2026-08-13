import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Vitest does not auto-register React Testing Library's cleanup the way Jest
// does unless `test.globals: true` is set; doing it explicitly here works
// regardless of that setting and avoids DOM leaking between tests in the
// same file (which otherwise causes false "multiple elements found" errors).
afterEach(() => {
  cleanup();
});
