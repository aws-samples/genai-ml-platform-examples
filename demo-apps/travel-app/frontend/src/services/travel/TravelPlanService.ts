import apiClient, {
  // ApiResponse not used, removing to fix warning
  TravelPlanRequest,
  TravelPlanResponse,
  PlanStatusResponse,
} from '../common/apiClient';
import { getSampleTravelPlan, sampleTravelPlans } from './SampleTravelData';
import webSocketService from '../websocket/WebSocketService';
import { config } from '../common/config';

/**
 * Travel plan interface with extended properties
 */
export interface TravelPlan extends TravelPlanResponse {
  details?: {
    destination?: string;
    startDate?: string;
    endDate?: string;
    budget?: number;
    travelers?: number;
    activities?: string[];
    accommodations?: string[];
    transportation?: string[];
    itinerary?: TravelItineraryItem[];
    [key: string]: any;
  };
}

/**
 * Travel itinerary item
 */
export interface TravelItineraryItem {
  day: number;
  date?: string;
  activities: {
    time?: string;
    title: string;
    description?: string;
    location?: string;
    cost?: number;
    duration?: number;
    [key: string]: any;
  }[];
  notes?: string;
}

/**
 * Travel plan service for managing travel plans
 */
class TravelPlanService {
  // Cache for travel plans to minimize API calls
  private travelPlanCache: Map<string, TravelPlan> = new Map();
  // Flag to track if we're currently fetching status for a plan
  private fetchingStatus: Set<string> = new Set();
  // Flag for polling status
  private pollingIntervals: Map<string, number> = new Map();

  /**
   * Create a new travel plan
   * @param planData Travel plan data
   * @param useDemoData Whether to use demo data instead of making an API call
   * @returns Created travel plan
   */
  public async createTravelPlan(
    planData: TravelPlanRequest,
    useDemoData = false
  ): Promise<TravelPlan> {
    
    // If we're in demo mode, use sample data
    if (useDemoData) {
      // Find a sample plan that matches the destination if possible
      const destination = planData.userPreferences.destination?.toLowerCase() || '';
      let samplePlan = sampleTravelPlans.find(plan => 
        plan.destination.name.toLowerCase().includes(destination) ||
        plan.destination.country.toLowerCase().includes(destination)
      );
      
      // If no match by destination, just use the first sample plan
      if (!samplePlan) {
        samplePlan = sampleTravelPlans[0];
      }
      
      // Create a demo plan ID
      const demoPlanId = `sample-${Date.now()}`;
      
      // Create a plan based on sample data
      const plan: TravelPlan = {
        planId: demoPlanId,
        userId: 'demo-user',
        status: samplePlan.status,
        createdAt: Date.now(),
        updatedAt: Date.now(),
        details: {
          destination: planData.userPreferences.destination,
          startDate: planData.userPreferences.startDate,
          endDate: planData.userPreferences.endDate,
          budget: planData.userPreferences.budget,
          travelers: planData.userPreferences.travelers,
          activities: samplePlan.activities?.map(a => a.name) || [],
          accommodations: samplePlan.accommodations?.map(a => a.name) || [],
          transportation: ['Airport Transfer', 'Public Transit', 'Walking'],
          // Create itinerary items
          itinerary: this.adaptSampleItinerary(samplePlan, planData)
        }
      };
      
      this.travelPlanCache.set(plan.planId, plan);
      
      // For demo mode, we'll simulate polling with a timeout
      setTimeout(() => {
        if (this.travelPlanCache.has(plan.planId)) {
          const cachedPlan = this.travelPlanCache.get(plan.planId)!;
          cachedPlan.status = 'CONFIRMED';
          cachedPlan.updatedAt = Date.now();
        }
      }, 5000);
      
      return plan;
    }
    
    // Normal API flow
    try {
      const response = await apiClient.createTravelPlan(planData);
      
      // Initialize plan in cache
      const plan: TravelPlan = {
        ...response.data,
        details: {
          destination: planData.userPreferences.destination,
          startDate: planData.userPreferences.startDate,
          endDate: planData.userPreferences.endDate,
          budget: planData.userPreferences.budget,
          travelers: planData.userPreferences.travelers,
        }
      };
      
      this.travelPlanCache.set(plan.planId, plan);
      
      // In backend-strands mode, set up plan-specific connection
      if (config.useBackendStrands) {
        webSocketService.setPlanId(plan.planId);
        
        // If not already connected, connect now (will use polling if no valid WebSocket URL)
        if (webSocketService.getState() !== 'open') {
          try {
            await webSocketService.connect();
          } catch (error) {
            console.log('WebSocket connection failed, will use polling:', error);
          }
        }
        
        // Start polling for backend-strands mode
        // The WebSocketService will handle polling internally if needed
        this.startStatusPolling(plan.planId);
      } else {
        // Legacy mode: Start polling for status updates
        this.startStatusPolling(plan.planId);
      }
      
      return plan;
    } catch (error) {
      console.error('Error creating travel plan:', error);
      
      // If API fails, create a demo plan instead
      return this.createTravelPlan(planData, true);
    }
  }
  
  /**
   * Adapt sample itinerary data to match user's date preferences
   * @param samplePlan The sample plan to adapt
   * @param planData The user's plan request data
   * @returns Adapted itinerary items
   */
  private adaptSampleItinerary(samplePlan: any, planData: TravelPlanRequest): TravelItineraryItem[] {
    if (!samplePlan.activities || samplePlan.activities.length === 0) {
      return [];
    }
    
    // We only need the start dates to calculate day offsets
    const userStartDate = new Date(planData.userPreferences.startDate || new Date());
    const sampleStartDate = new Date(samplePlan.startDate);
    
    // Group activities by day
    const activitiesByDay: Record<number, any[]> = {};
    
    samplePlan.activities.forEach((activity: any) => {
      const activityDate = new Date(activity.date);
      const sampleDayNumber = Math.floor((activityDate.getTime() - sampleStartDate.getTime()) / (1000 * 60 * 60 * 24)) + 1;
      
      if (!activitiesByDay[sampleDayNumber]) {
        activitiesByDay[sampleDayNumber] = [];
      }
      
      activitiesByDay[sampleDayNumber].push(activity);
    });
    
    // Create itinerary items
    const itinerary: TravelItineraryItem[] = [];
    
    Object.entries(activitiesByDay).forEach(([dayNumberStr, activities]) => {
      const dayNumber = parseInt(dayNumberStr);
      const newDate = new Date(userStartDate);
      newDate.setDate(userStartDate.getDate() + dayNumber - 1);
      const dateStr = newDate.toISOString().split('T')[0];
      
      itinerary.push({
        day: dayNumber,
        date: dateStr,
        activities: activities.map((activity: any) => ({
          time: activity.startTime,
          title: activity.name,
          description: activity.description,
          location: activity.location,
          cost: activity.price?.amount
        }))
      });
    });
    
    // Sort by day number
    return itinerary.sort((a, b) => a.day - b.day);
  }

  /**
   * Get a travel plan by ID
   * @param planId Travel plan ID
   * @param forceRefresh Force a refresh from the API
   * @param useSampleData Whether to use sample data (for demo purposes)
   * @returns Travel plan
   */
  public async getTravelPlan(
    planId: string,
    forceRefresh = false,
    useSampleData = false
  ): Promise<TravelPlan> {
    // Check if we should use sample data (for demos or development)
    const useDemo = useSampleData || planId.startsWith('sample-');
    
    if (useDemo) {
      // Look for a matching sample plan
      const samplePlan = getSampleTravelPlan(planId);
      if (samplePlan) {
        // Convert sample plan to TravelPlan format
        const plan: TravelPlan = {
          planId: samplePlan.planId,
          userId: 'demo-user',
          status: samplePlan.status,
          createdAt: new Date(samplePlan.createdAt).getTime(),
          updatedAt: new Date(samplePlan.updatedAt).getTime(),
          details: {
            destination: samplePlan.destination.name,
            startDate: samplePlan.startDate,
            endDate: samplePlan.endDate,
            budget: samplePlan.budget.total,
            travelers: 2,
            activities: samplePlan.activities?.map(a => a.name) || [],
            accommodations: samplePlan.accommodations?.map(a => a.name) || [],
            transportation: ['Airport Transfer', 'Public Transit', 'Walking'],
            // Create itinerary items from activities
            itinerary: samplePlan.activities?.reduce((acc: TravelItineraryItem[], activity) => {
              // Find existing day or create new one
              let dayItem = acc.find(item => item.date === activity.date);
              if (!dayItem) {
                const activityDate = new Date(activity.date);
                const startDate = new Date(samplePlan.startDate);
                const dayNumber = Math.floor((activityDate.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24)) + 1;
                
                dayItem = {
                  day: dayNumber,
                  date: activity.date,
                  activities: []
                };
                acc.push(dayItem);
              }
              
              // Add activity to day
              dayItem.activities.push({
                time: activity.startTime,
                title: activity.name,
                description: activity.description,
                location: activity.location,
                cost: activity.price?.amount
              });
              
              return acc;
            }, []).sort((a, b) => a.day - b.day) || []
          },
        };
        
        // Cache the plan
        this.travelPlanCache.set(planId, plan);
        return plan;
      }
    }
    
    // Regular flow - return from cache if available and not forcing refresh
    if (!forceRefresh && this.travelPlanCache.has(planId)) {
      return this.travelPlanCache.get(planId)!;
    }

    try {
      // Get the latest status
      const statusResponse = await this.getTravelPlanStatus(planId);
      
      // If we don't have the plan in cache yet, create a skeleton
      if (!this.travelPlanCache.has(planId)) {
        const plan: TravelPlan = {
          planId,
          userId: '', // This will be updated when we get the real data
          status: statusResponse.status,
          createdAt: Date.now(),
          updatedAt: statusResponse.updatedAt,
          details: {},
        };
        
        this.travelPlanCache.set(planId, plan);
      }
      
      // Update the cached plan with the latest status
      const plan = this.travelPlanCache.get(planId)!;
      plan.status = statusResponse.status;
      plan.updatedAt = statusResponse.updatedAt;
      
      // If we have results, update the details
      if (statusResponse.results) {
        plan.details = {
          ...plan.details,
          ...statusResponse.results,
        };
      }
      
      return plan;
    } catch (error) {
      console.error(`Error fetching travel plan ${planId}:`, error);
      
      // If API fails, try to return a sample plan for demo/development purposes
      const samplePlan = sampleTravelPlans[0]; // Use first sample plan as fallback
      
      const fallbackPlan: TravelPlan = {
        planId: planId,
        userId: 'demo-user',
        status: samplePlan.status,
        createdAt: new Date(samplePlan.createdAt).getTime(),
        updatedAt: new Date(samplePlan.updatedAt).getTime(),
        details: {
          destination: samplePlan.destination.name,
          startDate: samplePlan.startDate,
          endDate: samplePlan.endDate,
          budget: samplePlan.budget.total,
          travelers: 2,
          activities: samplePlan.activities?.map(a => a.name) || [],
          accommodations: samplePlan.accommodations?.map(a => a.name) || [],
          transportation: ['Airport Transfer', 'Public Transit', 'Walking'],
        },
      };
      
      // Cache the fallback plan
      this.travelPlanCache.set(planId, fallbackPlan);
      return fallbackPlan;
    }
  }

  /**
   * Get travel plan status
   * @param planId Travel plan ID
   * @returns Plan status
   */
  public async getTravelPlanStatus(planId: string): Promise<PlanStatusResponse> {
    // Prevent duplicate requests
    if (this.fetchingStatus.has(planId)) {
      throw new Error('Status request already in progress');
    }
    
    try {
      this.fetchingStatus.add(planId);
      const response = await apiClient.getTravelPlanStatus(planId);
      
      // Update our cache with the latest data if available
      if (this.travelPlanCache.has(planId)) {
        const plan = this.travelPlanCache.get(planId)!;
        
        // Update the plan with the latest status and results
        plan.status = response.data.status;
        plan.updatedAt = response.data.updatedAt;
        
        // Check if we have markdown content in orchestrator_response
        if (response.data.orchestrator_response) {
          plan.details = {
            ...plan.details,
            // Store the markdown content
            markdown_content: response.data.orchestrator_response,
            // Mark that we have markdown content
            has_markdown: true
          };
        }
        
        // Also handle legacy results format if present
        if (response.data.results) {
          plan.details = {
            ...plan.details,
            ...response.data.results
          };
        }
      }
      
      return response.data;
    } catch (error) {
      console.error(`Error fetching status for plan ${planId}:`, error);
      throw error;
    } finally {
      this.fetchingStatus.delete(planId);
    }
  }

  /**
   * Start polling for status updates
   * @param planId Travel plan ID
   * @param interval Polling interval in milliseconds
   */
  public startStatusPolling(planId: string, interval = 5000): void {
    // In backend-strands mode, we use WebSocket for real-time updates
    if (config.useBackendStrands) {
      console.log(`Skipping polling for plan ${planId} - using WebSocket in backend-strands mode`);
      return;
    }
    
    // Stop any existing polling
    this.stopStatusPolling(planId);
    
    console.log(`Starting status polling for plan ${planId} every ${interval}ms`);
    
    // Start new polling interval
    const intervalId = window.setInterval(async () => {
      try {
        // Skip if we're already fetching
        if (this.fetchingStatus.has(planId)) {
          return;
        }
        
        // Get the latest status
        const statusResponse = await this.getTravelPlanStatus(planId);
        
        // If the plan is in a terminal state, stop polling
        if (
          statusResponse.status === 'completed' ||
          statusResponse.status === 'failed' ||
          statusResponse.status === 'cancelled'
        ) {
          console.log(`Plan ${planId} reached terminal state: ${statusResponse.status}. Stopping polling.`);
          this.stopStatusPolling(planId);
        }
      } catch (error) {
        console.error(`Error polling status for plan ${planId}:`, error);
      }
    }, interval);
    
    this.pollingIntervals.set(planId, intervalId);
  }

  /**
   * Stop polling for status updates
   * @param planId Travel plan ID
   */
  public stopStatusPolling(planId: string): void {
    const intervalId = this.pollingIntervals.get(planId);
    if (intervalId) {
      clearInterval(intervalId);
      this.pollingIntervals.delete(planId);
    }
  }

  /**
   * Clear the travel plan cache
   */
  public clearCache(): void {
    this.travelPlanCache.clear();
  }

  /**
   * Stop all status polling
   */
  public stopAllPolling(): void {
    this.pollingIntervals.forEach((intervalId) => {
      clearInterval(intervalId);
    });
    this.pollingIntervals.clear();
  }
}

// Export as singleton
export const travelPlanService = new TravelPlanService();
export default travelPlanService; 