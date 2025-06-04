import React from 'react';
import { Box, Paper, Typography, useTheme } from '@mui/material';
import AgentLegendHorizontal from './visualization/AgentLegendHorizontal';
import { useChatContext } from '../../context/ChatContext';

interface AgentLegendPanelProps {
  title?: string;
}

const AgentLegendPanel: React.FC<AgentLegendPanelProps> = ({ 
  title = "Travel Experts" 
}) => {
  const theme = useTheme();
  const { state } = useChatContext();
  
  return (
    <Paper 
      elevation={2}
      sx={{ 
        p: 2, 
        borderRadius: '12px',
        transition: 'all 0.3s ease',
        height: '100%',
        display: 'flex',
        flexDirection: 'column'
      }}
    >
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          mb: 1,
          pb: 2,
          borderBottom: `1px solid ${theme.palette.divider}`,
        }}
      >
        <Typography 
          variant="h5" 
          component="h2" 
          sx={{ 
            fontWeight: 500,
            display: 'flex',
            alignItems: 'center',
            color: theme.palette.primary.main
          }}
        >
          {title}
        </Typography>
        
        <Typography
          variant="body2"
          sx={{
            color: theme.palette.text.secondary,
            fontStyle: 'italic'
          }}
        >
          Specialist agents collaborate to plan your trip
        </Typography>
      </Box>
      
      <Box sx={{ flex: 1 }}>
        <AgentLegendHorizontal activeAgents={state.activeAgents || []} />
      </Box>
    </Paper>
  );
};

export default AgentLegendPanel;