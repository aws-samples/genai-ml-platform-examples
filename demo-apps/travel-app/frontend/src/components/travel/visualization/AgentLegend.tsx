import React from 'react';
import { Box, Typography, useTheme, Paper, Tooltip } from '@mui/material';
import { motion, AnimatePresence } from 'framer-motion';
import FlightIcon from '@mui/icons-material/Flight';
import HotelIcon from '@mui/icons-material/Hotel';
import RestaurantIcon from '@mui/icons-material/Restaurant';
import DirectionsCarIcon from '@mui/icons-material/DirectionsCar';
import AttractionsIcon from '@mui/icons-material/Attractions';
import PublicIcon from '@mui/icons-material/Public';
import LocalOfferIcon from '@mui/icons-material/LocalOffer';
import EventIcon from '@mui/icons-material/Event';
import { AgentType } from './SpecialistAgent';

interface AgentLegendProps {
  activeAgents: string[];
}

const AgentLegend: React.FC<AgentLegendProps> = ({ activeAgents }) => {
  const theme = useTheme();

  // Define all agents with their details
  const agentDefinitions: Array<{
    type: AgentType;
    label: string;
    description: string;
    icon: React.ReactNode;
    color: string;
  }> = [
    {
      type: 'flight',
      label: 'Flight Expert',
      description: 'Finds optimal flight options based on your preferences',
      icon: <FlightIcon fontSize="small" />,
      color: theme.palette.info.main,
    },
    {
      type: 'hotel',
      label: 'Hotel Expert',
      description: 'Recommends the best accommodations for your stay',
      icon: <HotelIcon fontSize="small" />,
      color: theme.palette.success.main,
    },
    {
      type: 'attraction',
      label: 'Attraction Expert',
      description: 'Suggests the best places to visit at your destination',
      icon: <AttractionsIcon fontSize="small" />,
      color: theme.palette.error.main,
    },
    {
      type: 'dining',
      label: 'Dining Expert',
      description: 'Finds restaurants and local cuisine options',
      icon: <RestaurantIcon fontSize="small" />,
      color: theme.palette.warning.main,
    },
    {
      type: 'transportation',
      label: 'Transit Expert',
      description: 'Plans local transportation during your stay',
      icon: <DirectionsCarIcon fontSize="small" />,
      color: theme.palette.secondary.main,
    },
    {
      type: 'weather',
      label: 'Weather Expert',
      description: 'Checks forecasts for your travel dates',
      icon: <PublicIcon fontSize="small" />,
      color: theme.palette.info.light,
    },
    {
      type: 'pricing',
      label: 'Price Expert',
      description: 'Optimizes your trip to stay within budget',
      icon: <LocalOfferIcon fontSize="small" />,
      color: theme.palette.success.light,
    },
    {
      type: 'scheduling',
      label: 'Schedule Expert',
      description: 'Organizes your itinerary for the best experience',
      icon: <EventIcon fontSize="small" />,
      color: theme.palette.warning.light,
    },
  ];

  // Animation variants for legend items
  const itemVariants = {
    initial: {
      opacity: 0,
      y: 5,
    },
    animate: {
      opacity: 1,
      y: 0,
      transition: {
        duration: 0.3,
      },
    },
    exit: {
      opacity: 0,
      y: 5,
      transition: {
        duration: 0.2,
      },
    },
  };

  // Check if an agent is active
  const isAgentActive = (agentType: AgentType): boolean => {
    return activeAgents.includes(agentType);
  };

  return (
    <Paper
      elevation={1}
      sx={{
        padding: { xs: 1.5, md: 1.5 },
        borderRadius: 1,
        border: `1px solid ${theme.palette.divider}`,
        display: 'flex',
        flexDirection: 'column',
        gap: 1,
        backgroundColor: 'rgba(255, 255, 255, 0.97)',
        width: '100%',
        maxWidth: '280px',
        overflow: 'hidden',
        boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)',
      }}
    >
      <Box sx={{ 
        borderBottom: `1px solid ${theme.palette.divider}`,
        pb: 1,
        mb: 1,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between'
      }}>
        <Typography
          variant="subtitle2"
          sx={{
            fontWeight: 500,
            color: theme.palette.primary.main,
            letterSpacing: '0.02em',
            fontFamily: '"Amazon Ember", sans-serif',
            fontSize: '0.9rem'
          }}
        >
          Travel Experts
        </Typography>
        <Box 
          sx={{ 
            display: 'flex', 
            alignItems: 'center',
            backgroundColor: theme.palette.grey[100],
            px: 1,
            py: 0.5,
            borderRadius: 0.5,
            fontSize: '0.7rem',
            color: theme.palette.text.secondary,
            border: `1px solid ${theme.palette.divider}`,
          }}
        >
          {activeAgents.length || 0} Active
        </Box>
      </Box>

      <Box sx={{ 
        display: 'flex',
        flexDirection: 'column',
        gap: 1,
        width: '100%',
        overflow: 'auto',
        maxHeight: { xs: '140px', md: '400px' }
      }}>
        {agentDefinitions.map((agent) => (
          <Tooltip
            key={agent.type}
            title={agent.description}
            placement="right"
            arrow
          >
            <motion.div
              initial="initial"
              animate="animate"
              exit="exit"
              variants={itemVariants}
              style={{ width: '100%' }}
            >
              <Box
                sx={{
                display: 'flex',
                alignItems: 'center',
                borderRadius: 1,
                padding: '8px 12px',
                transition: 'all 0.2s ease',
                border: '1px solid',
                borderColor: isAgentActive(agent.type)
                  ? agent.color
                  : theme.palette.divider,
                backgroundColor: isAgentActive(agent.type)
                  ? `${agent.color}10`
                  : 'transparent',
                color: isAgentActive(agent.type)
                  ? agent.color
                  : theme.palette.text.secondary,
                fontWeight: isAgentActive(agent.type) ? 600 : 400,
                boxShadow: isAgentActive(agent.type)
                  ? `0 0 4px ${agent.color}40`
                  : 'none',
                width: '100%',
                gap: 1.5,
                position: 'relative',
                overflow: 'hidden',
                '&::after': isAgentActive(agent.type) ? {
                  content: '""',
                  position: 'absolute',
                  left: 0,
                  top: 0,
                  bottom: 0,
                  width: '3px',
                  backgroundColor: agent.color,
                } : {},
              }}
            >
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: isAgentActive(agent.type)
                    ? agent.color
                    : theme.palette.text.secondary,
                  mr: 1,
                  minWidth: '24px',
                  '& svg': {
                    fontSize: '1.1rem'
                  }
                }}
              >
                {agent.icon}
              </Box>
              <Typography
                variant="body2"
                sx={{
                  fontWeight: 'inherit',
                  fontSize: '0.8rem',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  ml: 0.5,
                  lineHeight: 1.2
                }}
              >
                {agent.label}
              </Typography>
            </Box>
          </motion.div>
          </Tooltip>
        ))}
      </Box>
    </Paper>
  );
};

export default AgentLegend;