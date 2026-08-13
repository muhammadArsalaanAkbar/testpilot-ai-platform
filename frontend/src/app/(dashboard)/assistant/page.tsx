"use client";

import { Bot, Send, Sparkles } from "lucide-react";
import { Card, CardContent } from "@/components/Card";

/**
 * AI QA Assistant (FR-023, FR-097-FR-103) — Phase 15 "Scaffold Only": the
 * nav entry point and this page exist so the capability is honestly visible
 * rather than silently missing, but the conversational interface itself is
 * Future work. The composer below is deliberately disabled, not a fake chat
 * that pretends to respond (FR-100's "never silently fail or fabricate an
 * answer" extends to not simulating a working feature before it exists).
 */
export default function AssistantPage() {
  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6">
      <div>
        <h2 className="text-subheading font-semibold text-foreground">AI QA Assistant</h2>
        <p className="mt-1 text-caption text-muted-foreground">
          Ask questions about your projects, test runs, failures, and issues.
        </p>
      </div>

      <Card className="border-dashed">
        <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
            <Bot className="h-6 w-6 text-primary" aria-hidden="true" />
          </div>
          <p className="text-body font-medium text-foreground">The AI QA Assistant is coming soon</p>
          <p className="max-w-sm text-caption text-muted-foreground">
            A conversational assistant that can answer questions grounded in your Organization&apos;s actual test
            cases, runs, failures, and issues — with links back to what it references — is planned for a future
            release.
          </p>
          <div className="mt-1 flex items-center gap-1.5 text-caption text-muted-foreground">
            <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
            This entry point is reserved so you know it&apos;s on the way.
          </div>
        </CardContent>
      </Card>

      <div className="flex items-center gap-2 rounded-md border border-border bg-muted/40 px-3 py-2 opacity-60">
        <input
          type="text"
          disabled
          placeholder="Ask the AI QA Assistant..."
          aria-label="Ask the AI QA Assistant (not available yet)"
          className="flex-1 bg-transparent text-body text-foreground placeholder:text-muted-foreground focus:outline-none"
        />
        <Send className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      </div>
    </div>
  );
}
