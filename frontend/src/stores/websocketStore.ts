import { create } from "zustand";
import type { WSConnectionStatus, WSErrorCode } from "@/types";

interface WebSocketState {
  status: WSConnectionStatus;
  error: { message: string; code: WSErrorCode } | null;
  conversationId: string | null;

  setStatus: (status: WSConnectionStatus) => void;
  setError: (error: { message: string; code: WSErrorCode } | null) => void;
  setConversationId: (id: string | null) => void;
  reset: () => void;
}

export const useWebSocketStore = create<WebSocketState>((set) => ({
  status: "disconnected",
  error: null,
  conversationId: null,

  setStatus: (status) => set({ status }),
  setError: (error) =>
    set((state) => ({
      error,
      status: error ? "error" : state.status,
    })),
  setConversationId: (id) => set({ conversationId: id }),
  reset: () =>
    set({
      status: "disconnected",
      error: null,
      conversationId: null,
    }),
}));
