import { Sparkles } from "lucide-react";
import { useShallow } from "zustand/react/shallow";
import { useAuthStore } from "@/stores";
import { MessageInput } from "./MessageInput";

interface WelcomeScreenProps {
  onSend: (content: string) => boolean;
  selectedModel?: string;
  onModelChange?: (modelId: string) => void;
}

export function WelcomeScreen({ onSend, selectedModel, onModelChange }: WelcomeScreenProps) {
  const user = useAuthStore(useShallow((s) => s.user));

  return (
    <div className="flex flex-1 flex-col items-center justify-center px-4">
      <div className="w-full max-w-2xl space-y-8">
        <div className="text-center">
          <div className="mb-4 flex justify-center">
            <Sparkles className="h-10 w-10 text-primary" />
          </div>
          <h1 className="text-4xl font-semibold tracking-tight">
            Hey there, {user?.username || "there"}
          </h1>
          <p className="mt-2 text-muted-foreground">有什麼我可以幫助你的嗎？</p>
        </div>
        <MessageInput
          onSend={onSend}
          variant="welcome"
          selectedModel={selectedModel}
          onModelChange={onModelChange}
        />
      </div>
    </div>
  );
}
