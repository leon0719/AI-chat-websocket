import { LogOut, MessageSquareOff, Plus } from "lucide-react";
import { useShallow } from "zustand/react/shallow";
import { EmptyState, LoadingSpinner } from "@/components/common";
import { Button, ScrollArea, Separator } from "@/components/ui";
import {
  useConversations,
  useCreateConversation,
  useDeleteConversation,
  useLogout,
  useUpdateConversation,
} from "@/hooks";
import { useAuthStore, useChatStore } from "@/stores";
import { ConversationItem } from "./ConversationItem";

export function ConversationList() {
  const { currentConversationId, setCurrentConversationId } = useChatStore(
    useShallow((s) => ({
      currentConversationId: s.currentConversationId,
      setCurrentConversationId: s.setCurrentConversationId,
    })),
  );
  const user = useAuthStore(useShallow((s) => s.user));
  const { data, isLoading, hasNextPage, fetchNextPage, isFetchingNextPage } = useConversations();
  const createConversation = useCreateConversation();
  const deleteConversation = useDeleteConversation();
  const updateConversation = useUpdateConversation();
  const logout = useLogout();

  const conversations = data?.pages.flatMap((page) => page.conversations) ?? [];

  const handleNewConversation = () => {
    createConversation.mutate(undefined, {
      onSuccess: (conversation) => {
        setCurrentConversationId(conversation.id);
      },
    });
  };

  const handleDelete = (id: string) => {
    deleteConversation.mutate(id, {
      onSuccess: () => {
        if (currentConversationId === id) {
          setCurrentConversationId(null);
        }
      },
    });
  };

  const handleArchive = (id: string) => {
    updateConversation.mutate({
      id,
      payload: { is_archived: true },
    });
  };

  const handleRename = (id: string, newTitle: string) => {
    updateConversation.mutate({
      id,
      payload: { title: newTitle },
    });
  };

  return (
    <div className="flex h-full w-64 flex-col border-r bg-muted/30">
      <div className="p-4">
        <Button
          onClick={handleNewConversation}
          className="w-full"
          disabled={createConversation.isPending}
        >
          {createConversation.isPending ? (
            <LoadingSpinner size="sm" className="text-primary-foreground" />
          ) : (
            <>
              <Plus className="mr-2 h-4 w-4" />
              新對話
            </>
          )}
        </Button>
      </div>

      <Separator />

      <ScrollArea className="flex-1 px-2">
        <div className="space-y-1 py-2">
          {isLoading ? (
            <div className="flex justify-center py-4">
              <LoadingSpinner />
            </div>
          ) : conversations.length === 0 ? (
            <EmptyState
              icon={MessageSquareOff}
              title="沒有對話"
              description="點擊上方按鈕開始新對話"
              className="py-8"
            />
          ) : (
            <>
              {conversations.map((conversation) => (
                <ConversationItem
                  key={conversation.id}
                  conversation={conversation}
                  isActive={currentConversationId === conversation.id}
                  onClick={() => setCurrentConversationId(conversation.id)}
                  onDelete={() => handleDelete(conversation.id)}
                  onArchive={() => handleArchive(conversation.id)}
                  onRename={(newTitle) => handleRename(conversation.id, newTitle)}
                />
              ))}
              {hasNextPage && (
                <div className="py-2 text-center">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => fetchNextPage()}
                    disabled={isFetchingNextPage}
                  >
                    {isFetchingNextPage ? <LoadingSpinner size="sm" /> : "載入更多"}
                  </Button>
                </div>
              )}
            </>
          )}
        </div>
      </ScrollArea>

      <Separator />

      <div className="p-4">
        <div className="flex items-center justify-between">
          <div className="truncate">
            <p className="text-sm font-medium truncate">{user?.username}</p>
            <p className="text-xs text-muted-foreground truncate">{user?.email}</p>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => logout.mutate()}
            disabled={logout.isPending}
          >
            {logout.isPending ? <LoadingSpinner size="sm" /> : <LogOut className="h-4 w-4" />}
          </Button>
        </div>
      </div>
    </div>
  );
}
