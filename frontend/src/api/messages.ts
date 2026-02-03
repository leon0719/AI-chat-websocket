import type { PaginatedMessages, PaginationParams } from "@/types";
import { apiClient } from "./client";

export const messagesApi = {
  list: async (conversationId: string, params?: PaginationParams): Promise<PaginatedMessages> => {
    const { data } = await apiClient.get<PaginatedMessages>(
      `/conversations/${conversationId}/messages`,
      { params },
    );
    return data;
  },
};
