import React from 'react';
import { Box, Typography, useTheme, Paper, Tooltip, Divider } from '@mui/material';
import { motion } from 'framer-motion';
import FlightIcon from '@mui/icons-material/Flight';
import HotelIcon from '@mui/icons-material/Hotel';
import RestaurantIcon from '@mui/icons-material/Restaurant';
import DirectionsCarIcon from '@mui/icons-material/DirectionsCar';
import AttractionsIcon from '@mui/icons-material/Attractions';
import PublicIcon from '@mui/icons-material/Public';
import LocalOfferIcon from '@mui/icons-material/LocalOffer';
import EventIcon from '@mui/icons-material/Event';
import { AgentType } from './SpecialistAgent';

export interface AgentLegendHorizontalProps {
  activeAgents: string[];
}

const AgentLegendHorizontal: React.FC<AgentLegendHorizontalProps> = ({ activeAgents }) => {
  const theme = useTheme();

  // Define all agents with their details
  const agentDefinitions: Array<{
    type: AgentType;
    label: string;
    description: string;
    detailedDescription?: string; // Added more comprehensive details
    outputs?: string[]; // What the agent contributes to travel plan
    icon: React.ReactNode;
    color: string;
  }> = [
    {
      type: 'flight',
      label: 'Flight Expert',
      description: 'Finds optimal flight options based on your preferences',
      detailedDescription: 'Searches thousands of flight options to find the best balance of price, convenience, and comfort. Considers layovers, airline preferences, and airport proximity to your destination.',
      outputs: ['Direct and connecting flight options', 'Airline and aircraft details', 'Baggage allowance information', 'Airport terminal guidance'],
      icon: <FlightIcon />,
      color: theme.palette.info.main,
    },
    {
      type: 'hotel',
      label: 'Hotel Expert',
      description: 'Recommends the best accommodations for your stay',
      detailedDescription: 'Analyzes accommodations based on location, amenities, reviews, and value. Considers proximity to attractions and transportation options to maximize your experience.',
      outputs: ['Boutique and luxury hotel options', 'Apartment and vacation rental alternatives', 'Area safety assessments', 'Special amenities and perks'],
      icon: <HotelIcon />,
      color: theme.palette.success.main,
    },
    {
      type: 'attraction',
      label: 'Attraction Expert',
      description: 'Suggests the best places to visit at your destination',
      detailedDescription: 'Curates must-see attractions, hidden gems, and personalized experiences based on your interests. Considers seasonal events, local festivals, and opening hours.',
      outputs: ['Iconic landmarks and cultural sites', 'Off-the-beaten-path experiences', 'Guided tour recommendations', 'Indoor alternatives for bad weather'],
      icon: <AttractionsIcon />,
      color: theme.palette.error.main,
    },
    {
      type: 'dining',
      label: 'Dining Expert',
      description: 'Finds restaurants and local cuisine options',
      detailedDescription: 'Recommends dining experiences from street food to fine dining, focusing on authentic local cuisine, dietary requirements, and reservation assistance. Special focus on hidden local favorites.',
      outputs: ['Award-winning restaurants', 'Local food markets and street food', 'Food tours and cooking classes', 'Reservations for popular venues'],
      icon: <RestaurantIcon />,
      color: theme.palette.warning.main,
    },
    {
      type: 'transportation',
      label: 'Transit Expert',
      description: 'Plans local transportation during your stay',
      detailedDescription: 'Develops a comprehensive transportation strategy including airport transfers, public transit options, car rentals, and walking routes. Considers local traffic patterns and accessibility needs.',
      outputs: ['Airport transfer recommendations', 'Public transportation passes', 'Walking tour routes', 'Car rental vs. rideshare analysis'],
      icon: <DirectionsCarIcon />,
      color: theme.palette.secondary.main,
    },
    {
      type: 'weather',
      label: 'Weather Expert',
      description: 'Checks forecasts for your travel dates',
      detailedDescription: 'Analyzes historical and forecasted weather patterns for your destination during your travel dates. Helps plan activities appropriate for the climate and suggests packing recommendations.',
      outputs: ['Daily weather forecasts', 'Seasonal considerations', 'Packing suggestions', 'Weather-appropriate activity plans'],
      icon: <PublicIcon />,
      color: theme.palette.info.light,
    },
    {
      type: 'pricing',
      label: 'Price Expert',
      description: 'Optimizes your trip to stay within budget',
      detailedDescription: 'Balances quality and cost for all aspects of your trip. Identifies opportunities to save money or splurge strategically, ensuring you get the best value for your budget.',
      outputs: ['Cost breakdowns by category', 'Money-saving recommendations', 'Budget monitoring', 'Value assessments for premium options'],
      icon: <LocalOfferIcon />,
      color: theme.palette.success.light,
    },
    {
      type: 'scheduling',
      label: 'Schedule Expert',
      description: 'Organizes your itinerary for the best experience',
      detailedDescription: 'Creates a day-by-day itinerary that balances activities with downtime, minimizes transit stress, and groups nearby attractions. Accounts for opening hours and optimal visiting times.',
      outputs: ['Daily and hourly itinerary', 'Travel timeline visualization', 'Coordination between all activities', 'Alternate plans for unexpected changes'],
      icon: <EventIcon />,
      color: theme.palette.warning.light,
    },
  ];

  // Check if an agent is active
  const isAgentActive = (agentType: AgentType): boolean => {
    return activeAgents.includes(agentType);
  };

  return (
    <Paper
      elevation={0}
      sx={{
        width: '100%',
        borderRadius: 1,
        border: `1px solid ${theme.palette.divider}`,
        backgroundColor: 'rgba(255, 255, 255, 0.97)',
        my: 2,
        overflow: 'hidden',
      }}
    >
      <Box
        sx={{
          p: 2,
          borderBottom: `1px solid ${theme.palette.divider}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <Typography
          variant="h6"
          sx={{
            fontWeight: 400,
            color: theme.palette.primary.main,
            fontFamily: '"Amazon Ember", sans-serif',
            fontSize: '1rem',
          }}
        >
          Travel Experts
        </Typography>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            backgroundColor: theme.palette.grey[100],
            px: 1.5,
            py: 0.5,
            borderRadius: 1,
            fontSize: '0.8rem',
            color: theme.palette.text.secondary,
            border: `1px solid ${theme.palette.divider}`,
          }}
        >
          {activeAgents.length || 0} Active
        </Box>
      </Box>

      <Box
        sx={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 2,
          p: 2,
          justifyContent: { xs: 'center', sm: 'space-around', md: 'space-between', lg: 'space-between' },
        }}
      >
        {agentDefinitions.map((agent) => (
          <Tooltip
            key={agent.type}
            title={
              <Box sx={{ p: 0.5, maxWidth: 300 }}>
                <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 0.5 }}>
                  {agent.label}
                </Typography>
                <Typography variant="body2" sx={{ mb: 1 }}>
                  {agent.detailedDescription || agent.description}
                </Typography>
                {agent.outputs && (
                  <>
                    <Typography variant="caption" sx={{ fontWeight: 600, display: 'block', mt: 1, mb: 0.5 }}>
                      Provides:
                    </Typography>
                    <Box component="ul" sx={{ m: 0, pl: 2 }}>
                      {agent.outputs.map((output, idx) => (
                        <Typography key={idx} component="li" variant="caption">
                          {output}
                        </Typography>
                      ))}
                    </Box>
                  </>
                )}
              </Box>
            }
            arrow
            placement="top"
          >
            <Box
              component={motion.div}
              initial={{ opacity: 0.9, scale: 0.98 }}
              animate={{ 
                opacity: isAgentActive(agent.type) ? 1 : 0.75,
                scale: isAgentActive(agent.type) ? 1 : 0.98,
                y: isAgentActive(agent.type) ? 0 : 2,
              }}
              whileHover={{ 
                scale: 1.02,
                opacity: 1,
                y: 0
              }}
              transition={{ duration: 0.2 }}
              sx={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 1,
                p: 1.5,
                width: { xs: '100px', sm: '120px', md: '130px' },
                borderRadius: 1,
                border: '1px solid',
                borderColor: isAgentActive(agent.type) ? agent.color : theme.palette.divider,
                backgroundColor: isAgentActive(agent.type) ? `${agent.color}08` : 'transparent',
                boxShadow: isAgentActive(agent.type) ? `0 0 4px ${agent.color}40` : 'none',
                transition: 'all 0.2s ease',
                position: 'relative',
                overflow: 'hidden',
                '&::after': isAgentActive(agent.type) ? {
                  content: '""',
                  position: 'absolute',
                  left: 0,
                  top: 0,
                  height: '3px',
                  width: '100%',
                  backgroundColor: agent.color,
                } : {},
              }}
            >
              <Box
                sx={{
                  color: isAgentActive(agent.type) ? agent.color : theme.palette.text.secondary,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  height: '32px',
                }}
              >
                {agent.icon}
              </Box>
              <Typography
                variant="body2"
                align="center"
                sx={{
                  fontWeight: isAgentActive(agent.type) ? 600 : 400,
                  color: isAgentActive(agent.type) ? agent.color : theme.palette.text.secondary,
                  fontSize: '0.75rem',
                  whiteSpace: 'nowrap',
                  maxWidth: '100%',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {agent.label}
              </Typography>
            </Box>
          </Tooltip>
        ))}
      </Box>
    </Paper>
  );
};

export default AgentLegendHorizontal;