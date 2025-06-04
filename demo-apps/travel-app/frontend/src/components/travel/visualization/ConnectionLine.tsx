import React from 'react';
import { Box, useTheme } from '@mui/material';
import { motion } from 'framer-motion';

interface ConnectionLineProps {
  from: [number, number]; // [x, y] coordinates for start point
  to: [number, number]; // [x, y] coordinates for end point
  isActive: boolean;
  thickness?: number;
  color?: string;
  animated?: boolean;
  bidirectional?: boolean;
  dataSpeed?: 'slow' | 'medium' | 'fast';
  zIndex?: number; // Control layering of connection lines
}

const ConnectionLine: React.FC<ConnectionLineProps> = ({
  from,
  to,
  isActive,
  thickness = 2,
  color,
  animated = true,
  bidirectional = false,
  dataSpeed = 'medium',
  zIndex = 1
}) => {
  const theme = useTheme();

  // Determine the line color
  const lineColor = color || (isActive ? theme.palette.primary.main : theme.palette.grey[300]);
  
  // Get animation duration based on speed setting
  const getAnimationDuration = () => {
    switch(dataSpeed) {
      case 'slow': return 5;
      case 'fast': return 2;
      default: return 3; // Medium speed
    }
  };

  // Create path string for SVG line
  const pathString = `M${from[0]},${from[1]} L${to[0]},${to[1]}`;
  
  // Variants for the main line
  const lineVariants = {
    inactive: {
      opacity: 0.3,
      transition: { duration: 0.3 }
    },
    active: {
      opacity: 1,
      transition: { duration: 0.3 }
    }
  };
  
  // Variants for the animated dot moving along the path
  const dotVariants = {
    inactive: { 
      offsetDistance: '0%',
      opacity: 0 
    },
    active: { 
      offsetDistance: ['0%', '100%'],
      opacity: 1,
      transition: { 
        offsetDistance: { 
          duration: getAnimationDuration(), 
          repeat: Infinity,
          ease: "linear"
        },
        opacity: { duration: 0.3 }
      } 
    }
  };

  return (
    <Box
      sx={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        zIndex: 20, // Increased z-index to ensure visibility
        pointerEvents: 'none'
      }}
    >
      <svg 
        width="100%" 
        height="100%" 
        style={{ 
          position: 'absolute', 
          top: 0, 
          left: 0,
          zIndex,
          overflow: 'visible' // Important to allow lines to extend beyond container
        }}
      >
        {/* Base line */}
        <motion.path
          d={pathString}
          stroke={lineColor}
          strokeWidth={thickness * 2}
          fill="none"
          initial="inactive"
          animate={isActive ? "active" : "inactive"}
          variants={lineVariants}
          strokeLinecap="round"
        />
        
        {/* Glow effect for the line */}
        {isActive && (
          <motion.path
            d={pathString}
            stroke={lineColor}
            strokeWidth={thickness * 3}
            strokeOpacity={0.5}
            fill="none"
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.5 }}
            filter={`drop-shadow(0 0 4px ${lineColor})`}
            strokeLinecap="round"
          />
        )}
      </svg>
      
      {/* Animated dot that moves along the path */}
      {animated && isActive && (
        <motion.div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            offsetPath: `path('${pathString}')`,
            zIndex: zIndex + 1
          }}
          initial="inactive"
          animate="active"
          variants={dotVariants}
        >
          <Box
            sx={{
              width: thickness * 8,
              height: thickness * 8,
              borderRadius: '50%',
              background: `radial-gradient(circle, ${lineColor} 40%, rgba(255,255,255,0) 70%)`,
              transform: 'translate(-50%, -50%)',
              filter: `blur(${thickness * 0.2}px) brightness(1.8)`,
              boxShadow: `0 0 ${thickness * 4}px ${lineColor}`
            }}
          />
        </motion.div>
      )}
    </Box>
  );
};

export default ConnectionLine; 