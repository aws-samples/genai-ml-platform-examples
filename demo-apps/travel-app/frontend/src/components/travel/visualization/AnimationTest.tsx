import React, { useState } from 'react';
import { Box, Button, Typography, Grid, Paper } from '@mui/material';
import { motion, AnimatePresence } from 'framer-motion';
import WorkflowStage from './WorkflowStage';
import PlannerBrain from './PlannerBrain';
import SpecialistAgent from './SpecialistAgent';
import ConnectionLine from './ConnectionLine';
import '../animation.css';

const AnimationTest: React.FC = () => {
  const [activeStage, setActiveStage] = useState<'planning' | 'routing' | 'executing' | 'updating' | 'complete' | 'idle'>('planning');
  
  // Function to cycle through stages when clicking the button
  const cycleStage = () => {
    const stages: Array<'planning' | 'routing' | 'executing' | 'updating' | 'complete' | 'idle'> = 
      ['planning', 'routing', 'executing', 'updating', 'complete', 'idle'];
    
    const currentIndex = stages.indexOf(activeStage);
    const nextIndex = (currentIndex + 1) % stages.length;
    setActiveStage(stages[nextIndex]);
  };
  
  return (
    <Box sx={{ p: 4 }}>
      <Typography variant="h4" gutterBottom>
        Animation Test Panel
      </Typography>
      
      <Box sx={{ mb: 3 }}>
        <Button 
          variant="contained" 
          onClick={cycleStage}
          sx={{ mr: 2 }}
        >
          Change Stage: {activeStage}
        </Button>
        <Typography variant="caption" color="text.secondary">
          Click to cycle through different workflow stages and test transitions
        </Typography>
      </Box>
      
      <Grid container spacing={3}>
        {/* Test WorkflowStage */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              WorkflowStage Animation
            </Typography>
            <Box sx={{ display: 'flex', justifyContent: 'space-around', mt: 2 }}>
              <WorkflowStage type="planning" isActive={activeStage === 'planning'} index={1} />
              <WorkflowStage type="routing" isActive={activeStage === 'routing'} index={2} />
              <WorkflowStage type="executing" isActive={activeStage === 'executing'} index={3} />
              <WorkflowStage type="updating" isActive={activeStage === 'updating'} index={4} />
            </Box>
          </Paper>
        </Grid>
        
        {/* Test PlannerBrain */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              PlannerBrain Animation
            </Typography>
            <Box sx={{ display: 'flex', justifyContent: 'center', mt: 2 }}>
              <PlannerBrain isActive={activeStage !== 'idle'} activeStage={activeStage} />
            </Box>
          </Paper>
        </Grid>
        
        {/* Test SpecialistAgent */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3, height: '300px', position: 'relative' }}>
            <Typography variant="h6" gutterBottom>
              SpecialistAgent Animation
            </Typography>
            <Box 
              sx={{ 
                display: 'flex', 
                justifyContent: 'center', 
                alignItems: 'center',
                height: '80%',
                position: 'relative'
              }}
            >
              <AnimatePresence>
                {activeStage !== 'idle' && (
                  <motion.div 
                    style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                  >
                    <SpecialistAgent type="flight" isActive={activeStage === 'executing'} position={0} />
                  </motion.div>
                )}
              </AnimatePresence>
            </Box>
          </Paper>
        </Grid>
        
        {/* Test ConnectionLine */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3, height: '300px', position: 'relative' }}>
            <Typography variant="h6" gutterBottom>
              ConnectionLine Animation
            </Typography>
            <Box 
              sx={{ 
                height: '80%',
                position: 'relative'
              }}
            >
              <ConnectionLine 
                from={[50, 150]} 
                to={[300, 150]} 
                isActive={activeStage !== 'idle'} 
                thickness={3}
                animated={true}
                dataSpeed={activeStage === 'executing' ? 'fast' : 'medium'}
              />
            </Box>
          </Paper>
        </Grid>
        
        {/* Test Animation Classes */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              CSS Animation Classes
            </Typography>
            <Box sx={{ display: 'flex', justifyContent: 'space-around', mt: 2 }}>
              <Box>
                <Typography variant="caption">Pulse</Typography>
                <div className="pulse" style={{ width: 50, height: 50, backgroundColor: 'blue', borderRadius: '50%' }}></div>
              </Box>
              <Box>
                <Typography variant="caption">Spin</Typography>
                <div className="spin" style={{ width: 50, height: 50, backgroundColor: 'green', borderRadius: '50%' }}></div>
              </Box>
              <Box>
                <Typography variant="caption">Bounce</Typography>
                <div className="bounce" style={{ width: 50, height: 50, backgroundColor: 'red', borderRadius: '50%' }}></div>
              </Box>
              <Box>
                <Typography variant="caption">Glow</Typography>
                <div className="glow" style={{ width: 50, height: 50, backgroundColor: 'purple', borderRadius: '50%' }}></div>
              </Box>
            </Box>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default AnimationTest; 