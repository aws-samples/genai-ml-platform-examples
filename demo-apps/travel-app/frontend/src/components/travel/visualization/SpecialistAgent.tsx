import React, { useState, useEffect, useRef } from 'react';
import { Box, Paper, Typography, Tooltip, useTheme } from '@mui/material';
import { motion } from 'framer-motion';
import FlightIcon from '@mui/icons-material/Flight';
import HotelIcon from '@mui/icons-material/Hotel';
import RestaurantIcon from '@mui/icons-material/Restaurant';
import DirectionsCarIcon from '@mui/icons-material/DirectionsCar';
import AttractionsIcon from '@mui/icons-material/Attractions';
import PublicIcon from '@mui/icons-material/Public';
import LocalOfferIcon from '@mui/icons-material/LocalOffer';
import EventIcon from '@mui/icons-material/Event';
import MapIcon from '@mui/icons-material/Map';
import AccountBalanceWalletIcon from '@mui/icons-material/AccountBalanceWallet';
import HubIcon from '@mui/icons-material/Hub';

export type AgentType = 
  | 'flight' 
  | 'hotel' 
  | 'dining' 
  | 'transportation' 
  | 'attraction' 
  | 'destination'
  | 'activity'
  | 'budget'
  | 'orchestrator'
  | 'weather' 
  | 'pricing' 
  | 'scheduling';

interface SpecialistAgentProps {
  type: AgentType;
  isActive: boolean;
  position?: number;
  statusMessage?: string;
  progress?: number;
  lastActivity?: string;
}

const SpecialistAgent: React.FC<SpecialistAgentProps> = ({
  type,
  isActive,
  position = 0,
  statusMessage,
  progress,
  lastActivity
}) => {
  const theme = useTheme();
  
  // Local state to track temporary activation
  const [tempActive, setTempActive] = useState(isActive);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  
  // Update temporary state whenever the isActive prop changes
  useEffect(() => {
    setTempActive(isActive);
    
    // If becoming active, set timer to deactivate
    if (isActive) {
      // Clear any existing timer
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
      
      // Set new timer to auto-deactivate after 3 seconds
      timerRef.current = setTimeout(() => {
        setTempActive(false);
      }, 3000);
    }
    
    // Cleanup timer on unmount
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, [isActive]);

  // Define agent-specific properties
  const getAgentIcon = () => {
    switch (type) {
      case 'flight':
        return <FlightIcon />;
      case 'hotel':
        return <HotelIcon />;
      case 'dining':
        return <RestaurantIcon />;
      case 'transportation':
        return <DirectionsCarIcon />;
      case 'attraction':
        return <AttractionsIcon />;
      case 'destination':
        return <MapIcon />;
      case 'activity':
        return <EventIcon />;
      case 'budget':
        return <AccountBalanceWalletIcon />;
      case 'orchestrator':
        return <HubIcon />;
      case 'weather':
        return <PublicIcon />;
      case 'pricing':
        return <LocalOfferIcon />;
      case 'scheduling':
        return <EventIcon />;
      default:
        return <PublicIcon />;
    }
  };

  const getAgentColor = () => {
    // Define agent colors - inactive agents will be grey but maintain their shape
    const colors = {
      'flight': theme.palette.info.main,
      'hotel': theme.palette.success.main,
      'dining': theme.palette.warning.main,
      'transportation': theme.palette.secondary.main,
      'attraction': theme.palette.error.main,
      'destination': theme.palette.primary.main,
      'activity': theme.palette.error.light,
      'budget': theme.palette.success.dark,
      'orchestrator': theme.palette.primary.dark,
      'weather': theme.palette.info.light,
      'pricing': theme.palette.success.light,
      'scheduling': theme.palette.warning.light
    };
    
    if (!isActive) {
      // When inactive, use a very light version of the same color
      return theme.palette.grey[300];
    }
    
    return colors[type] || theme.palette.primary.main;
  };

  const getAgentName = () => {
    const names = {
      'flight': 'Flight Specialist',
      'hotel': 'Hotel Specialist', 
      'dining': 'Dining Expert',
      'transportation': 'Transport Advisor',
      'attraction': 'Attraction Curator',
      'destination': 'Destination Expert',
      'activity': 'Activity Curator',
      'budget': 'Budget Analyst',
      'orchestrator': 'Travel Orchestrator',
      'weather': 'Weather Advisor',
      'pricing': 'Pricing Analyst',
      'scheduling': 'Schedule Coordinator'
    };
    return names[type] || `${type.charAt(0).toUpperCase() + type.slice(1)} Agent`;
  };

  const getAgentDescription = () => {
    switch (type) {
      case 'flight':
        return 'Searches thousands of flight options to find the best balance of price, convenience, and comfort. Considers layovers, airline preferences, and airport proximity to your destination.';
      case 'hotel':
        return 'Analyzes accommodations based on location, amenities, reviews, and value. Considers proximity to attractions and transportation options to maximize your experience.';
      case 'dining':
        return 'Recommends dining experiences from street food to fine dining, focusing on authentic local cuisine, dietary requirements, and reservation assistance. Special focus on hidden local favorites.';
      case 'transportation':
        return 'Develops a comprehensive transportation strategy including airport transfers, public transit options, car rentals, and walking routes. Considers local traffic patterns and accessibility needs.';
      case 'attraction':
        return 'Curates must-see attractions, hidden gems, and personalized experiences based on your interests. Considers seasonal events, local festivals, and opening hours.';
      case 'weather':
        return 'Analyzes historical and forecasted weather patterns for your destination during your travel dates. Helps plan activities appropriate for the climate and suggests packing recommendations.';
      case 'pricing':
        return 'Balances quality and cost for all aspects of your trip. Identifies opportunities to save money or splurge strategically, ensuring you get the best value for your budget.';
      case 'destination':
        return 'Provides comprehensive insights about your destination including culture, customs, safety tips, best times to visit, and insider knowledge to enhance your travel experience.';
      case 'activity':
        return 'Curates experiences and creates detailed itineraries based on your interests. Plans activities, manages timing, and ensures optimal use of your travel time.';
      case 'budget':
        return 'Analyzes costs and optimizes your budget allocation across all travel components. Identifies savings opportunities and ensures you get maximum value.';
      case 'orchestrator':
        return 'Coordinates all specialist agents to create a unified travel plan. Synthesizes recommendations from all experts into a coherent, comprehensive travel experience.';
      case 'scheduling':
        return 'Creates a day-by-day itinerary that balances activities with downtime, minimizes transit stress, and groups nearby attractions. Accounts for opening hours and optimal visiting times.';
      default:
        return 'Specialist agent for comprehensive travel planning';
    }
  };

  // Animation variants
  const containerVariants = {
    initial: {
      opacity: 0,
      scale: 0.8,
    },
    animate: {
      opacity: 1, 
      scale: 1,
      transition: {
        duration: 0.5,
        delay: position * 0.1
      }
    },
    exit: {
      opacity: 0,
      scale: 0.8,
      transition: {
        duration: 0.3
      }
    }
  };

  const agentVariants = {
    active: {
      scale: 1.1,
      transition: {
        duration: 0.3
      }
    },
    inactive: {
      scale: 1,
      transition: {
        duration: 0.3
      }
    }
  };

  const iconVariants = {
    active: {
      rotate: type === 'flight' ? [0, 0, 10, 0] : 
              type === 'weather' ? [0, 180, 360] : 
              [0, 10, -10, 0],
      transition: {
        duration: type === 'weather' ? 5 : 2,
        repeat: Infinity,
        repeatType: "loop" as const,
        ease: "easeInOut"
      }
    },
    inactive: {
      rotate: 0
    }
  };

  const pulseVariants = {
    active: {
      opacity: [0.5, 0.8, 0.5],
      scale: [1, 1.1, 1],
      transition: {
        duration: 2,
        repeat: Infinity,
        repeatType: "loop" as const
      }
    }
  };

  // We no longer need label positioning since we're using a legend

  // We no longer need to calculate positions here
  // The parent component (DynamicLoopVisualization) now handles positioning
  // This component just needs to render the agent at the position it's given

  return (
    <Tooltip title={getAgentDescription()} arrow placement="top">
      <motion.div
        initial="initial"
        animate="animate"
        exit="exit"
        variants={containerVariants}
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          position: 'relative',
          zIndex: isActive ? 5 : 1
        }}
      >
        <motion.div
          style={{ position: 'relative' }}
          variants={agentVariants}
          animate={tempActive ? "active" : "inactive"}
          whileHover={{ scale: 1.05 }}
        >
          <Paper
            elevation={tempActive ? 3 : 1}
            component={motion.div}
            sx={{
              width: 44,
              height: 44,
              borderRadius: '50%',
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              background: tempActive 
                ? `radial-gradient(circle, ${getAgentColor()} 50%, ${theme.palette.common.white} 150%)` 
                : theme.palette.grey[200],
              color: tempActive ? 'white' : 'rgba(0, 0, 0, 0.38)',
              border: tempActive ? `2px solid ${theme.palette.common.white}` : '1px solid rgba(0,0,0,0.05)',
              boxShadow: tempActive ? `0 0 12px 2px ${getAgentColor()}` : 'none',
              zIndex: 2
            }}
          >
            <motion.div
              variants={iconVariants}
              animate={tempActive ? "active" : "inactive"}
            >
              {getAgentIcon()}
            </motion.div>
          </Paper>

          {/* Animated glow ring for active agents */}
          {tempActive && (
            <motion.div
              variants={pulseVariants}
              animate="active"
              style={{
                position: 'absolute',
                top: -3,
                left: -3,
                width: 'calc(100% + 6px)',
                height: 'calc(100% + 6px)',
                borderRadius: '50%',
                border: `2px solid ${getAgentColor()}`,
                zIndex: 1
              }}
            />
          )}
        </motion.div>

      </motion.div>
    </Tooltip>
  );
};

export default SpecialistAgent; 