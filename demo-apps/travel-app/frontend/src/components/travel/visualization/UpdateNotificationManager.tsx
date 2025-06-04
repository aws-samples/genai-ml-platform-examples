import React, { useEffect, useState } from 'react';
import { Box } from '@mui/material';
import workflowUpdateService from '../../../services/websocket/WorkflowUpdateService';
import UpdateIndicator from './UpdateIndicator';
import { WorkflowUpdate, WorkflowUpdateType, ConnectionStatus } from '../../../models/WorkflowUpdate';

/**
 * Component that manages update notifications from the WebSocket service
 */
const UpdateNotificationManager: React.FC = () => {
  const [notifications, setNotifications] = useState<(WorkflowUpdate & { id: string })[]>([]);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>(ConnectionStatus.DISCONNECTED);
  
  // Subscribe to workflow updates
  useEffect(() => {
    // Subscribe to workflow updates
    const unsubscribeFromUpdates = workflowUpdateService.subscribeToUpdates((update) => {
      // Skip connection status updates as they're shown in the header
      if (update.type === WorkflowUpdateType.CONNECTION_STATUS) {
        return;
      }
      
      // Add the update to the notifications list with a unique ID
      setNotifications((prevNotifications) => [
        ...prevNotifications,
        { ...update, id: `notification-${Date.now()}-${Math.random()}` }
      ]);
    });
    
    // Subscribe to connection status updates
    const unsubscribeFromConnectionStatus = workflowUpdateService.subscribeToConnectionStatus((status) => {
      setConnectionStatus(status);
    });
    
    return () => {
      unsubscribeFromUpdates();
      unsubscribeFromConnectionStatus();
    };
  }, []);
  
  // Remove a notification by ID
  const removeNotification = (id: string) => {
    setNotifications((prevNotifications) => 
      prevNotifications.filter((notification) => notification.id !== id)
    );
  };
  
  return (
    <Box sx={{ position: 'fixed', bottom: 16, right: 16, zIndex: 1000 }}>
      {notifications.map((notification, index) => (
        <Box key={notification.id} sx={{ mb: index === notifications.length - 1 ? 0 : 2 }}>
          <UpdateIndicator
            update={notification}
            position="bottom-right"
            duration={5000}
            onComplete={() => removeNotification(notification.id)}
          />
        </Box>
      ))}
    </Box>
  );
};

export default UpdateNotificationManager; 