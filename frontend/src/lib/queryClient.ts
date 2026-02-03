import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      gcTime: 1000 * 60 * 30, // 30 minutes
      retry: 1,
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: 0,
    },
  },
});

export const queryKeys = {
  auth: {
    me: ["auth", "me"] as const,
  },
  conversations: {
    all: ["conversations"] as const,
    list: (params?: { page?: number; pageSize?: number; includeArchived?: boolean }) =>
      ["conversations", "list", params] as const,
    detail: (id: string) => ["conversations", "detail", id] as const,
  },
  messages: {
    all: ["messages"] as const,
    list: (conversationId: string) => ["messages", "list", conversationId] as const,
  },
} as const;
