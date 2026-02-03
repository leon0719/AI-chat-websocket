export type WSErrorCode =
  | "INVALID_JSON"
  | "UNKNOWN_TYPE"
  | "AUTH_REQUIRED"
  | "AUTH_FAILED"
  | "AUTH_TIMEOUT"
  | "NO_CONVERSATION"
  | "RATE_LIMIT_EXCEEDED"
  | "ALREADY_PROCESSING"
  | "INTERNAL_ERROR"
  | "EMPTY_CONTENT"
  | "MESSAGE_TOO_LONG"
  | "AI_TIMEOUT"
  | "AI_ERROR";

export interface WSAuthMessage {
  type: "auth";
  token: string;
}

export interface WSAuthSuccessMessage {
  type: "auth.success";
  conversation_id: string;
}

export interface WSChatMessage {
  type: "chat.message";
  content: string;
}

export interface WSStreamMessage {
  type: "chat.stream";
  content: string;
  done: boolean;
  message_id?: string;
}

export interface WSErrorMessage {
  type: "chat.error";
  error: string;
  code: WSErrorCode;
}

export interface WSPingMessage {
  type: "ping";
}

export interface WSPongMessage {
  type: "pong";
}

export type WSIncomingMessage =
  | WSAuthSuccessMessage
  | WSStreamMessage
  | WSErrorMessage
  | WSPingMessage;

export type WSOutgoingMessage = WSAuthMessage | WSChatMessage | WSPongMessage;

export type WSConnectionStatus =
  | "disconnected"
  | "connecting"
  | "authenticating"
  | "connected"
  | "error";
