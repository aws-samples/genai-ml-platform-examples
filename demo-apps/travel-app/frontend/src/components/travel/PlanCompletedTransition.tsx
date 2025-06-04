import React, { useEffect, useState } from 'react';
import { Box, Typography, Fade, useTheme, Paper } from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import { WorkflowStage } from '../../context/ChatContext';

interface PlanCompletedTransitionProps {
  currentStage: WorkflowStage;
  previousStage: WorkflowStage;
  onTransitionComplete?: () => void;
}

/**
 * A transition component that shows a success animation when the travel plan is completed
 * This adds a visual enhancement during the transition from planning to results view
 */
const PlanCompletedTransition: React.FC<PlanCompletedTransitionProps> = ({
  currentStage,
  previousStage,
  onTransitionComplete
}) => {
  const theme = useTheme();
  const [showAnimation, setShowAnimation] = useState(false);
  
  // Show animation when transitioning to the completed stage
  useEffect(() => {
    if (currentStage === 'complete' && previousStage !== 'complete') {
      setShowAnimation(true);
      
      // Hide after animation completes
      const timer = setTimeout(() => {
        setShowAnimation(false);
        if (onTransitionComplete) {
          onTransitionComplete();
        }
      }, 2000); // Animation duration
      
      return () => clearTimeout(timer);
    }
  }, [currentStage, previousStage, onTransitionComplete]);
  
  if (!showAnimation) {
    return null;
  }
  
  return (
    <Fade in={showAnimation} timeout={800}>
      <Box
        sx={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          bgcolor: 'rgba(0, 0, 0, 0.3)',
          zIndex: 1000,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backdropFilter: 'blur(4px)'
        }}
      >
        <Paper
          elevation={6}
          sx={{
            py: 4,
            px: 6,
            borderRadius: '16px',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            maxWidth: '90%',
            textAlign: 'center',
            animation: 'pop-in 0.5s ease-out forwards',
            '@keyframes pop-in': {
              '0%': {
                opacity: 0,
                transform: 'scale(0.8)'
              },
              '70%': {
                transform: 'scale(1.05)'
              },
              '100%': {
                opacity: 1,
                transform: 'scale(1)'
              }
            }
          }}
        >
          <CheckCircleIcon 
            sx={{ 
              fontSize: 80, 
              color: theme.palette.success.main,
              mb: 2,
              animation: 'pulse 1.5s infinite'
            }} 
          />
          <Typography variant="h4" gutterBottom sx={{ fontWeight: 'bold', color: theme.palette.primary.main }}>
            Travel Plan Complete!
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Your personalized itinerary has been created. Review your travel plan below.
          </Typography>
        </Paper>
      </Box>
    </Fade>
  );
};

export default PlanCompletedTransition;