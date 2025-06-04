import React from 'react';
import { Box, Paper, Typography, Tooltip, useTheme } from '@mui/material';
import { motion } from 'framer-motion';
import AutorenewIcon from '@mui/icons-material/Autorenew';
import DescriptionIcon from '@mui/icons-material/Description';
import RouteIcon from '@mui/icons-material/Route';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import UpdateIcon from '@mui/icons-material/Update';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';

export type StageType = 'planning' | 'routing' | 'executing' | 'updating' | 'complete' | 'idle';

interface WorkflowStageProps {
  type: StageType;
  isActive: boolean;
  index: number;
  label?: string;
  description?: string;
  isTransitioning?: boolean;
}

const WorkflowStage: React.FC<WorkflowStageProps> = ({
  type,
  isActive,
  index,
  label,
  description,
  isTransitioning = false
}) => {
  const theme = useTheme();

  // Define stage-specific properties
  const getStageIcon = () => {
    switch (type) {
      case 'planning':
        return <DescriptionIcon />;
      case 'routing':
        return <RouteIcon />;
      case 'executing':
        return <PlayArrowIcon />;
      case 'updating':
        return <UpdateIcon />;
      case 'complete':
        return <CheckCircleIcon />;
      default:
        return <AutorenewIcon />;
    }
  };

  const getStageColor = () => {
    if (!isActive) return theme.palette.grey[300];
    
    switch (type) {
      case 'planning':
        return theme.palette.primary.main;
      case 'routing':
        return theme.palette.secondary.main;
      case 'executing':
        return theme.palette.success.main;
      case 'updating':
        return theme.palette.warning.main;
      case 'complete':
        return theme.palette.info.main;
      default:
        return theme.palette.grey[500];
    }
  };

  const stageLabel = label || type.charAt(0).toUpperCase() + type.slice(1);
  const stageDescription = description || `The ${stageLabel.toLowerCase()} phase of the workflow`;

  // Animation variants
  const containerVariants = {
    active: { 
      scale: 1.05,
      transition: { duration: 0.3 }
    },
    inactive: { 
      scale: 1,
      transition: { duration: 0.3 } 
    },
    transitioning: {
      scale: [1, 1.05, 1],
      opacity: [1, 0.7, 1],
      transition: { duration: 0.5, repeat: 1 }
    }
  };

  const iconVariants = {
    active: { 
      rotate: [0, 10, 0, -10, 0],
      scale: 1.1,
      transition: { duration: 0.5, repeat: 0 }
    },
    inactive: { 
      rotate: 0,
      scale: 1,
      transition: { duration: 0.3 } 
    },
    transitioning: {
      rotate: [0, 180, 360],
      scale: [1, 0.8, 1],
      transition: { duration: 0.5 }
    }
  };

  const pulseVariants = {
    pulse: {
      scale: [1, 1.05, 1],
      opacity: [0.7, 0.9, 0.7],
      transition: {
        duration: 2,
        repeat: Infinity,
        repeatType: "loop" as const
      }
    }
  };

  return (
    <Tooltip title={stageDescription} arrow placement="top">
      <motion.div
        initial="inactive"
        animate={isTransitioning ? "transitioning" : isActive ? "active" : "inactive"}
        variants={containerVariants}
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          margin: 8
        }}
      >
        <motion.div
          whileHover={{ scale: 1.05 }}
          style={{
            position: 'relative'
          }}
        >
          <Paper
            elevation={isActive ? 4 : 1}
            component={motion.div}
            sx={{
              width: 48,
              height: 48,
              borderRadius: '50%',
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              backgroundColor: getStageColor(),
              color: isActive ? 'white' : 'rgba(0, 0, 0, 0.38)',
              border: isActive ? `2px solid ${theme.palette.common.white}` : '1px solid rgba(0,0,0,0.1)',
              boxShadow: isActive ? `0 0 8px 2px ${getStageColor()}` : 'none',
              position: 'relative',
              zIndex: 1
            }}
          >
            <motion.div
              variants={iconVariants}
              initial="inactive"
              animate={isTransitioning ? "transitioning" : isActive ? "active" : "inactive"}
            >
              {getStageIcon()}
            </motion.div>
            
            {/* Stage index indicator */}
            <Box
              sx={{
                position: 'absolute',
                top: -8,
                right: -8,
                width: 24,
                height: 24,
                borderRadius: '50%',
                backgroundColor: theme.palette.background.paper,
                border: `2px solid ${getStageColor()}`,
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                fontSize: '0.75rem',
                fontWeight: 'bold'
              }}
            >
              {index}
            </Box>
          </Paper>
          
          {/* Animated pulse ring for active stages */}
          {isActive && (
            <motion.div
              variants={pulseVariants}
              animate="pulse"
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                height: '100%',
                borderRadius: '50%',
                border: `2px solid ${getStageColor()}`,
                zIndex: 0
              }}
            />
          )}
        </motion.div>
        <Typography
          variant="caption"
          component={motion.p}
          initial={{ opacity: 0.8 }}
          animate={{ 
            opacity: isActive ? 1 : 0.8,
            fontWeight: isActive ? 700 : 400
          }}
          transition={{ duration: 0.3 }}
          sx={{
            mt: 1,
            color: isActive ? 'text.primary' : 'text.secondary'
          }}
        >
          {stageLabel}
        </Typography>
      </motion.div>
    </Tooltip>
  );
};

export default WorkflowStage; 