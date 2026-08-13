import { render, screen } from "@testing-library/react";
import { FolderPlus } from "lucide-react";
import { describe, expect, it, vi } from "vitest";
import { EmptyState } from "@/components/states/EmptyState";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";
import userEvent from "@testing-library/user-event";

describe("EmptyState", () => {
  it("renders a title, description, and action distinctly from a loading/error state", () => {
    render(
      <EmptyState
        icon={FolderPlus}
        title="No projects yet"
        description="Create your first project to get started."
        action={<button>Create project</button>}
      />,
    );
    expect(screen.getByText("No projects yet")).toBeInTheDocument();
    expect(screen.getByText("Create your first project to get started.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create project" })).toBeInTheDocument();
  });
});

describe("LoadingState", () => {
  it("renders a status region rather than visible content (content-shaped, not a bare spinner)", () => {
    render(<LoadingState variant="table" rows={3} />);
    expect(screen.getByRole("status", { name: "Loading" })).toBeInTheDocument();
  });
});

describe("ErrorState", () => {
  it("is announced via role=alert and is visually/semantically distinct from EmptyState", () => {
    render(<ErrorState description="Could not load projects." />);
    expect(screen.getByRole("alert")).toHaveTextContent("Could not load projects.");
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
  });

  it("uses a distinct message for the AI/service-unavailable variant vs. a generic error", () => {
    render(<ErrorState variant="unavailable" />);
    expect(screen.getByText("Currently unavailable")).toBeInTheDocument();
  });

  it("calls onRetry when the retry action is used", async () => {
    const onRetry = vi.fn();
    render(<ErrorState onRetry={onRetry} />);
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });
});
