"use client";

import { useMutation } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export interface ChatResponseBody {
  conversation_id: string;
  message: string;
  grounded: boolean;
  referenced_entities: string[];
}

interface SendMessageInput {
  message: string;
  conversationId: string | null;
  projectId: string | null;
}

/**
 * POST /assistant/chat is synchronous — one mutation call per message, no
 * polling (unlike useAIAnalysis.ts's job-status pattern). The backend keeps
 * conversation history server-side (assistant_conversations/assistant_messages),
 * but has no GET-history endpoint (contracts/ai-provider-adapter.md scopes
 * grounding to "conversation history, this session only") — the page
 * component owns the in-memory message list for the active browser session.
 */
export function useAssistantChat() {
  return useMutation({
    mutationFn: ({ message, conversationId, projectId }: SendMessageInput) =>
      apiClient.post<ChatResponseBody>("/assistant/chat", {
        message,
        conversation_id: conversationId,
        project_id: projectId,
      }),
  });
}
