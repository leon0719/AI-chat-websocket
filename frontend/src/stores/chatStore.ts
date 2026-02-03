import { create } from "zustand";
import type { Message } from "@/types";

interface StreamingMessage {
  id: string;
  content: string;
  isStreaming: boolean;
}

interface ChatState {
  currentConversationId: string | null;
  streamingMessage: StreamingMessage | null;
  pendingUserMessage: Message | null;

  setCurrentConversationId: (id: string | null) => void;
  startStreaming: (id: string) => void;
  appendStreamContent: (content: string) => void;
  finishStreaming: (messageId: string) => void;
  clearStreaming: () => void;
  setPendingUserMessage: (message: Message | null) => void;
}

export const useChatStore = create<ChatState>((set) => ({
  currentConversationId: null,
  streamingMessage: null,
  pendingUserMessage: null,

  setCurrentConversationId: (id) => set({ currentConversationId: id }),

  startStreaming: (id) =>
    set({
      streamingMessage: { id, content: "", isStreaming: true },
    }),

  appendStreamContent: (content) =>
    set((state) => ({
      streamingMessage: state.streamingMessage
        ? {
            ...state.streamingMessage,
            content: state.streamingMessage.content + content,
          }
        : null,
    })),

  finishStreaming: (messageId) =>
    set((state) => ({
      streamingMessage: state.streamingMessage
        ? {
            ...state.streamingMessage,
            id: messageId,
            isStreaming: false,
          }
        : null,
    })),

  clearStreaming: () => set({ streamingMessage: null }),
  setPendingUserMessage: (message) => set({ pendingUserMessage: message }),
}));
