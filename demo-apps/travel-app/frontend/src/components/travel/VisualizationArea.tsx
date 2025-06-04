import React from 'react';
import { Box, Paper, Typography, useTheme, Chip, Tooltip, IconButton } from '@mui/material';
import TravelExploreIcon from '@mui/icons-material/TravelExplore';
import SignalWifiStatusbar4BarIcon from '@mui/icons-material/SignalWifiStatusbar4Bar';
import SignalWifiStatusbarConnectedNoInternet4Icon from '@mui/icons-material/SignalWifiStatusbarConnectedNoInternet4';
import SignalWifi0BarIcon from '@mui/icons-material/SignalWifi0Bar';
import RefreshIcon from '@mui/icons-material/Refresh';
import { useChatContext } from '../../context/ChatContext';
import DynamicLoopVisualization from './visualization/DynamicLoopVisualization';
import { ConnectionStatus } from '../../models/WorkflowUpdate';
import './animation.css';

interface VisualizationAreaProps {
  isActive?: boolean;
  children?: React.ReactNode;
}

const VisualizationArea: React.FC<VisualizationAreaProps> = ({ 
  isActive = false,
  children 
}) => {
  const theme = useTheme();
  const { state, connectToWorkflowUpdates } = useChatContext();
  
  console.log('VisualizationArea render:', {
    isActive,
    workflowStage: state.workflowStage,
    activeAgents: state.activeAgents,
    agentStatuses: state.agentStatuses,
    connectionStatus: state.connectionStatus
  });

  // Map connection status to appropriate icon and color
  const getConnectionStatusDisplay = () => {
    switch (state.connectionStatus) {
      case ConnectionStatus.CONNECTED:
        return {
          icon: <SignalWifiStatusbar4BarIcon fontSize="small" />,
          color: theme.palette.success.main,
          label: 'Connected',
          tooltip: 'Real-time updates are active'
        };
      case ConnectionStatus.CONNECTING:
        return {
          icon: <SignalWifi0BarIcon fontSize="small" className="pulse" />,
          color: theme.palette.warning.main,
          label: 'Connecting',
          tooltip: 'Attempting to establish connection...'
        };
      case ConnectionStatus.ERROR:
        return {
          icon: <SignalWifiStatusbarConnectedNoInternet4Icon fontSize="small" />,
          color: theme.palette.error.main,
          label: 'Error',
          tooltip: 'Connection error. Click to retry.'
        };
      case ConnectionStatus.DISCONNECTED:
      default:
        return {
          icon: <SignalWifi0BarIcon fontSize="small" />,
          color: theme.palette.text.disabled,
          label: 'Disconnected',
          tooltip: 'Not receiving real-time updates'
        };
    }
  };

  const connectionStatus = getConnectionStatusDisplay();

  // Handle reconnection
  const handleReconnect = () => {
    connectToWorkflowUpdates();
  };

  return (
    <Paper 
      elevation={3}
      sx={{ 
        p: 3, 
        height: '100%',
        minHeight: '300px',
        display: 'flex',
        flexDirection: 'column',
        borderRadius: '12px',
        border: isActive ? `2px solid ${theme.palette.primary.main}` : 'none',
        transition: 'border 0.3s ease-in-out'
      }}
    >
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h5" component="h2">
          Dynamic Reasoning Loop
        </Typography>
        
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <Tooltip title={connectionStatus.tooltip}>
            <Chip
              icon={connectionStatus.icon}
              label={connectionStatus.label}
              size="small"
              sx={{ 
                backgroundColor: `${connectionStatus.color}20`,
                color: connectionStatus.color,
                mr: 1
              }}
            />
          </Tooltip>
          
          {(state.connectionStatus === ConnectionStatus.DISCONNECTED || 
            state.connectionStatus === ConnectionStatus.ERROR) && (
            <Tooltip title="Reconnect">
              <IconButton 
                size="small" 
                onClick={handleReconnect}
                color="primary"
              >
                <RefreshIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
        </Box>
      </Box>
      
      {isActive ? (
        <Box
          sx={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            overflow: 'hidden',
            minHeight: '450px', // Ensure minimum height
            position: 'relative',
            background: `radial-gradient(circle at center, ${theme.palette.background.default} 0%, ${theme.palette.background.paper} 100%)`
          }}
        >
          <DynamicLoopVisualization 
            activeStage={state.workflowStage} 
            activeAgents={state.activeAgents}
            agentStatuses={state.agentStatuses}
          />
        </Box>
      ) : (
        <Box
          className="transition-all hover-scale"
          sx={{
            flex: 1,
            bgcolor: 'background.paper',
            border: '1px dashed',
            borderColor: 'divider',
            borderRadius: '8px',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            p: 3,
            cursor: 'default'
          }}
        >
          <TravelExploreIcon 
            className="pulse"
            sx={{ fontSize: 60, color: 'text.secondary', opacity: 0.5, mb: 2 }} 
          />
          <Typography 
            variant="body2" 
            color="text.secondary" 
            align="center"
            className="fade-in"
          >
            {isActive 
              ? "Processing your request. Visualization will appear here..."
              : "Enter your travel request to see the agent visualization"}
          </Typography>
        </Box>
      )}
      
      {state.error && (
        <Box 
          sx={{ 
            mt: 2, 
            p: 1, 
            backgroundColor: `${theme.palette.error.main}20`,
            borderRadius: '4px',
            color: theme.palette.error.main
          }}
        >
          <Typography variant="body2">
            {state.error}
          </Typography>
        </Box>
      )}
    </Paper>
  );
};

export default VisualizationArea; 