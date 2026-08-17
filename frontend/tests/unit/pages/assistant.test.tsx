import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AssistantPage from "@/app/(dashboard)/assistant/page";
import { apiClient, ApiError } from "@/lib/api-client";

vi.mock("@/lib/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api-client")>();
  return {
    ...actual,
    apiClient: {
      ...actual.apiClient,
      get: vi.fn(),
      post: vi.fn(),
    },
  };
});

const mockedGet = vi.mocked(apiClient.get);
const mockedPost = vi.mocked(apiClient.post);

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }
  return render(<AssistantPage />, { wrapper: Wrapper });
}

beforeEach(() => {
  vi.clearAllMocks();
  Element.prototype.scrollIntoView = vi.fn();
  // Default: no projects, so the page starts in general (ungrounded) mode
  // unless a test overrides this with its own project list.
  mockedGet.mockResolvedValue({ items: [] });
});

describe("AssistantPage", () => {
  it("renders the assistant heading and description", async () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "AI QA Assistant" })).toBeInTheDocument();
    expect(screen.getByText(/Ask questions about your projects/)).toBeInTheDocument();
  });

  it("shows an empty state with suggested prompts before any message is sent", async () => {
    renderPage();
    expect(await screen.findByText("Ask the AI QA Assistant anything")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Suggest regression tests" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Explain the latest test failure" })).toBeInTheDocument();
  });

  it("sends the suggested prompt's text when clicked", async () => {
    mockedPost.mockResolvedValue({
      conversation_id: "11111111-1111-1111-1111-111111111111",
      message: "Here are some regression tests.",
      grounded: false,
      referenced_entities: [],
    });
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Suggest regression tests" }));

    expect(await screen.findByText("Suggest regression tests")).toBeInTheDocument();
    expect(mockedPost).toHaveBeenCalledWith("/assistant/chat", {
      message: "Suggest regression tests",
      conversation_id: null,
      project_id: null,
    });
    expect(await screen.findByText("Here are some regression tests.")).toBeInTheDocument();
  });

  it("sends a typed message via the composer and renders both bubbles", async () => {
    mockedPost.mockResolvedValue({
      conversation_id: "22222222-2222-2222-2222-222222222222",
      message: "Sure, here's an answer.",
      grounded: false,
      referenced_entities: [],
    });
    renderPage();
    const user = userEvent.setup();

    const input = await screen.findByLabelText("Message");
    await user.type(input, "What should I test next?");
    await user.click(screen.getByRole("button", { name: "Send message" }));

    expect(await screen.findByText("What should I test next?")).toBeInTheDocument();
    expect(await screen.findByText("Sure, here's an answer.")).toBeInTheDocument();
    expect(input).toHaveValue("");
  });

  it("disables the send button while empty and shows a loading indicator while a response is pending", async () => {
    let resolvePost!: (value: Awaited<ReturnType<typeof apiClient.post>>) => void;
    mockedPost.mockReturnValue(
      new Promise((resolve) => {
        resolvePost = resolve;
      }),
    );
    renderPage();
    const user = userEvent.setup();

    const sendButton = screen.getByRole("button", { name: "Send message" });
    expect(sendButton).toBeDisabled();

    const input = await screen.findByLabelText("Message");
    await user.type(input, "hello there");
    expect(sendButton).not.toBeDisabled();

    await user.click(sendButton);
    expect(await screen.findByLabelText("Assistant is typing")).toBeInTheDocument();
    expect(screen.getByLabelText("Message")).toBeDisabled();

    resolvePost({
      conversation_id: "33333333-3333-3333-3333-333333333333",
      message: "done",
      grounded: false,
      referenced_entities: [],
    });

    await waitFor(() => expect(screen.queryByLabelText("Assistant is typing")).not.toBeInTheDocument());
  });

  it("shows an inline error with retry when the request fails, without losing the sent message", async () => {
    mockedPost.mockRejectedValue(
      new ApiError(503, { error: { code: "assistant_unavailable", message: "The AI QA Assistant is temporarily unavailable" } }),
    );
    renderPage();
    const user = userEvent.setup();

    const input = await screen.findByLabelText("Message");
    await user.type(input, "will this fail?");
    await user.click(screen.getByRole("button", { name: "Send message" }));

    expect(await screen.findByText("will this fail?")).toBeInTheDocument();
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText("The AI QA Assistant is temporarily unavailable")).toBeInTheDocument();
    expect(within(alert).getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("renders markdown in the assistant's response", async () => {
    mockedPost.mockResolvedValue({
      conversation_id: "44444444-4444-4444-4444-444444444444",
      message: "Here is a **bold** point.",
      grounded: false,
      referenced_entities: [],
    });
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Suggest regression tests" }));

    const strong = await screen.findByText("bold");
    expect(strong.tagName).toBe("STRONG");
  });

  it("renders a citation link for each referenced entity in a grounded response", async () => {
    mockedPost.mockResolvedValue({
      conversation_id: "66666666-6666-6666-6666-666666666666",
      message: "Your login test case covers this.",
      grounded: true,
      referenced_entities: [
        {
          entity_type: "test_case",
          entity_id: "77777777-7777-7777-7777-777777777777",
          title: "Login with valid credentials",
          url: "/projects/p-1/test-cases/77777777-7777-7777-7777-777777777777",
        },
      ],
    });
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Suggest regression tests" }));

    const citationLink = await screen.findByRole("link", { name: /Test case:.*Login with valid credentials/ });
    expect(citationLink).toHaveAttribute("href", "/projects/p-1/test-cases/77777777-7777-7777-7777-777777777777");
  });

  it("renders no citations when the response has none", async () => {
    mockedPost.mockResolvedValue({
      conversation_id: "88888888-8888-8888-8888-888888888888",
      message: "General QA advice with nothing to cite.",
      grounded: false,
      referenced_entities: [],
    });
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Suggest regression tests" }));

    await screen.findByText("General QA advice with nothing to cite.");
    expect(screen.queryByRole("link", { name: /Test case:|Test run:|Issue:/ })).not.toBeInTheDocument();
  });

  it("keeps the same project selected for the rest of a conversation and sends it with each message", async () => {
    mockedGet.mockResolvedValue({
      items: [
        { id: "p-1", name: "Storefront", url: "https://a.example.com", status: "active" },
        { id: "p-2", name: "Admin Console", url: "https://b.example.com", status: "active" },
      ],
    });
    mockedPost.mockResolvedValue({
      conversation_id: "55555555-5555-5555-5555-555555555555",
      message: "Looking at Storefront now.",
      grounded: true,
      referenced_entities: [],
    });
    renderPage();
    const user = userEvent.setup();

    const projectSelect = await screen.findByLabelText("Project context");
    await user.selectOptions(projectSelect, "Storefront");

    const input = await screen.findByLabelText("Message");
    await user.type(input, "What's risky here?");
    await user.click(screen.getByRole("button", { name: "Send message" }));

    await screen.findByText("Looking at Storefront now.");
    expect(mockedPost).toHaveBeenCalledWith("/assistant/chat", {
      message: "What's risky here?",
      conversation_id: null,
      project_id: "p-1",
    });
    const groundedIndicator = await screen.findByText(/Grounded in/);
    expect(within(groundedIndicator).getByText("Storefront")).toBeInTheDocument();
    expect(projectSelect).toBeDisabled();
  });
});
