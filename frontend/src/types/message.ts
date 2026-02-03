export type MessageRole = "system" | "user" | "assistant";

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  model_used: string;
  created_at: string;
}

export interface PaginatedMessages {
  messages: Message[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}
