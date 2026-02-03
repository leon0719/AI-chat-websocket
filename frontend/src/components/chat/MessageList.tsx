import { MessageCircle } from "lucide-react";
import { useEffect } from "react";
import { StickToBottom, useStickToBottomContext } from "use-stick-to-bottom";
import { useShallow } from "zustand/react/shallow";
import { EmptyState, LoadingSpinner } from "@/components/common";
import { useInvalidateMessages, useMessages } from "@/hooks";
import { useChatStore } from "@/stores";
import type { Message } from "@/types";
import { MessageItem, StreamingMessage } from "./MessageItem";

interface MessageListProps {
  conversationId: string;
}

type StreamingItem = { type: "streaming"; id: string; content: string; isStreaming: boolean };
type ListItem = Message | StreamingItem;

function isStreamingItem(item: ListItem): item is StreamingItem {
  return "type" in item && item.type === "streaming";
}

function LoadMoreButton({
  hasNextPage,
  isFetchingNextPage,
  onLoadMore,
}: {
  hasNextPage: boolean;
  isFetchingNextPage: boolean;
  onLoadMore: () => void;
}) {
  if (!hasNextPage) return null;

  return (
    <div className="py-4 text-center">
      <button
        type="button"
        className="text-sm text-muted-foreground hover:text-foreground"
        onClick={onLoadMore}
        disabled={isFetchingNextPage}
      >
        {isFetchingNextPage ? <LoadingSpinner size="sm" /> : "載入更早的訊息"}
      </button>
    </div>
  );
}

function ScrollToBottomButton() {
  const { isAtBottom, scrollToBottom } = useStickToBottomContext();

  if (isAtBottom) return null;

  return (
    <button
      type="button"
      className="absolute bottom-4 left-1/2 -translate-x-1/2 rounded-full bg-background/80 p-2 shadow-lg ring-1 ring-border backdrop-blur-sm transition-opacity hover:bg-background"
      onClick={() => scrollToBottom()}
      aria-label="滾動到底部"
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="20"
        height="20"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d="M12 5v14" />
        <path d="m19 12-7 7-7-7" />
      </svg>
    </button>
  );
}

export function MessageList({ conversationId }: MessageListProps) {
  const { data, isLoading, hasNextPage, fetchNextPage, isFetchingNextPage } =
    useMessages(conversationId);
  const { streamingMessage, pendingUserMessage } = useChatStore(
    useShallow((s) => ({
      streamingMessage: s.streamingMessage,
      pendingUserMessage: s.pendingUserMessage,
    })),
  );
  const invalidateMessages = useInvalidateMessages(conversationId);

  const messages = data?.messages ?? [];

  const allItems: ListItem[] = [
    ...messages,
    ...(pendingUserMessage ? [pendingUserMessage] : []),
    ...(streamingMessage && !messages.some((m) => m.id === streamingMessage.id)
      ? [{ type: "streaming" as const, ...streamingMessage }]
      : []),
  ];

  useEffect(() => {
    if (streamingMessage && !streamingMessage.isStreaming) {
      invalidateMessages();
    }
  }, [streamingMessage, invalidateMessages]);

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (messages.length === 0 && !pendingUserMessage && !streamingMessage) {
    return (
      <EmptyState
        icon={MessageCircle}
        title="開始對話"
        description="在下方輸入您的訊息開始與 AI 對話"
        className="h-full"
      />
    );
  }

  return (
    <StickToBottom className="relative flex-1" resize="smooth" initial="instant">
      <StickToBottom.Content className="flex flex-col overflow-auto">
        <div className="mx-auto w-full max-w-3xl pt-20">
          <LoadMoreButton
            hasNextPage={hasNextPage ?? false}
            isFetchingNextPage={isFetchingNextPage}
            onLoadMore={() => fetchNextPage()}
          />
          {allItems.map((item) =>
            isStreamingItem(item) ? (
              <StreamingMessage
                key={item.id}
                content={item.content}
                isStreaming={item.isStreaming}
              />
            ) : (
              <MessageItem key={item.id} message={item} />
            ),
          )}
        </div>
      </StickToBottom.Content>
      <ScrollToBottomButton />
    </StickToBottom>
  );
}
