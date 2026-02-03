import { ArrowUp, ChevronDown } from "lucide-react";
import { useCallback, useRef, useState } from "react";
import { useShallow } from "zustand/react/shallow";
import {
  Button,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  Textarea,
} from "@/components/ui";
import { DEFAULT_MODEL, SUPPORTED_MODELS } from "@/lib/constants";
import { cn } from "@/lib/utils";
import { MAX_USER_MESSAGE_LENGTH } from "@/schemas";
import { useChatStore, useWebSocketStore } from "@/stores";
import type { Message } from "@/types";

interface MessageInputProps {
  onSend: (content: string) => boolean;
  variant?: "default" | "welcome";
  selectedModel?: string;
  onModelChange?: (modelId: string) => void;
}

export function MessageInput({
  onSend,
  variant = "default",
  selectedModel: externalModel,
  onModelChange,
}: MessageInputProps) {
  const [content, setContent] = useState("");
  const defaultModel =
    SUPPORTED_MODELS.find((m) => m.value === DEFAULT_MODEL) || SUPPORTED_MODELS[0];
  const [internalModel, setInternalModel] =
    useState<(typeof SUPPORTED_MODELS)[number]>(defaultModel);

  const selectedModel = SUPPORTED_MODELS.find((m) => m.value === externalModel) || internalModel;
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const status = useWebSocketStore(useShallow((s) => s.status));
  const { streamingMessage, setPendingUserMessage } = useChatStore(
    useShallow((s) => ({
      streamingMessage: s.streamingMessage,
      setPendingUserMessage: s.setPendingUserMessage,
    })),
  );

  const isConnected = status === "connected";
  const isStreaming = streamingMessage?.isStreaming ?? false;
  const canSend = isConnected && !isStreaming && content.trim().length > 0;

  const handleSend = useCallback(() => {
    if (!canSend) return;

    const trimmedContent = content.trim();
    if (trimmedContent.length > MAX_USER_MESSAGE_LENGTH) {
      return;
    }

    const pendingMessage: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: trimmedContent,
      prompt_tokens: null,
      completion_tokens: null,
      model_used: selectedModel.value,
      created_at: new Date().toISOString(),
    };

    setPendingUserMessage(pendingMessage);
    const success = onSend(trimmedContent);

    if (success) {
      setContent("");
      textareaRef.current?.focus();
    } else {
      setPendingUserMessage(null);
    }
  }, [canSend, content, onSend, setPendingUserMessage, selectedModel.value]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className={cn("p-4", variant === "default" && "bg-background")}>
      <div
        className={cn(
          "mx-auto flex flex-col gap-2 rounded-2xl border bg-card p-3 shadow-sm",
          variant === "default" && "max-w-3xl",
        )}
      >
        <Textarea
          ref={textareaRef}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            isConnected
              ? variant === "welcome"
                ? "有什麼我可以幫助你的？"
                : "輸入訊息..."
              : "連接中..."
          }
          disabled={!isConnected || isStreaming}
          className="min-h-12 resize-none border-0 bg-transparent p-0 text-base shadow-none focus-visible:ring-0 md:text-base"
          rows={1}
        />
        <div className="flex items-center justify-between">
          <div />
          <div className="flex items-center gap-2">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8 gap-1 text-xs text-muted-foreground"
                >
                  {selectedModel.label}
                  <ChevronDown className="h-3 w-3" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {SUPPORTED_MODELS.map((model) => (
                  <DropdownMenuItem
                    key={model.value}
                    onClick={() => {
                      if (onModelChange) {
                        onModelChange(model.value);
                      } else {
                        setInternalModel(model);
                      }
                    }}
                    className={cn(
                      "cursor-pointer",
                      selectedModel.value === model.value && "bg-accent",
                    )}
                  >
                    {model.label}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
            <Button
              onClick={handleSend}
              disabled={!canSend}
              size="icon"
              className="h-8 w-8 shrink-0 rounded-full bg-orange-500 hover:bg-orange-600 disabled:bg-muted"
            >
              <ArrowUp className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>
      {content.length > MAX_USER_MESSAGE_LENGTH * 0.9 && (
        <p className="mt-2 text-center text-xs text-muted-foreground">
          {content.length} / {MAX_USER_MESSAGE_LENGTH} 字元
        </p>
      )}
    </div>
  );
}
