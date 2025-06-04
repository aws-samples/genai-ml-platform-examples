import React, { useEffect, useState } from 'react';
import { WebSocketState } from '../../services';
import useWebSocket from '../../hooks/useWebSocket';
import styled from 'styled-components';

// Styled components for the status indicator
const StatusContainer = styled.div`
  display: flex;
  align-items: center;
  font-size: 0.75rem;
  color: #666;
  padding: 4px 8px;
  border-radius: 4px;
  position: fixed;
  bottom: 8px;
  right: 8px;
  background-color: rgba(255, 255, 255, 0.8);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  transition: all 0.3s ease;
  z-index: 1000;
`;

const StatusDot = styled.span<{ status: WebSocketState }>`
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 6px;
  background-color: ${props => {
    switch(props.status) {
      case WebSocketState.OPEN:
        return '#4CAF50'; // Green for connected
      case WebSocketState.CONNECTING:
        return '#FFC107'; // Yellow for connecting
      case WebSocketState.CLOSING:
      case WebSocketState.CLOSED:
        return '#F44336'; // Red for closed/closing
      default:
        return '#9E9E9E'; // Grey for unknown
    }
  }};
`;

const StatusText = styled.span`
  font-family: 'Roboto', sans-serif;
  font-weight: 500;
`;

/**
 * WebSocketStatus Component
 * 
 * Displays the current WebSocket connection status
 */
const WebSocketStatus: React.FC<{ className?: string }> = ({ className }) => {
  const { connectionState, lastMessage } = useWebSocket();
  const [visible, setVisible] = useState(true);
  const [lastActivity, setLastActivity] = useState<Date | null>(null);

  useEffect(() => {
    // Update last activity when a message is received
    if (lastMessage) {
      setLastActivity(new Date());
      
      // Show status temporarily when a message is received
      setVisible(true);
      const timer = setTimeout(() => {
        // Hide after some time if connected (otherwise keep showing)
        if (connectionState === WebSocketState.OPEN) {
          setVisible(false);
        }
      }, 3000);
      
      return () => clearTimeout(timer);
    }
  }, [lastMessage, connectionState]);

  useEffect(() => {
    // Always show status when not connected
    if (connectionState !== WebSocketState.OPEN) {
      setVisible(true);
    }
  }, [connectionState]);

  // Format the status text
  const getStatusText = (): string => {
    switch(connectionState) {
      case WebSocketState.OPEN:
        return 'Connected';
      case WebSocketState.CONNECTING:
        return 'Connecting...';
      case WebSocketState.CLOSING:
        return 'Closing...';
      case WebSocketState.CLOSED:
        return 'Disconnected';
      default:
        return 'Unknown';
    }
  };

  // Don't render anything if not visible and connected
  if (!visible && connectionState === WebSocketState.OPEN) {
    return null;
  }

  return (
    <StatusContainer className={className}>
      <StatusDot status={connectionState} />
      <StatusText>{getStatusText()}</StatusText>
      {lastActivity && connectionState === WebSocketState.OPEN && (
        <span style={{ marginLeft: '6px', fontSize: '0.7rem' }}>
          Last update: {lastActivity.toLocaleTimeString()}
        </span>
      )}
    </StatusContainer>
  );
};

export default WebSocketStatus; 