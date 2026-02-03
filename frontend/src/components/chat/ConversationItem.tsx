import { Archive, Check, MessageSquare, Pencil, Trash2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button, Input } from "@/components/ui";
import { cn, formatRelativeTime } from "@/lib/utils";
import type { ConversationListItem } from "@/types";

interface ConversationItemProps {
  conversation: ConversationListItem;
  isActive: boolean;
  onClick: () => void;
  onDelete?: () => void;
  onArchive?: () => void;
  onRename?: (newTitle: string) => void;
}

export function ConversationItem({
  conversation,
  isActive,
  onClick,
  onDelete,
  onArchive,
  onRename,
}: ConversationItemProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState(conversation.title || "");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isEditing) {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [isEditing]);

  const handleStartEdit = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEditTitle(conversation.title || "");
    setIsEditing(true);
  };

  const handleSave = () => {
    const trimmedTitle = editTitle.trim();
    if (trimmedTitle && trimmedTitle !== conversation.title) {
      onRename?.(trimmedTitle);
    }
    setIsEditing(false);
  };

  const handleCancel = () => {
    setEditTitle(conversation.title || "");
    setIsEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.nativeEvent.isComposing) {
      e.preventDefault();
      handleSave();
    } else if (e.key === "Escape") {
      handleCancel();
    }
  };

  if (isEditing) {
    return (
      <div className="flex items-center gap-2 rounded-lg bg-accent px-3 py-2">
        <MessageSquare className="h-4 w-4 shrink-0 text-muted-foreground" />
        <Input
          ref={inputRef}
          value={editTitle}
          onChange={(e) => setEditTitle(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={handleSave}
          className="h-7 flex-1 text-sm"
          placeholder="輸入對話名稱"
        />
        <Button variant="ghost" size="icon" className="h-6 w-6" onClick={handleSave}>
          <Check className="h-3 w-3" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6"
          onMouseDown={(e) => e.preventDefault()}
          onClick={handleCancel}
        >
          <X className="h-3 w-3" />
        </Button>
      </div>
    );
  }

  return (
    <div className="group relative">
      <button
        type="button"
        className={cn(
          "flex w-full cursor-pointer items-center gap-3 rounded-lg px-3 py-2 pr-20 text-left transition-colors",
          isActive ? "bg-accent text-accent-foreground" : "hover:bg-accent/50",
        )}
        onClick={onClick}
      >
        <MessageSquare className="h-4 w-4 shrink-0 text-muted-foreground" />
        <div className="flex-1 truncate">
          <p className="truncate text-sm font-medium">{conversation.title || "新對話"}</p>
          <p className="text-xs text-muted-foreground">
            {formatRelativeTime(conversation.updated_at)}
          </p>
        </div>
      </button>
      <div className="absolute right-2 top-1/2 flex -translate-y-1/2 gap-1 opacity-0 transition-opacity group-hover:opacity-100">
        {onRename && (
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={handleStartEdit}>
            <Pencil className="h-3 w-3" />
          </Button>
        )}
        {onArchive && (
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={onArchive}>
            <Archive className="h-3 w-3" />
          </Button>
        )}
        {onDelete && (
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6 text-destructive hover:text-destructive"
            onClick={onDelete}
          >
            <Trash2 className="h-3 w-3" />
          </Button>
        )}
      </div>
    </div>
  );
}
