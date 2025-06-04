import React from 'react';
import { Box, Paper, Typography, Tooltip, useTheme } from '@mui/material';
import { motion } from 'framer-motion';
import PsychologyIcon from '@mui/icons-material/Psychology';
import { StageType } from './WorkflowStage';

interface PlannerBrainProps {
  isActive: boolean;
  activeStage: StageType;
}

const PlannerBrain: React.FC<PlannerBrainProps> = ({ isActive, activeStage }) => {
  const theme = useTheme();

  // Different descriptions based on the active stage
  const getBrainDescription = (): string => {
    switch (activeStage) {
      case 'planning':
        return 'Planning the optimal approach to fulfill your travel request';
      case 'routing':
        return 'Determining which specialist agents to engage';
      case 'executing':
        return 'Coordinating specialist agents to find the best options';
      case 'updating':
        return 'Refining results based on constraint satisfaction';
      case 'complete':
        return 'Travel planning completed successfully';
      default:
        return 'Central coordinator for the travel planning process';
    }
  };

  // Animation variants for the brain
  const brainVariants = {
    active: {
      scale: 1.05,
      transition: {
        duration: 0.5,
        yoyo: Infinity,
        repeatDelay: 1
      }
    },
    inactive: {
      scale: 1,
      transition: {
        duration: 0.3
      }
    }
  };

  // Animation for the brain icon
  const iconVariants = {
    active: {
      rotate: [0, 5, 0, -5, 0],
      transition: {
        duration: 2.5,
        repeat: Infinity,
        ease: "easeInOut"
      }
    },
    inactive: {
      rotate: 0
    }
  };

  // Glow pulse animation
  const glowVariants = {
    active: {
      opacity: [0.5, 0.8, 0.5],
      scale: [1, 1.1, 1],
      transition: {
        duration: 3,
        repeat: Infinity,
        repeatType: "loop" as const
      }
    }
  };

  return (
    <Tooltip title={getBrainDescription()} arrow placement="top">
      <motion.div
        initial="inactive"
        animate={isActive ? "active" : "inactive"}
        variants={brainVariants}
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 16,
        }}
      >
        <motion.div style={{ position: 'relative' }}>
          <Paper
            elevation={isActive ? 6 : 2}
            component={motion.div}
            sx={{
              width: 70,
              height: 70,
              borderRadius: '50%',
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              background: isActive 
                ? `radial-gradient(circle, ${theme.palette.primary.main} 60%, ${theme.palette.primary.dark} 100%)` 
                : theme.palette.grey[300],
              color: isActive ? 'white' : 'rgba(0, 0, 0, 0.38)',
              border: isActive ? `3px solid ${theme.palette.common.white}` : 'none',
              boxShadow: isActive 
                ? `0 0 20px 3px ${theme.palette.primary.main}` 
                : 'none',
              position: 'relative',
              zIndex: 10
            }}
            whileHover={{ scale: 1.05 }}
          >
            <motion.div
              variants={iconVariants}
              animate={isActive ? "active" : "inactive"}
            >
              <PsychologyIcon sx={{ fontSize: 38 }} />
            </motion.div>
          </Paper>
          
          {/* Animated glow effect */}
          {isActive && (
            <motion.div
              variants={glowVariants}
              animate="active"
              style={{
                position: 'absolute',
                top: -8,
                left: -8,
                width: 'calc(100% + 16px)',
                height: 'calc(100% + 16px)',
                borderRadius: '50%',
                backgroundColor: 'transparent',
                border: `3px solid ${theme.palette.primary.light}`,
                zIndex: 5
              }}
            />
          )}
          
          {/* Additional glow rings when active */}
          {isActive && (
            <>
              <motion.div
                animate={{
                  scale: [1, 1.15, 1],
                  opacity: [0.3, 0.5, 0.3],
                }}
                transition={{
                  duration: 2,
                  repeat: Infinity,
                  repeatType: "loop" as const,
                  delay: 0.5
                }}
                style={{
                  position: 'absolute',
                  top: -10,
                  left: -10,
                  width: 'calc(100% + 20px)',
                  height: 'calc(100% + 20px)',
                  borderRadius: '50%',
                  border: `2px solid ${theme.palette.primary.light}`,
                  zIndex: 4
                }}
              />
              <motion.div
                animate={{
                  scale: [1, 1.2, 1],
                  opacity: [0.2, 0.3, 0.2],
                }}
                transition={{
                  duration: 3,
                  repeat: Infinity,
                  repeatType: "loop" as const,
                  delay: 1
                }}
                style={{
                  position: 'absolute',
                  top: -18,
                  left: -18,
                  width: 'calc(100% + 36px)',
                  height: 'calc(100% + 36px)',
                  borderRadius: '50%',
                  border: `1px solid ${theme.palette.primary.light}`,
                  zIndex: 3
                }}
              />
            </>
          )}
        </motion.div>
        
        <motion.div
          animate={{
            y: isActive ? [0, -3, 0] : 0
          }}
          transition={{
            duration: 1.5,
            repeat: isActive ? Infinity : 0,
            repeatType: "loop" as const
          }}
        >
          <Typography
            variant="subtitle2"
            sx={{
              mt: 1,
              fontWeight: 'bold',
              color: isActive ? theme.palette.primary.dark : theme.palette.text.secondary,
              padding: '3px 10px',
              marginTop: '10px',
              borderRadius: '4px',
              backgroundColor: 'rgba(255, 255, 255, 0.95)',
              border: `1px solid ${theme.palette.primary.main}30`,
              boxShadow: '0 3px 6px rgba(0,0,0,0.15)',
              zIndex: 50,
              position: 'relative',
              whiteSpace: 'nowrap'
            }}
          >
            Planner Brain
          </Typography>
        </motion.div>
      </motion.div>
    </Tooltip>
  );
};

export default PlannerBrain; 