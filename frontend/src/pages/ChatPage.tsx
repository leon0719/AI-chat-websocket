import { useShallow } from "zustand/react/shallow";
import { ChatArea, ChatAreaEmpty } from "@/components/chat/ChatArea";
import { ConversationList } from "@/components/chat/ConversationList";
import { useChatStore } from "@/stores";

export function ChatPage() {
  const currentConversationId = useChatStore(useShallow((s) => s.currentConversationId));

  return (
    <>
      <ConversationList />
      {currentConversationId ? (
        <ChatArea conversationId={currentConversationId} />
      ) : (
        <ChatAreaEmpty />
      )}
    </>
  );
}
