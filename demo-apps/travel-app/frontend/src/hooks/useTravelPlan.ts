import { useState, useEffect, useCallback } from 'react';
import { 
  travelPlanService, 
  TravelPlan, 
  TravelPlanRequest,
  WebSocketMessageType
} from '../services';
import useWebSocket from './useWebSocket';

/**
 * Hook for managing travel plans in React components
 * @param planId Optional plan ID to load and manage
 * @returns Travel plan state and methods
 */
export const useTravelPlan = (planId?: string) => {
  const [plan, setPlan] = useState<TravelPlan | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);
  
  // Use WebSocket for real-time updates
  const { addMessageListener, removeMessageListener } = useWebSocket();

  // Load a travel plan
  const loadTravelPlan = useCallback(async (id: string, forceRefresh = false) => {
    setLoading(true);
    setError(null);
    
    try {
      const loadedPlan = await travelPlanService.getTravelPlan(id, forceRefresh);
      setPlan(loadedPlan);
      return loadedPlan;
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to load travel plan');
      setError(error);
      throw error;
    } finally {
      setLoading(false);
    }
  }, []);

  // Create a new travel plan
  const createTravelPlan = useCallback(async (planData: TravelPlanRequest) => {
    setLoading(true);
    setError(null);
    
    try {
      const newPlan = await travelPlanService.createTravelPlan(planData);
      setPlan(newPlan);
      return newPlan;
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to create travel plan');
      setError(error);
      throw error;
    } finally {
      setLoading(false);
    }
  }, []);

  // Refresh the current plan
  const refreshPlan = useCallback(async () => {
    if (plan) {
      return loadTravelPlan(plan.planId, true);
    }
    return null;
  }, [plan, loadTravelPlan]);

  // Handle WebSocket updates for the plan
  useEffect(() => {
    if (!plan) return;

    const handlePlanUpdate = (message: any) => {
      const { planId: updatedPlanId } = message.payload;
      
      // Only update if this is for our plan
      if (updatedPlanId === plan.planId) {
        refreshPlan().catch(console.error);
      }
    };

    // Add WebSocket listener for plan updates
    addMessageListener(WebSocketMessageType.PLAN_UPDATE, handlePlanUpdate);

    // Remove listener when component unmounts or plan changes
    return () => {
      removeMessageListener(WebSocketMessageType.PLAN_UPDATE, handlePlanUpdate);
    };
  }, [plan, addMessageListener, removeMessageListener, refreshPlan]);

  // Load plan on mount if planId is provided
  useEffect(() => {
    if (planId) {
      loadTravelPlan(planId).catch(console.error);
    }
  }, [planId, loadTravelPlan]);

  // Clean up polling when unmounting
  useEffect(() => {
    return () => {
      if (plan) {
        travelPlanService.stopStatusPolling(plan.planId);
      }
    };
  }, [plan]);

  return {
    plan,
    loading,
    error,
    createTravelPlan,
    loadTravelPlan,
    refreshPlan,
  };
};

export default useTravelPlan; 