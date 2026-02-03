export interface Conversation {
  id: string;
  title: string;
  model: string;
  system_prompt: string;
  temperature: number;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
}

export interface ConversationListItem {
  id: string;
  title: string;
  model: string;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
}

export interface ConversationCreatePayload {
  title?: string;
  model?: string;
  system_prompt?: string;
  temperature?: number;
}

export interface ConversationUpdatePayload {
  title?: string;
  model?: string;
  system_prompt?: string;
  temperature?: number;
  is_archived?: boolean;
}

export interface PaginatedConversations {
  conversations: ConversationListItem[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}
