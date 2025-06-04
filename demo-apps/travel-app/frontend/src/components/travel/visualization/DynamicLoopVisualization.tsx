import React, { useRef, useState, useEffect, useCallback } from 'react';
import { Box, Typography, useTheme } from '@mui/material';
import { motion, AnimatePresence } from 'framer-motion';

import { StageType } from './WorkflowStage';
import PlannerBrain from './PlannerBrain';
import SpecialistAgent, { AgentType } from './SpecialistAgent';

interface AgentStatus {
  name: string;
  isActive: boolean;
  statusMessage?: string;
  progress?: number;
  lastActivity?: string;
}

interface DynamicLoopVisualizationProps {
  activeStage: StageType;
  activeAgents?: string[];
  agentStatuses?: Record<string, AgentStatus>;
}

const DynamicLoopVisualization: React.FC<DynamicLoopVisualizationProps> = ({
  activeStage,
  activeAgents = [],
  agentStatuses = {}
}) => {
  console.log('DynamicLoopVisualization render:', {
    activeStage,
    activeAgents,
    agentStatuses
  });
  
  const theme = useTheme();
  const containerRef = useRef<HTMLDivElement>(null);
  const [centerPoint, setCenterPoint] = useState<[number, number]>([0, 0]);
  const [containerSize, setContainerSize] = useState<{ width: number; height: number }>({
    width: 0,
    height: 0
  });
  
  // Animation settings - default to medium speed (no UI control)
  const animationSpeed: 'slow' | 'medium' | 'fast' = 'medium';
  const [isTransitioning, setIsTransitioning] = useState(false);
  const prevStageRef = useRef<StageType>(activeStage);
  
  // Ensure visualization is centered and properly sized
  const [visualizationReady, setVisualizationReady] = useState(false);

  // Reference for the planner brain element
  const brainRef = useRef<HTMLDivElement>(null);
  
  // Update container size and set visualization ready flag on mount and resize
  useEffect(() => {
    const updateDimensions = () => {
      if (containerRef.current) {
        const { width, height } = containerRef.current.getBoundingClientRect();
        console.log('Container dimensions:', { width, height });
        setContainerSize({ width, height });
        
        // Set visualization as ready after initial layout
        if (!visualizationReady && width > 0 && height > 0) {
          console.log('Setting visualization ready to true');
          setTimeout(() => setVisualizationReady(true), 100);
        }
      }
    };

    updateDimensions();
    window.addEventListener('resize', updateDimensions);
    
    return () => {
      window.removeEventListener('resize', updateDimensions);
    };
  }, [visualizationReady]);
  
  // Set the initial center point to the middle of the container
  // This is needed before the brain reference is available
  useEffect(() => {
    if (containerSize.width > 0 && containerSize.height > 0) {
      setCenterPoint([
        containerSize.width / 2,
        containerSize.height / 2
      ]);
    }
  }, [containerSize]);
  
  // When the brain reference is available, update the center point
  useEffect(() => {
    const brainElement = brainRef.current;
    if (brainElement) {
      const updateBrainPosition = () => {
        const containerElement = containerRef.current;
        if (!containerElement || !brainElement) return;
        
        const rect = brainElement.getBoundingClientRect();
        const containerRect = containerElement.getBoundingClientRect();
        
        // Calculate position relative to the container
        const relativeX = rect.left - containerRect.left + rect.width / 2;
        const relativeY = rect.top - containerRect.top + rect.height / 2;
        
        setCenterPoint([relativeX, relativeY]);
        console.log("Updated center point to:", relativeX, relativeY);
      };
      
      // Update immediately and after a short delay to ensure DOM is settled
      updateBrainPosition();
      const timerId = setTimeout(updateBrainPosition, 100);
      
      return () => clearTimeout(timerId);
    }
  }, [containerSize, visualizationReady]);
  
  // Handle stage transitions with animation
  useEffect(() => {
    if (prevStageRef.current !== activeStage) {
      setIsTransitioning(true);
      
      // Set timer to finish transition
      const timer = setTimeout(() => {
        setIsTransitioning(false);
        prevStageRef.current = activeStage;
      }, 1000); // 1 second transition
      
      return () => clearTimeout(timer);
    }
  }, [activeStage]);

  // Define workflow stages
  const workflowStages: { type: StageType; label: string; description: string }[] = [
    { 
      type: 'planning', 
      label: 'Planning', 
      description: 'Analyze the request and determine the best approach'
    },
    { 
      type: 'routing', 
      label: 'Routing', 
      description: 'Identify the specialist agents needed for this request'
    },
    { 
      type: 'executing', 
      label: 'Executing', 
      description: 'Execute the plan using specialist agents to find options'
    },
    { 
      type: 'updating', 
      label: 'Refining', 
      description: 'Review findings and refine the results'
    }
  ];

  // Always display all agents but activate only the relevant ones
  // This creates a fixed layout with inactive agents greyed out
  const getAllAgents = (): AgentType[] => {
    // Always show all possible agents in fixed positions
    return [
      'flight', 
      'hotel', 
      'destination',
      'activity', 
      'budget',
      'orchestrator',
      'dining', 
      'transportation'
    ] as AgentType[];
  };

  // We'll manage temporary active states with timers
  const [temporarilyActiveAgents, setTemporarilyActiveAgents] = useState<Record<string, boolean>>({});
  
  // Track timers so we can clear them if needed
  const agentTimersRef = useRef<Record<string, NodeJS.Timeout>>({});
  
  // When activeAgents changes, update the temporary states with timers
  useEffect(() => {
    if (activeAgents && activeAgents.length > 0) {
      // Create a record of currently active agents
      const newActiveState = { ...temporarilyActiveAgents };
      
      // Mark each active agent
      activeAgents.forEach(agent => {
        newActiveState[agent] = true;
        
        // Clear any existing timer for this agent
        if (agentTimersRef.current[agent]) {
          clearTimeout(agentTimersRef.current[agent]);
        }
        
        // Set a timer to deactivate after 10 seconds
        agentTimersRef.current[agent] = setTimeout(() => {
          setTemporarilyActiveAgents(prev => ({
            ...prev,
            [agent]: false
          }));
        }, 10000);
      });
      
      // Update state
      setTemporarilyActiveAgents(newActiveState);
    }
    
    // Cleanup timers when component unmounts
    return () => {
      Object.values(agentTimersRef.current).forEach(timer => clearTimeout(timer));
    };
  }, [activeAgents]);
  
  // Determine which agents should be active (highlighted) based on real-time updates or logical workflow
  const isAgentActive = (agent: AgentType): boolean => {
    // Check temporary active state first
    if (temporarilyActiveAgents[agent]) {
      return true;
    }
    
    // If we have active agents from real-time updates, use those
    if (activeAgents && activeAgents.length > 0) {
      return activeAgents.includes(agent);
    }
    
    // Fallback to stage-based logic with a more coherent pattern
    switch (activeStage) {
      case 'planning':
        // During planning, weather and scheduling are key
        return agent === 'weather' || agent === 'scheduling';
      case 'routing':
        // During routing, no agents are active yet - they're being selected
        return false;
      case 'executing':
        // During execution, focus on core travel components
        return ['flight', 'hotel', 'attraction'].includes(agent);
      case 'updating':
        // During refinement, focus on optimization agents
        return ['pricing', 'scheduling', 'dining', 'transportation'].includes(agent);
      default:
        return false;
    }
  };
  
  // Get Z-index for agent to ensure proper layering
  const getZIndexForAgent = (agent: AgentType): number => {
    // Assign specific z-index values to prevent random overlapping
    const zIndexMap: Record<AgentType, number> = {
      'flight': 20,
      'hotel': 19,
      'destination': 18,
      'activity': 17,
      'budget': 16,
      'orchestrator': 15,
      'dining': 14,
      'transportation': 13,
      'attraction': 12,
      'weather': 11,
      'pricing': 10,
      'scheduling': 9
    };
    
    return zIndexMap[agent] || 10;
  };

  // Get all agents to display - always show all agents
  const agents = getAllAgents();

  // Calculate agent positions for proper layout around the brain
  const getAgentPosition = (agentType: AgentType): { angle: number, radius: number, cartesian: [number, number] } => {
    const agentCount = 8;
    const radius = 160; // Radius around the brain for proper spacing
    
    // Calculate position based on agent type for consistent positioning
    const agentIndexMap: Record<AgentType, number> = {
      'flight': 0,        // Top (12 o'clock)
      'hotel': 1,         // Top right (1:30)
      'destination': 2,   // Right (3 o'clock)
      'activity': 3,      // Bottom right (4:30)
      'budget': 4,        // Bottom (6 o'clock)
      'orchestrator': 5,  // Bottom left (7:30)
      'dining': 6,        // Left (9 o'clock)
      'transportation': 7, // Top left (10:30)
      'attraction': 8,    // Not displayed but needed for types
      'weather': 9,       // Not displayed but needed for types
      'pricing': 10,      // Not displayed but needed for types
      'scheduling': 11    // Not displayed but needed for types
    };
    const agentIndex = agentIndexMap[agentType] || 0;
    
    // Calculate angle based on position (starts at top, moves clockwise)
    const angle = (Math.PI * 2 * agentIndex) / agentCount - Math.PI / 2;
    
    // Calculate Cartesian coordinates
    const x = radius * Math.cos(angle);
    const y = radius * Math.sin(angle);
    
    return { 
      angle, 
      radius,
      cartesian: [x, y]  
    };
  };

  // Animation variants for container transitions
  const containerVariants = {
    initial: {
      opacity: 0,
    },
    animate: {
      opacity: 1,
      transition: {
        duration: 0.5,
        when: "beforeChildren",
        staggerChildren: 0.1
      }
    },
    exit: {
      opacity: 0,
      transition: {
        duration: 0.3
      }
    }
  };


  // Legend and animation speed controls have been removed

  return (
    <motion.div
      initial="initial"
      animate="animate"
      exit="exit"
      variants={containerVariants}
      style={{ 
        width: '100%', 
        height: '100%', 
        position: 'relative', 
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column'
      }}
    >
      <Box 
        ref={containerRef}
        sx={{ 
          width: '100%', 
          height: '100%', 
          display: 'flex',
          flexDirection: 'column',
          position: 'relative',
          overflow: 'hidden',
          pt: 4,
          pb: 2,
          flex: 1
        }}
      >
        
        {/* Central visualization area */}
        <Box 
          sx={{ 
            flex: 1,
            position: 'relative',
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            minHeight: '350px', // Ensure enough vertical space
            marginTop: '10px', // Add minimal space at the top
            marginBottom: '30px', // Add space before status indicator
            overflow: 'visible', // Allow content to overflow for better visibility
            px: 3 // Add horizontal padding for better spacing
          }}
        >
          {/* Connection lines have been removed */}

          {/* Planner Brain - Set as a reference point for connections */}
          <Box 
            ref={brainRef}
            sx={{ 
              position: 'relative', 
              zIndex: 30,
              // Ensure the brain is correctly positioned at the center
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center'
            }}
          >
            <PlannerBrain isActive={true} activeStage={activeStage} />
          </Box>

          {/* Specialist Agents - positioned absolutely around the brain */}
          <AnimatePresence mode="sync">
            {agents.map((agent, index) => {
              // Get position with pre-calculated cartesian coordinates
              const position = getAgentPosition(agent);
              const [agentX, agentY] = position.cartesian;
              
              return (
                <Box 
                  key={agent} 
                  sx={{ 
                    position: 'absolute',
                    top: '50%',
                    left: '50%',
                    transform: `translate(calc(-50% + ${agentX}px), calc(-50% + ${agentY}px))`,
                    zIndex: getZIndexForAgent(agent),
                    // Add a debug border to verify positioning (remove in production)
                    // border: '1px dashed rgba(0,0,0,0.1)',
                    width: '60px',
                    height: '60px',
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center'
                  }}
                >
                  <SpecialistAgent
                    key={agent}
                    type={agent}
                    isActive={agentStatuses[agent]?.isActive ?? isAgentActive(agent)}
                    position={index}
                    statusMessage={agentStatuses[agent]?.statusMessage}
                    progress={agentStatuses[agent]?.progress}
                    lastActivity={agentStatuses[agent]?.lastActivity}
                  />
                </Box>
              );
            })}
          </AnimatePresence>

          {/* Stage transition flash effect removed */}
        </Box>
        
        </Box>
      </motion.div>
  );
};

export default DynamicLoopVisualization; 