import { useState, useEffect, useCallback } from 'react';
import { webSocketService, WebSocketState, WebSocketMessageType, WebSocketMessage } from '../services';

/**
 * Type for WebSocket message handlers
 */
type MessageHandler = (message: WebSocketMessage) => void;

/**
 * Hook for using WebSocket in React components
 * @param userId Optional user ID for the connection
 * @param planId Optional plan ID for backend-strands mode
 * @returns WebSocket connection state and methods
 */
export const useWebSocket = (userId?: string, planId?: string) => {
  const [connectionState, setConnectionState] = useState<WebSocketState>(
    webSocketService.getState()
  );
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const [error, setError] = useState<Error | null>(null);

  // Connect to WebSocket
  const connect = useCallback(async () => {
    try {
      // Set user ID if provided
      if (userId) {
        webSocketService.setUserId(userId);
      }
      
      // Set plan ID if provided (for backend-strands mode)
      if (planId) {
        webSocketService.setPlanId(planId);
      }
      
      await webSocketService.connect();
      setConnectionState(webSocketService.getState());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to connect to WebSocket'));
    }
  }, [userId, planId]);

  // Disconnect from WebSocket
  const disconnect = useCallback(() => {
    webSocketService.disconnect();
    setConnectionState(webSocketService.getState());
  }, []);

  // Send a message through WebSocket
  const sendMessage = useCallback(
    (type: string, payload: any): boolean => {
      return webSocketService.sendMessage(type, payload);
    },
    []
  );

  // Add a message listener
  const addMessageListener = useCallback(
    (type: string | WebSocketMessageType, handler: MessageHandler) => {
      webSocketService.addEventListener(type, handler);
    },
    []
  );

  // Remove a message listener
  const removeMessageListener = useCallback(
    (type: string | WebSocketMessageType, handler: MessageHandler) => {
      return webSocketService.removeEventListener(type, handler);
    },
    []
  );

  // Setup generic message listener to track last message
  useEffect(() => {
    const messageHandler = (message: WebSocketMessage) => {
      setLastMessage(message);
    };

    webSocketService.addEventListener('all', messageHandler);

    return () => {
      webSocketService.removeEventListener('all', messageHandler);
    };
  }, []);

  // Set up connection state change tracking
  useEffect(() => {
    // Check state periodically
    const intervalId = setInterval(() => {
      const currentState = webSocketService.getState();
      if (currentState !== connectionState) {
        setConnectionState(currentState);
      }
    }, 1000);

    return () => {
      clearInterval(intervalId);
    };
  }, [connectionState]);

  // Connect on mount if not already connected
  useEffect(() => {
    // In backend-strands mode, only connect if we have a plan ID
    const shouldAutoConnect = planId || !require('../services/common/config').config.useBackendStrands;
    
    if (shouldAutoConnect && webSocketService.getState() === WebSocketState.CLOSED) {
      connect();
    }

    return () => {
      // Don't disconnect on unmount as other components may be using the connection
      // Instead, we'll use a reference counting mechanism or connection manager for this
    };
  }, [connect, planId]);

  return {
    connectionState,
    lastMessage,
    error,
    isConnected: connectionState === WebSocketState.OPEN,
    isConnecting: connectionState === WebSocketState.CONNECTING,
    connect,
    disconnect,
    sendMessage,
    addMessageListener,
    removeMessageListener,
  };
};

export default useWebSocket; 