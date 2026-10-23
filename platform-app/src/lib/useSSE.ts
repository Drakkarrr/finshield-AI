import { useEffect, useRef, useState, useCallback } from 'react';

interface SSEEvent {
  type: string;
  [key: string]: any;
}

interface UseSSEOptions {
  onMessage?: (event: SSEEvent) => void;
  onError?: (error: Event) => void;
  onOpen?: () => void;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
}

export function useSSE(endpoint: string, options: UseSSEOptions = {}) {
  const {
    onMessage,
    onError,
    onOpen,
    reconnectInterval = 5000,
    maxReconnectAttempts = 5,
  } = options;

  const [isOpen, setIsOpen] = useState(false);
  const [lastEvent, setLastEvent] = useState<SSEEvent | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const connect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const eventSource = new EventSource(endpoint);
    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      setIsOpen(true);
      reconnectAttemptsRef.current = 0;
      onOpen?.();
    };

    eventSource.onmessage = (event) => {
      try {
        const data: SSEEvent = JSON.parse(event.data);
        setLastEvent(data);
        onMessage?.(data);
      } catch (error) {
        console.error('Failed to parse SSE message:', error);
      }
    };

    eventSource.onerror = (error) => {
      setIsOpen(false);
      onError?.(error as Event);

      // Attempt reconnection
      if (reconnectAttemptsRef.current < maxReconnectAttempts) {
        reconnectAttemptsRef.current += 1;
        const delay = reconnectInterval * Math.pow(2, reconnectAttemptsRef.current - 1);
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, delay);
      }
    };
  }, [endpoint, onMessage, onError, onOpen, reconnectInterval, maxReconnectAttempts]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setIsOpen(false);
  }, []);

  useEffect(() => {
    connect();
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    isOpen,
    lastEvent,
    reconnect: connect,
    disconnect,
  };
}
