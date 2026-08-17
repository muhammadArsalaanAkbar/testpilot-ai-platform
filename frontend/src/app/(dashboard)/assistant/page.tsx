"use client";

import { AlertTriangle, Bot, Bug, ClipboardList, Play, RotateCcw, Send, Sparkles, User } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { Button } from "@/components/Button";
import { Card, CardContent } from "@/components/Card";
import { apiClient, ApiError } from "@/lib/api-client";
import { cn } from "@/lib/cn";
import { useAssistantChat } from "@/features/assistant/useAssistantChat";
import type { ChatCitation } from "@/features/assistant/useAssistantChat";

interface Project {
  id: string;
  name: string;
  url: string;
  status: "active" | "archived";
}

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: ChatCitation[];
}

const SUGGESTED_PROMPTS = [
  "Analyze my latest failed test",
  "Suggest regression tests",
  "Find gaps in my current test coverage",
  "Generate tests for the login flow",
  "Explain the latest test failure",
];

/**
 * AI QA Assistant (FR-023, FR-097-FR-103). Project context is chosen once,
 * before the first message — the backend fixes a conversation's project at
 * creation (assistant/service.py), so the picker locks once `conversationId`
 * exists rather than implying a mid-conversation switch is possible.
 *
 * Conversation history here is this-browser-session-only: the API persists
 * messages server-side but exposes no GET-history endpoint (matching
 * contracts/ai-provider-adapter.md's own "conversation history, this
 * session only" scope for what grounds a chat request).
 */
export default function AssistantPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const scrollAnchorRef = useRef<HTMLDivElement>(null);
  const chat = useAssistantChat();

  useEffect(() => {
    let cancelled = false;
    apiClient
      .get<{ items: Project[] }>("/projects")
      .then((data) => {
        if (cancelled) return;
        setProjects(data.items);
        const onlyProject = data.items.length === 1 ? data.items[0] : undefined;
        if (onlyProject) {
          setProjectId(onlyProject.id);
        }
      })
      .catch(() => {
        // The project list is a convenience for grounding, not required for
        // the assistant to function at all — a failed fetch just leaves the
        // page in general (ungrounded) mode instead of blocking it.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    scrollAnchorRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, chat.isPending]);

  async function sendToApi(text: string) {
    setErrorMessage(null);
    try {
      const response = await chat.mutateAsync({ message: text, conversationId, projectId });
      setConversationId(response.conversation_id);
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: response.message,
          citations: response.referenced_entities,
        },
      ]);
    } catch (err) {
      setErrorMessage(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    }
  }

  function handleSend(text: string) {
    const trimmed = text.trim();
    if (!trimmed || chat.isPending) return;
    setInput("");
    setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: "user", content: trimmed }]);
    void sendToApi(trimmed);
  }

  function handleRetry() {
    const lastUserMessage = [...messages].reverse().find((m) => m.role === "user");
    if (lastUserMessage) void sendToApi(lastUserMessage.content);
  }

  function handleNewConversation() {
    setMessages([]);
    setConversationId(null);
    setErrorMessage(null);
  }

  const selectedProject = projects.find((p) => p.id === projectId) ?? null;
  const hasStarted = messages.length > 0;

  return (
    <div className="mx-auto flex h-[calc(100vh-8rem)] max-w-3xl flex-col gap-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-subheading font-semibold text-foreground">AI QA Assistant</h2>
          <p className="mt-1 text-caption text-muted-foreground">
            Ask questions about your projects, test runs, failures, and issues.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {projects.length > 1 && (
            <select
              aria-label="Project context"
              value={projectId ?? ""}
              disabled={hasStarted}
              onChange={(e) => setProjectId(e.target.value || null)}
              className="h-9 rounded-md border border-border bg-background px-2 text-caption text-foreground disabled:opacity-60"
            >
              <option value="">General (no project)</option>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          )}
          {hasStarted && (
            <Button variant="outline" size="sm" onClick={handleNewConversation}>
              <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
              New chat
            </Button>
          )}
        </div>
      </div>

      {(selectedProject !== null || hasStarted) && (
        <div className="flex items-center gap-1.5 text-caption text-muted-foreground">
          <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
          {selectedProject ? (
            <span>
              Grounded in <span className="font-medium text-foreground">{selectedProject.name}</span>
            </span>
          ) : (
            <span>General assistant — not grounded in a specific project</span>
          )}
        </div>
      )}

      <Card className="flex flex-1 flex-col overflow-hidden">
        <CardContent className="flex flex-1 flex-col gap-4 overflow-y-auto p-4" aria-live="polite">
          {messages.length === 0 ? (
            <div className="flex flex-1 flex-col items-center justify-center gap-4 text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
                <Bot className="h-6 w-6 text-primary" aria-hidden="true" />
              </div>
              <div>
                <p className="text-body font-medium text-foreground">Ask the AI QA Assistant anything</p>
                <p className="mt-1 max-w-sm text-caption text-muted-foreground">
                  Grounded in your project&apos;s test cases, runs, and issues when a project is selected.
                </p>
              </div>
              <div className="flex flex-wrap justify-center gap-2">
                {SUGGESTED_PROMPTS.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    onClick={() => handleSend(prompt)}
                    className="rounded-full border border-border bg-muted/40 px-3 py-1.5 text-caption text-foreground transition-colors hover:bg-muted"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <>
              {messages.map((message) => (
                <MessageBubble key={message.id} message={message} />
              ))}
              {chat.isPending && <TypingBubble />}
              {errorMessage && (
                <div
                  role="alert"
                  className="flex items-center gap-3 rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2.5"
                >
                  <AlertTriangle className="h-4 w-4 shrink-0 text-destructive" aria-hidden="true" />
                  <p className="flex-1 text-caption text-foreground">{errorMessage}</p>
                  <Button variant="outline" size="sm" onClick={handleRetry}>
                    Retry
                  </Button>
                </div>
              )}
            </>
          )}
          <div ref={scrollAnchorRef} />
        </CardContent>

        <form
          className="flex items-center gap-2 border-t border-border p-3"
          onSubmit={(e) => {
            e.preventDefault();
            handleSend(input);
          }}
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask the AI QA Assistant..."
            aria-label="Message"
            disabled={chat.isPending}
            className="flex-1 rounded-md border border-border bg-background px-3 py-2 text-body text-foreground placeholder:text-muted-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
          />
          <Button type="submit" size="icon" disabled={!input.trim() || chat.isPending} aria-label="Send message">
            <Send className="h-4 w-4" aria-hidden="true" />
          </Button>
        </form>
      </Card>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={cn("flex gap-3", isUser && "flex-row-reverse")}>
      <div
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
          isUser ? "bg-secondary text-secondary-foreground" : "bg-primary/10 text-primary",
        )}
      >
        {isUser ? <User className="h-4 w-4" aria-hidden="true" /> : <Bot className="h-4 w-4" aria-hidden="true" />}
      </div>
      <div
        className={cn(
          "max-w-[80%] rounded-lg px-3 py-2 text-body",
          isUser ? "bg-primary text-primary-foreground" : "bg-muted text-foreground",
        )}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : (
          <ReactMarkdown
            components={{
              p: ({ ...props }) => <p className="mb-2 last:mb-0" {...props} />,
              ul: ({ ...props }) => <ul className="mb-2 list-disc pl-5 last:mb-0" {...props} />,
              ol: ({ ...props }) => <ol className="mb-2 list-decimal pl-5 last:mb-0" {...props} />,
              code: ({ ...props }) => <code className="rounded bg-background/60 px-1 py-0.5 text-caption" {...props} />,
              pre: ({ ...props }) => (
                <pre className="mb-2 overflow-x-auto rounded-md bg-background/60 p-2 text-caption last:mb-0" {...props} />
              ),
              a: ({ children, ...props }) => (
                <a className="underline underline-offset-2" target="_blank" rel="noreferrer" {...props}>
                  {children}
                </a>
              ),
            }}
          >
            {message.content}
          </ReactMarkdown>
        )}
        {!isUser && message.citations && message.citations.length > 0 && (
          <CitationList citations={message.citations} />
        )}
      </div>
    </div>
  );
}

const CITATION_ICON = { test_case: ClipboardList, test_run: Play, issue: Bug } as const;
const CITATION_LABEL = { test_case: "Test case", test_run: "Test run", issue: "Issue" } as const;

/** FR-102: server-validated references the answer is grounded in — every
 * citation here already survived assistant/service.py's authorization
 * check, so it's always safe to render as a direct link. */
function CitationList({ citations }: { citations: ChatCitation[] }) {
  return (
    <div className="mt-2 flex flex-wrap gap-1.5 border-t border-border/60 pt-2">
      {citations.map((citation) => {
        const Icon = CITATION_ICON[citation.entity_type];
        return (
          <Link
            key={`${citation.entity_type}:${citation.entity_id}`}
            href={citation.url}
            className="inline-flex items-center gap-1 rounded-full border border-border bg-background/60 px-2 py-1 text-caption text-foreground transition-colors hover:bg-background"
          >
            <Icon className="h-3 w-3 shrink-0 text-muted-foreground" aria-hidden="true" />
            <span className="text-muted-foreground">{CITATION_LABEL[citation.entity_type]}:</span>
            <span className="max-w-[16rem] truncate">{citation.title}</span>
          </Link>
        );
      })}
    </div>
  );
}

function TypingBubble() {
  return (
    <div className="flex gap-3" aria-label="Assistant is typing">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
        <Bot className="h-4 w-4" aria-hidden="true" />
      </div>
      <div className="flex items-center gap-1 rounded-lg bg-muted px-3 py-2.5">
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.3s]" />
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.15s]" />
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground" />
      </div>
    </div>
  );
}
