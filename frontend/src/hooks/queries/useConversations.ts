import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { conversationsApi } from "@/api";
import { PAGINATION } from "@/lib/constants";
import { queryKeys } from "@/lib/queryClient";
import type { ConversationCreatePayload, ConversationUpdatePayload } from "@/types";

interface UseConversationsOptions {
  includeArchived?: boolean;
  pageSize?: number;
}

export function useConversations(options?: UseConversationsOptions) {
  const { includeArchived = false, pageSize = PAGINATION.DEFAULT_PAGE_SIZE } = options ?? {};

  return useInfiniteQuery({
    queryKey: queryKeys.conversations.list({ includeArchived, pageSize }),
    queryFn: ({ pageParam = 1 }) =>
      conversationsApi.list({
        page: pageParam,
        page_size: pageSize,
        include_archived: includeArchived,
      }),
    getNextPageParam: (lastPage) => (lastPage.has_more ? lastPage.page + 1 : undefined),
    initialPageParam: 1,
  });
}

export function useConversation(id: string | null) {
  return useQuery({
    queryKey: queryKeys.conversations.detail(id ?? ""),
    queryFn: () => {
      if (!id) throw new Error("Conversation ID is required");
      return conversationsApi.get(id);
    },
    enabled: !!id,
  });
}

export function useCreateConversation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload?: ConversationCreatePayload) => conversationsApi.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.conversations.all });
    },
  });
}

export function useUpdateConversation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: ConversationUpdatePayload }) =>
      conversationsApi.update(id, payload),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.conversations.detail(data.id), data);
      queryClient.invalidateQueries({ queryKey: queryKeys.conversations.all });
    },
  });
}

export function useDeleteConversation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => conversationsApi.delete(id),
    onSuccess: (_, id) => {
      queryClient.removeQueries({ queryKey: queryKeys.conversations.detail(id) });
      queryClient.invalidateQueries({ queryKey: queryKeys.conversations.all });
    },
  });
}
