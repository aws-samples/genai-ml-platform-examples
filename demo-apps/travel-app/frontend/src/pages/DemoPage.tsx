import React, { useState, useEffect } from 'react';
import Container from '@mui/material/Container';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Grid from '@mui/material/Grid';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Paper from '@mui/material/Paper';
import TravelExploreIcon from '@mui/icons-material/TravelExplore';

// Import custom components
import ChatInput from '../components/travel/ChatInput';
import VisualizationArea from '../components/travel/VisualizationArea';
import OutputDisplay from '../components/travel/OutputDisplay';
import PlanCompletedTransition from '../components/travel/PlanCompletedTransition';

// Import context
import {
  ChatProvider,
  useChatContext,
  sendUserMessage,
  setProcessing,
  sendSystemMessage,
  WorkflowStage
} from '../context/ChatContext';

// Import services
import { travelPlanService } from '../services/travel/TravelPlanService';
import { useTravelPlan } from '../hooks/useTravelPlan';
import { useWebSocket } from '../hooks/useWebSocket';
import { WebSocketMessageType } from '../services';



// Inner component to use context
const DemoPageContent: React.FC = () => {
  const { state, dispatch, connectToWorkflowUpdates } = useChatContext();
  const [previousStage, setPreviousStage] = useState<WorkflowStage>('idle');
  const [showTransition, setShowTransition] = useState(false);
  const [currentPlanId, setCurrentPlanId] = useState<string | null>(null);

  // Use travel plan hook to manage the current plan
  const { plan, loadTravelPlan } = useTravelPlan(currentPlanId || undefined);
  const { addMessageListener, removeMessageListener } = useWebSocket();

  // Track workflow stage changes for transitions
  useEffect(() => {
    // Only set previous stage when current stage changes and isn't the initial state
    if (state.workflowStage !== previousStage && state.workflowStage !== 'idle') {
      setPreviousStage(state.workflowStage);

      // Show transition animation when completing the plan
      if (state.workflowStage === 'complete' && previousStage !== 'complete') {
        setShowTransition(true);
      }
    }
  }, [state.workflowStage, previousStage]);

  // Update results when plan has markdown content
  useEffect(() => {
    if (plan && plan.details?.markdown_content) {
      console.log('Plan has markdown content, updating results');
      // Set the results to display the markdown
      dispatch({
        type: 'SET_RESULTS',
        payload: [{
          type: 'markdown',
          content: plan.details.markdown_content
        }]
      });
      // Also set workflow stage to complete if not already
      if (state.workflowStage !== 'complete') {
        dispatch({ type: 'SET_WORKFLOW_STAGE', payload: 'complete' });
      }
    }
  }, [plan, dispatch, state.workflowStage]);

  // Listen for RESULTS_UPDATED messages
  useEffect(() => {
    const handleResultsUpdated = (message: any) => {
      console.log('Received RESULTS_UPDATED message:', message);
      console.log('Payload structure:', JSON.stringify(message.payload, null, 2));
      if (message.payload?.results) {
        console.log('Found results, dispatching SET_RESULTS');
        // Set the markdown content as results
        dispatch({
          type: 'SET_RESULTS',
          payload: [{
            type: 'markdown',
            content: message.payload.results
          }]
        });
        // Also set workflow stage to complete
        console.log('Setting workflow stage to complete');
        dispatch({ type: 'SET_WORKFLOW_STAGE', payload: 'complete' });
      } else {
        console.log('No results found in payload');
      }
    };

    addMessageListener(WebSocketMessageType.RESULTS_UPDATED, handleResultsUpdated);

    return () => {
      removeMessageListener(WebSocketMessageType.RESULTS_UPDATED, handleResultsUpdated);
    };
  }, [addMessageListener, removeMessageListener, dispatch]);



  const handleSubmit = (message: string) => {
    // Add user message to chat
    sendUserMessage(dispatch, message);

    // Set processing state
    setProcessing(dispatch, true);

    // Add initial system response
    sendSystemMessage(
      dispatch,
      "I'm processing your travel request. Let me work with our specialist agents to find the best options for you."
    );


    // Connect to workflow updates
    console.log('DemoPage: Connecting to workflow updates');
    connectToWorkflowUpdates();


    // Create a travel plan using the real API
    // Prepare request data
    const planRequest = {
      userId: 'user123', // This would normally come from authentication
      userGoal: message,
      userPreferences: {
        // Extract basic preferences - in a real app these could be parsed from the message
        // or provided via a form
        budget: 5000,
        startDate: '', // Let the backend determine from the message
        endDate: '', // Let the backend determine from the message
        travelers: 2,
        destination: '', // Let the backend determine this from the message
      }
    };

    // Log the request we're about to send
    console.log('Sending travel plan request:', planRequest);

    // Call the API to create the travel plan
    travelPlanService.createTravelPlan(planRequest)
      .then(plan => {
        console.log('Travel plan created:', plan);
        // Store the plan ID for tracking
        setCurrentPlanId(plan.planId);
        // The rest of the workflow will be handled by WebSocket updates
      })
      .catch(error => {
        console.error('Error creating travel plan:', error);

        // Send error message to user
        sendSystemMessage(
          dispatch,
          `I encountered an error while creating your travel plan: ${error.message}. Please try again or contact support if the issue persists.`
        );

        // Reset processing state
        setProcessing(dispatch, false);
      });
  };

  // Handle transition completion
  const handleTransitionComplete = () => {
    setShowTransition(false);
  };

  // Determine active components based on workflow stage
  // For testing: Always show visualization
  const isVisualizationActive = true;
  // Normal behavior: const isVisualizationActive = state.workflowStage !== 'idle' && state.workflowStage !== 'complete';
  const isOutputActive = state.workflowStage === 'complete';

  return (
    <Container maxWidth="lg">
      <Box sx={{ my: 4 }}>
        <Typography variant="h3" component="h1" gutterBottom>
          Interactive Demo
        </Typography>
        <Typography variant="body1" paragraph>
          Enter your travel preferences below to see the collaborative agent system in action.
          This demo showcases how multiple specialist agents work together under the direction
          of a central Planner Brain.
        </Typography>

        <Card sx={{ mb: 4 }}>
          <CardContent>
            <Typography variant="h5" component="h2" gutterBottom>
              <TravelExploreIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
              Start Planning Your Trip
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Describe your ideal trip including destination preferences, date range, budget,
              and any specific interests (e.g., "I want to plan a beach vacation to Hawaii for
              a family of 4 in August with a budget of $5000")
            </Typography>

            <ChatInput
              onSubmit={handleSubmit}
              isProcessing={state.isProcessing}
            />
          </CardContent>
        </Card>

        {/* Show completion transition */}
        {showTransition && (
          <PlanCompletedTransition
            currentStage={state.workflowStage}
            previousStage={previousStage}
            onTransitionComplete={handleTransitionComplete}
          />
        )}

        {/* Conditional rendering based on workflow stage */}
        {!isOutputActive ? (
          /* Show visualization only during planning - no output panel */
          <>
            <Grid container spacing={3} sx={{ mb: 3 }}>
              <Grid item xs={12}>
                <VisualizationArea isActive={isVisualizationActive} />
              </Grid>
            </Grid>

          </>
        ) : (
          /* Show full-width output when completed */
          <Box
            sx={{
              mb: 3,
            }}
          >
            <Grid container spacing={3}>
              <Grid item xs={12}>
                <OutputDisplay
                  results={state.results}
                  isActive={true}
                />
              </Grid>
            </Grid>
          </Box>
        )}

        {!isOutputActive ? (
          // Show detailed workflow stage when processing
          <Paper sx={{ p: 3, borderRadius: '12px' }}>
            <Typography variant="h5" component="h2" gutterBottom>
              Current Workflow Stage: {state.workflowStage}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {state.isProcessing
                ? "Processing your request... This may take a few moments."
                : "Enter your query to begin planning your trip."}
            </Typography>
          </Paper>
        ) : (
          // No success message shown - removed as requested
          <Box sx={{ height: 20 }} /> // Small spacer instead
        )}
      </Box>
    </Container>
  );
};

// Wrapper component that provides context
const DemoPage: React.FC = () => (
  <ChatProvider>
    <DemoPageContent />
  </ChatProvider>
);

export default DemoPage; 