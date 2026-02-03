import { useCallback, useEffect, useRef } from "react";
import { useShallow } from "zustand/react/shallow";
import { WS_BASE_URL } from "@/lib/constants";
import { useAuthStore, useChatStore, useWebSocketStore } from "@/stores";
import type {
  WSErrorMessage,
  WSIncomingMessage,
  WSOutgoingMessage,
  WSStreamMessage,
} from "@/types";

interface UseWebSocketOptions {
  conversationId: string | null;
  onStream?: (message: WSStreamMessage) => void;
  onError?: (error: WSErrorMessage) => void;
  onConnected?: () => void;
  onDisconnected?: () => void;
}

export function useWebSocket(options: UseWebSocketOptions) {
  const { conversationId, onStream, onError, onConnected, onDisconnected } = options;
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 3;
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const accessToken = useAuthStore(useShallow((s) => s.accessToken));
  const { setStatus, setError, setConversationId, reset } = useWebSocketStore(
    useShallow((s) => ({
      setStatus: s.setStatus,
      setError: s.setError,
      setConversationId: s.setConversationId,
      reset: s.reset,
    })),
  );
  const { startStreaming, appendStreamContent, finishStreaming, clearStreaming } = useChatStore(
    useShallow((s) => ({
      startStreaming: s.startStreaming,
      appendStreamContent: s.appendStreamContent,
      finishStreaming: s.finishStreaming,
      clearStreaming: s.clearStreaming,
    })),
  );

  const connect = useCallback(() => {
    if (!conversationId || !accessToken) {
      return;
    }

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    setStatus("connecting");
    const wsUrl = `${WS_BASE_URL}/ws/chat/${conversationId}/`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus("authenticating");
      const authMessage: WSOutgoingMessage = {
        type: "auth",
        token: accessToken,
      };
      ws.send(JSON.stringify(authMessage));
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as WSIncomingMessage;

        switch (message.type) {
          case "auth.success":
            setStatus("connected");
            setError(null);
            setConversationId(message.conversation_id);
            reconnectAttempts.current = 0;
            onConnected?.();
            break;

          case "chat.stream":
            if (message.content) {
              appendStreamContent(message.content);
            }
            if (message.done && message.message_id) {
              finishStreaming(message.message_id);
            }
            onStream?.(message);
            break;

          case "chat.error":
            setError({ message: message.error, code: message.code });
            clearStreaming();
            onError?.(message);
            break;

          case "ping":
            ws.send(JSON.stringify({ type: "pong" }));
            break;
        }
      } catch {
        // ignore malformed messages
      }
    };

    ws.onerror = () => {
      setError({ message: "WebSocket connection error", code: "INTERNAL_ERROR" });
    };

    ws.onclose = (event) => {
      wsRef.current = null;
      clearStreaming();

      if (event.code === 4001) {
        setError({ message: "Authentication failed", code: "AUTH_FAILED" });
        reset();
        return;
      }

      if (event.code !== 1000 && reconnectAttempts.current < maxReconnectAttempts) {
        reconnectAttempts.current++;
        const delay = Math.min(1000 * 2 ** reconnectAttempts.current, 10000);
        reconnectTimeoutRef.current = setTimeout(connect, delay);
      } else {
        reset();
        onDisconnected?.();
      }
    };
  }, [
    conversationId,
    accessToken,
    setStatus,
    setError,
    setConversationId,
    reset,
    appendStreamContent,
    finishStreaming,
    clearStreaming,
    onStream,
    onError,
    onConnected,
    onDisconnected,
  ]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close(1000);
      wsRef.current = null;
    }
    reset();
  }, [reset]);

  const sendMessage = useCallback(
    (content: string) => {
      if (wsRef.current?.readyState !== WebSocket.OPEN) {
        return false;
      }

      startStreaming(crypto.randomUUID());
      const message: WSOutgoingMessage = {
        type: "chat.message",
        content,
      };
      wsRef.current.send(JSON.stringify(message));
      return true;
    },
    [startStreaming],
  );

  useEffect(() => {
    connect();
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    connect,
    disconnect,
    sendMessage,
  };
}
