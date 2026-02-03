import { useInfiniteQuery, useQueryClient } from "@tanstack/react-query";
import { messagesApi } from "@/api";
import { PAGINATION } from "@/lib/constants";
import { queryKeys } from "@/lib/queryClient";
import type { Message, PaginatedMessages } from "@/types";

interface UseMessagesOptions {
  pageSize?: number;
}

export function useMessages(conversationId: string | null, options?: UseMessagesOptions) {
  const { pageSize = PAGINATION.MESSAGES_PAGE_SIZE } = options ?? {};

  return useInfiniteQuery({
    queryKey: queryKeys.messages.list(conversationId ?? ""),
    queryFn: ({ pageParam = 1 }) => {
      if (!conversationId) throw new Error("Conversation ID is required");
      return messagesApi.list(conversationId, { page: pageParam, page_size: pageSize });
    },
    getNextPageParam: (lastPage) => (lastPage.has_more ? lastPage.page + 1 : undefined),
    initialPageParam: 1,
    enabled: !!conversationId,
    select: (data) => ({
      pages: data.pages,
      pageParams: data.pageParams,
      messages: data.pages.flatMap((page) => page.messages),
    }),
  });
}

export function useAddOptimisticMessage(conversationId: string | null) {
  const queryClient = useQueryClient();

  return (message: Message) => {
    if (!conversationId) return;

    queryClient.setQueryData<{
      pages: PaginatedMessages[];
      pageParams: number[];
    }>(queryKeys.messages.list(conversationId), (old) => {
      if (!old) return old;

      const newPages = [...old.pages];
      if (newPages.length > 0) {
        const lastPage = { ...newPages[newPages.length - 1] };
        lastPage.messages = [...lastPage.messages, message];
        newPages[newPages.length - 1] = lastPage;
      }

      return {
        ...old,
        pages: newPages,
      };
    });
  };
}

export function useInvalidateMessages(conversationId: string | null) {
  const queryClient = useQueryClient();

  return () => {
    if (!conversationId) return;
    queryClient.invalidateQueries({
      queryKey: queryKeys.messages.list(conversationId),
    });
  };
}
