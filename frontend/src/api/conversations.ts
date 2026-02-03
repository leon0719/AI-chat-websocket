import type {
  Conversation,
  ConversationCreatePayload,
  ConversationUpdatePayload,
  PaginatedConversations,
  PaginationParams,
} from "@/types";
import { apiClient } from "./client";

interface ListConversationsParams extends PaginationParams {
  include_archived?: boolean;
}

export const conversationsApi = {
  list: async (params?: ListConversationsParams): Promise<PaginatedConversations> => {
    const { data } = await apiClient.get<PaginatedConversations>("/conversations/", {
      params,
    });
    return data;
  },

  get: async (id: string): Promise<Conversation> => {
    const { data } = await apiClient.get<Conversation>(`/conversations/${id}`);
    return data;
  },

  create: async (payload?: ConversationCreatePayload): Promise<Conversation> => {
    const { data } = await apiClient.post<Conversation>("/conversations/", payload ?? {});
    return data;
  },

  update: async (id: string, payload: ConversationUpdatePayload): Promise<Conversation> => {
    const { data } = await apiClient.patch<Conversation>(`/conversations/${id}`, payload);
    return data;
  },

  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/conversations/${id}`);
  },
};
