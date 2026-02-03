import { MessageCircle, WifiOff } from "lucide-react";
import { useCallback, useState } from "react";
import { useShallow } from "zustand/react/shallow";
import { EmptyState, LoadingSpinner } from "@/components/common";
import { Button } from "@/components/ui";
import {
  useConversation,
  useCreateConversation,
  useInvalidateMessages,
  useMessages,
  useWebSocket,
} from "@/hooks";
import { DEFAULT_MODEL } from "@/lib/constants";
import { useChatStore, useWebSocketStore } from "@/stores";
import { MessageInput } from "./MessageInput";
import { MessageList } from "./MessageList";
import { WelcomeScreen } from "./WelcomeScreen";

interface ChatAreaProps {
  conversationId: string;
}

export function ChatArea({ conversationId }: ChatAreaProps) {
  const { status, error } = useWebSocketStore(
    useShallow((s) => ({ status: s.status, error: s.error })),
  );
  const {
    clearStreaming,
    setPendingUserMessage,
    streamingMessage,
    pendingUserMessage,
    setCurrentConversationId,
  } = useChatStore(
    useShallow((s) => ({
      clearStreaming: s.clearStreaming,
      setPendingUserMessage: s.setPendingUserMessage,
      streamingMessage: s.streamingMessage,
      pendingUserMessage: s.pendingUserMessage,
      setCurrentConversationId: s.setCurrentConversationId,
    })),
  );
  const invalidateMessages = useInvalidateMessages(conversationId);
  const { data: messagesData, isLoading: isLoadingMessages } = useMessages(conversationId);
  const { data: conversation } = useConversation(conversationId);
  const createConversation = useCreateConversation();
  const [selectedModel, setSelectedModel] = useState<string | undefined>(undefined);

  // 當 conversation 載入後，同步模型
  const currentModel = selectedModel || conversation?.model || DEFAULT_MODEL;

  const { sendMessage, connect } = useWebSocket({
    conversationId,
    onStream: (message) => {
      if (message.done) {
        setPendingUserMessage(null);
        invalidateMessages();
      }
    },
    onError: () => {
      setPendingUserMessage(null);
      clearStreaming();
    },
  });

  const handleSend = useCallback(
    (content: string) => {
      return sendMessage(content);
    },
    [sendMessage],
  );

  const handleModelChange = useCallback(
    (modelId: string) => {
      createConversation.mutate(
        { model: modelId },
        {
          onSuccess: (newConversation) => {
            setCurrentConversationId(newConversation.id);
            setSelectedModel(modelId);
          },
        },
      );
    },
    [createConversation, setCurrentConversationId],
  );

  const messages = messagesData?.messages ?? [];
  const hasMessages = messages.length > 0 || pendingUserMessage || streamingMessage;

  if (status === "connecting" || status === "authenticating") {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-4">
        <LoadingSpinner size="lg" />
        <p className="text-sm text-muted-foreground">
          {status === "connecting" ? "連接中..." : "認證中..."}
        </p>
      </div>
    );
  }

  if (status === "error" || error) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-4">
        <EmptyState
          icon={WifiOff}
          title="連接失敗"
          description={error?.message || "無法連接到伺服器"}
          action={
            <Button onClick={connect} variant="outline">
              重新連接
            </Button>
          }
        />
      </div>
    );
  }

  if (isLoadingMessages) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-4">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (!hasMessages) {
    return (
      <WelcomeScreen
        onSend={handleSend}
        selectedModel={currentModel}
        onModelChange={handleModelChange}
      />
    );
  }

  return (
    <div className="flex flex-1 flex-col">
      <MessageList conversationId={conversationId} />
      <MessageInput
        onSend={handleSend}
        selectedModel={currentModel}
        onModelChange={handleModelChange}
      />
    </div>
  );
}

export function ChatAreaEmpty() {
  return (
    <div className="flex flex-1 items-center justify-center">
      <EmptyState
        icon={MessageCircle}
        title="選擇對話"
        description="從左側選擇一個對話或建立新對話"
      />
    </div>
  );
}
