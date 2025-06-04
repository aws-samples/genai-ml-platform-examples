import React, { useState, useEffect } from 'react';
import { Box, Typography, Grow, useTheme } from '@mui/material';
import NotificationsActiveIcon from '@mui/icons-material/NotificationsActive';
import { WorkflowUpdate, WorkflowUpdateType } from '../../../models/WorkflowUpdate';

interface UpdateIndicatorProps {
  update: WorkflowUpdate;
  onComplete?: () => void;
  position?: 'top-right' | 'top-left' | 'bottom-right' | 'bottom-left';
  duration?: number; // in milliseconds
}

const UpdateIndicator: React.FC<UpdateIndicatorProps> = ({
  update,
  onComplete,
  position = 'bottom-right',
  duration = 3000
}) => {
  const theme = useTheme();
  const [visible, setVisible] = useState(true);

  // Position styles
  const getPositionStyles = () => {
    switch (position) {
      case 'top-right':
        return { top: 16, right: 16 };
      case 'top-left':
        return { top: 16, left: 16 };
      case 'bottom-right':
        return { bottom: 16, right: 16 };
      case 'bottom-left':
        return { bottom: 16, left: 16 };
      default:
        return { bottom: 16, right: 16 };
    }
  };

  // Get title and message based on update type
  const getUpdateContent = () => {
    switch (update.type) {
      case WorkflowUpdateType.STAGE_CHANGE:
        return {
          title: 'Workflow Stage Changed',
          message: `Now in ${update.payload.currentStage} stage`,
          color: theme.palette.primary.main
        };
      case WorkflowUpdateType.AGENT_ACTIVATED:
        return {
          title: 'Agent Activated',
          message: `${update.payload.agentName} is now working`,
          color: theme.palette.info.main
        };
      case WorkflowUpdateType.AGENT_DEACTIVATED:
        return {
          title: 'Agent Deactivated',
          message: `${update.payload.agentName} has stopped`,
          color: theme.palette.text.secondary
        };
      case WorkflowUpdateType.AGENT_PROCESSING:
        return {
          title: 'Agent Processing',
          message: update.payload.operationDescription,
          color: theme.palette.info.main
        };
      case WorkflowUpdateType.AGENT_COMPLETE:
        return {
          title: 'Agent Complete',
          message: update.payload.summary,
          color: theme.palette.success.main
        };
      case WorkflowUpdateType.AGENT_ERROR:
        return {
          title: 'Agent Error',
          message: update.payload.errorMessage,
          color: theme.palette.error.main
        };
      case WorkflowUpdateType.SYSTEM_ERROR:
        return {
          title: 'System Error',
          message: update.payload.errorMessage,
          color: theme.palette.error.main
        };
      case WorkflowUpdateType.RESULTS_UPDATED:
        return {
          title: 'Results Updated',
          message: 'New travel options available',
          color: theme.palette.success.main
        };
      default:
        return {
          title: 'Update Received',
          message: 'Workflow has been updated',
          color: theme.palette.info.main
        };
    }
  };

  const { title, message, color } = getUpdateContent();

  // Auto-hide after duration
  useEffect(() => {
    const timer = setTimeout(() => {
      setVisible(false);
      if (onComplete) {
        setTimeout(onComplete, 300); // Call onComplete after exit animation
      }
    }, duration);

    return () => clearTimeout(timer);
  }, [duration, onComplete]);

  return (
    <Grow in={visible} timeout={300} mountOnEnter unmountOnExit>
      <Box
        sx={{
          position: 'absolute',
          zIndex: 1000,
          minWidth: 250,
          maxWidth: 350,
          backgroundColor: theme.palette.background.paper,
          borderRadius: 2,
          boxShadow: 3,
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          ...getPositionStyles()
        }}
      >
        <Box
          sx={{
            backgroundColor: `${color}20`,
            borderLeft: `4px solid ${color}`,
            p: 1.5,
            display: 'flex',
            alignItems: 'center'
          }}
        >
          <NotificationsActiveIcon sx={{ color, mr: 1, fontSize: 20 }} />
          <Typography variant="subtitle2" sx={{ color }}>{title}</Typography>
        </Box>
        <Box sx={{ p: 1.5, pt: 1 }}>
          <Typography variant="body2">{message}</Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
            {new Date(update.timestamp).toLocaleTimeString()}
          </Typography>
        </Box>
      </Box>
    </Grow>
  );
};

export default UpdateIndicator; 