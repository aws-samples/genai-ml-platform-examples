import React, { useEffect, useState, useCallback } from 'react';
import { WebSocketMessageType } from '../../services';
import useWebSocket from '../../hooks/useWebSocket';
import styled from 'styled-components';

// Types
interface Notification {
  id: string;
  message: string;
  type: 'info' | 'success' | 'warning' | 'error';
  timestamp: number;
  autoClose?: boolean;
}

interface NotificationsProps {
  position?: 'top-right' | 'top-left' | 'bottom-right' | 'bottom-left';
  maxVisible?: number;
  autoCloseDelay?: number;
}

// Styled components
const NotificationsContainer = styled.div<{ position: string }>`
  position: fixed;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  max-width: 350px;
  width: 100%;
  ${props => {
    switch (props.position) {
      case 'top-right':
        return 'top: 20px; right: 20px;';
      case 'top-left':
        return 'top: 20px; left: 20px;';
      case 'bottom-right':
        return 'bottom: 20px; right: 20px;';
      case 'bottom-left':
        return 'bottom: 20px; left: 20px;';
      default:
        return 'top: 20px; right: 20px;';
    }
  }}
`;

const NotificationItem = styled.div<{ type: string; exiting?: boolean }>`
  display: flex;
  padding: 14px;
  margin-bottom: 10px;
  border-radius: 2px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
  animation: ${props => props.exiting ? 'fadeOutDown 0.3s ease-out forwards' : 'fadeInUp 0.3s ease-out'};
  color: #16191F; /* AWS text color */
  border-left: 4px solid;
  border-left-color: ${props => {
    switch (props.type) {
      case 'success':
        return '#2E7D32'; /* AWS success green */
      case 'warning':
        return '#FF9900'; /* AWS orange */
      case 'error':
        return '#D13212'; /* AWS error red */
      default:
        return '#0073BB'; /* AWS blue */
    }
  }};
  background-color: #FFFFFF;

  @keyframes fadeInUp {
    from {
      transform: translateY(20px);
      opacity: 0;
    }
    to {
      transform: translateY(0);
      opacity: 1;
    }
  }
  
  @keyframes fadeOutDown {
    from {
      transform: translateY(0);
      opacity: 1;
    }
    to {
      transform: translateY(20px);
      opacity: 0;
    }
  }
`;

const MessageContent = styled.div`
  flex: 1;
`;

const CloseButton = styled.button`
  background: none;
  border: none;
  color: #16191F;
  font-size: 14px;
  cursor: pointer;
  margin-left: 8px;
  padding: 4px;
  opacity: 0.6;
  font-family: 'Amazon Ember', sans-serif;
  display: flex;
  align-items: center;
  justify-content: center;
  &:hover {
    opacity: 1;
  }
  &:focus {
    outline: none;
  }
`;

/**
 * Notifications Component
 * 
 * Displays system notifications received via WebSockets
 */
const Notifications: React.FC<NotificationsProps> = ({ 
  position = 'bottom-right',
  maxVisible = 1, // Only show one notification at a time
  autoCloseDelay = 5000
}) => {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const { addMessageListener } = useWebSocket();

  // Determine notification type based on payload
  const getNotificationType = (payload: any): 'info' | 'success' | 'warning' | 'error' => {
    // Check if error information is present
    if (payload.error || payload.status === 'error') {
      return 'error';
    }
    
    // Check status or notification type in payload
    const status = payload.status || '';
    const type = payload.notificationType || '';
    
    if (status === 'success' || type === 'WORKFLOW_COMPLETED') {
      return 'success';
    }
    
    if (status === 'warning' || type === 'INTERACTION_NEEDED') {
      return 'warning';
    }
    
    // Default to info
    return 'info';
  };

  // Add a new notification, replacing any existing one
  const addNotification = useCallback((notification: Notification) => {
    // Replace existing notifications instead of stacking them
    setNotifications([notification]);
    
    // Auto-close if specified
    if (notification.autoClose) {
      setTimeout(() => {
        removeNotification(notification.id);
      }, autoCloseDelay);
    }
  }, [autoCloseDelay]);

  // Maintain a reference to notifications that are exiting (being removed)
  const [exitingNotification, setExitingNotification] = useState<string | null>(null);
  
  // Remove a notification by ID with animation
  const removeNotification = useCallback((id: string) => {
    // Set the notification as exiting first for animation
    setExitingNotification(id);
    
    // Then actually remove it after animation completes
    setTimeout(() => {
      setNotifications(prev => prev.filter(notif => notif.id !== id));
      setExitingNotification(null);
    }, 300); // Match this duration with CSS animation
  }, []);

  // Listen for WebSocket notification messages
  useEffect(() => {
    const handleNotification = (message: any) => {
      if (message.type === WebSocketMessageType.SYSTEM_NOTIFICATION) {
        addNotification({
          id: `notif-${Date.now()}-${Math.floor(Math.random() * 1000)}`,
          message: message.payload.message,
          type: getNotificationType(message.payload),
          timestamp: Date.now(),
          autoClose: true
        });
      }
    };

    // Add listener for system notifications
    addMessageListener(WebSocketMessageType.SYSTEM_NOTIFICATION, handleNotification);

    // Cleanup listener on unmount
    return () => {
      // Note: No cleanup needed as the WebSocketService maintains listener references
    };
  }, [addMessageListener, addNotification, getNotificationType]);

  // Show only the most recent notifications up to maxVisible
  const visibleNotifications = notifications.slice(0, maxVisible);

  return (
    <NotificationsContainer position={position}>
      {visibleNotifications.map(notification => (
        <NotificationItem 
          key={notification.id} 
          type={notification.type}
          exiting={exitingNotification === notification.id}
        >
          <MessageContent>
            {notification.message}
          </MessageContent>
          <CloseButton onClick={() => removeNotification(notification.id)}>
            ✕
          </CloseButton>
        </NotificationItem>
      ))}
    </NotificationsContainer>
  );
};

export default Notifications; 