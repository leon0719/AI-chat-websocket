import { Check, Copy } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui";
import type { Message } from "@/types";
import { MarkdownContent } from "./MarkdownContent";

interface MessageItemProps {
  message: Message;
}

export function MessageItem({ message }: MessageItemProps) {
  const isUser = message.role === "user";
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // ignore
    }
  };

  if (isUser) {
    return (
      <div className="flex justify-end px-4 py-3">
        <div className="max-w-[80%] rounded-2xl bg-primary px-4 py-2 text-primary-foreground">
          <p className="whitespace-pre-wrap">{message.content}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="group px-4 py-3">
      <div className="max-w-none">
        <div className="prose dark:prose-invert max-w-none">
          <MarkdownContent content={message.content} />
        </div>
        <div className="mt-2 flex gap-1 opacity-0 transition-opacity group-hover:opacity-100">
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={handleCopy}>
            {copied ? (
              <Check className="h-3.5 w-3.5 text-green-500" />
            ) : (
              <Copy className="h-3.5 w-3.5" />
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}

interface StreamingMessageProps {
  content: string;
  isStreaming: boolean;
}

export function StreamingMessage({ content, isStreaming }: StreamingMessageProps) {
  return (
    <div className="px-4 py-3">
      <div className="max-w-none">
        <div className="prose dark:prose-invert max-w-none">
          <MarkdownContent content={content} />
          {isStreaming && (
            <span className="ml-1 inline-block h-4 w-2 animate-pulse bg-foreground" />
          )}
        </div>
      </div>
    </div>
  );
}
