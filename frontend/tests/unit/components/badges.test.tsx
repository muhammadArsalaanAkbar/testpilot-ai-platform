import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusBadge } from "@/components/badges/StatusBadge";
import { SeverityBadge } from "@/components/badges/SeverityBadge";
import { PriorityBadge } from "@/components/badges/PriorityBadge";

describe("StatusBadge", () => {
  it.each([
    ["passed", "Passed"],
    ["failed", "Failed"],
    ["skipped", "Skipped"],
    ["running", "Running"],
    ["queued", "Queued"],
  ] as const)("renders visible text for status=%s, not color alone (UX-003)", (status, label) => {
    render(<StatusBadge status={status} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it("pairs the icon with text so meaning does not depend on color perception", () => {
    const { container } = render(<StatusBadge status="failed" />);
    // The icon is aria-hidden (decorative) — the accessible name comes from the text node.
    expect(container.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
    expect(screen.getByText("Failed")).toBeVisible();
  });
});

describe("SeverityBadge", () => {
  it.each([
    ["minor", "Minor"],
    ["major", "Major"],
    ["critical", "Critical"],
    ["blocker", "Blocker"],
  ] as const)("renders visible text for severity=%s", (severity, label) => {
    render(<SeverityBadge severity={severity} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });
});

describe("PriorityBadge", () => {
  it.each([
    ["low", "Low"],
    ["medium", "Medium"],
    ["high", "High"],
    ["critical", "Critical"],
  ] as const)("renders visible text for priority=%s", (priority, label) => {
    render(<PriorityBadge priority={priority} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });
});
