/**
 * Backend Strands API Client
 * 
 * This client provides compatibility with the backend-strands API endpoints
 * while maintaining the existing interface expected by the frontend.
 */

import axios, { AxiosInstance } from 'axios';
import { config } from '../common/config';
import { 
  ApiResponse, 
  TravelPlanRequest, 
  TravelPlanResponse,
  PlanStatusResponse
} from '../common/apiClient';

/**
 * Backend Strands specific request/response interfaces
 */
export interface BackendStrandsStartRequest {
  user_goal: string;
  user_preferences?: Record<string, any>;
  user_id?: string;
}

export interface BackendStrandsStartResponse {
  success: boolean;
  plan_id: string;
  status: string;
  initial_response?: string;
  error?: string;
}

export interface BackendStrandsContinueRequest {
  plan_id: string;
  user_input: string;
}

export interface BackendStrandsContinueResponse {
  success: boolean;
  status: string;
  response?: string;
  error?: string;
}

export interface BackendStrandsStatusResponse {
  plan_id: string;
  status: string;
  current_stage?: string;
  travel_plan?: any;
  orchestrator_response?: string;
  final_response?: string;
  processing_duration?: number;
  error?: string;
  created_at?: string;
  updated_at?: string;
  agents?: string[];
}

/**
 * Backend Strands API Client
 */
export class BackendStrandsApiClient {
  private client: AxiosInstance;
  
  constructor(baseURL: string) {
    this.client = axios.create({
      baseURL,
      timeout: config.requestTimeout,
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }
  
  /**
   * Start planning (equivalent to createTravelPlan)
   */
  public async startPlanning(request: TravelPlanRequest): Promise<ApiResponse<TravelPlanResponse>> {
    try {
      // Transform request to backend-strands format
      const backendRequest: BackendStrandsStartRequest = {
        user_goal: request.userGoal,
        user_preferences: {
          ...request.userPreferences,
          userId: request.userId
        },
        user_id: request.userId
      };
      
      const response = await this.client.post<BackendStrandsStartResponse>(
        '/api/planning/start',
        backendRequest
      );
      
      if (!response.data.success) {
        throw new Error(response.data.error || 'Failed to start planning');
      }
      
      // Transform response to frontend format
      const transformedResponse: TravelPlanResponse = {
        planId: response.data.plan_id,
        userId: request.userId,
        status: response.data.status,
        createdAt: Date.now(),
        updatedAt: Date.now()
      };
      
      return {
        data: transformedResponse,
        status: response.status
      };
    } catch (error: any) {
      throw {
        message: error.message || 'Failed to start planning',
        status: error.response?.status || 500,
        code: 'PLANNING_START_ERROR',
        details: error.response?.data
      };
    }
  }
  
  /**
   * Continue planning with user input
   */
  public async continuePlanning(
    planId: string, 
    userInput: string
  ): Promise<ApiResponse<BackendStrandsContinueResponse>> {
    try {
      const request: BackendStrandsContinueRequest = {
        plan_id: planId,
        user_input: userInput
      };
      
      const response = await this.client.post<BackendStrandsContinueResponse>(
        '/api/planning/continue',
        request
      );
      
      if (!response.data.success) {
        throw new Error(response.data.error || 'Failed to continue planning');
      }
      
      return {
        data: response.data,
        status: response.status
      };
    } catch (error: any) {
      throw {
        message: error.message || 'Failed to continue planning',
        status: error.response?.status || 500,
        code: 'PLANNING_CONTINUE_ERROR',
        details: error.response?.data
      };
    }
  }
  
  /**
   * Get planning status (equivalent to getTravelPlanStatus)
   */
  public async getPlanningStatus(planId: string): Promise<ApiResponse<PlanStatusResponse>> {
    try {
      const response = await this.client.get<BackendStrandsStatusResponse>(
        `/api/planning/${planId}/status`
      );
      
      // Transform response to frontend format
      const transformedResponse: PlanStatusResponse = {
        planId: response.data.plan_id,
        status: response.data.status,
        currentStage: response.data.current_stage,
        progress: this.calculateProgress(response.data.status, response.data.current_stage),
        updatedAt: response.data.updated_at ? new Date(response.data.updated_at).getTime() : Date.now(),
        results: response.data.travel_plan,
        // Use final_response if available, otherwise orchestrator_response
        orchestrator_response: response.data.final_response || response.data.orchestrator_response,
        agents: response.data.agents
      };
      
      return {
        data: transformedResponse,
        status: response.status
      };
    } catch (error: any) {
      throw {
        message: error.message || 'Failed to get planning status',
        status: error.response?.status || 500,
        code: 'PLANNING_STATUS_ERROR',
        details: error.response?.data
      };
    }
  }
  
  /**
   * Finalize planning
   */
  public async finalizePlanning(planId: string): Promise<ApiResponse<any>> {
    try {
      const response = await this.client.post(
        `/api/planning/${planId}/finalize`
      );
      
      return {
        data: response.data,
        status: response.status
      };
    } catch (error: any) {
      throw {
        message: error.message || 'Failed to finalize planning',
        status: error.response?.status || 500,
        code: 'PLANNING_FINALIZE_ERROR',
        details: error.response?.data
      };
    }
  }
  
  /**
   * Calculate progress based on status and stage
   */
  private calculateProgress(status: string, stage?: string): number {
    const statusProgress: Record<string, number> = {
      'pending': 0,
      'planning': 25,
      'in_progress': 50,
      'executing': 75,
      'completed': 100,
      'failed': 0
    };
    
    return statusProgress[status.toLowerCase()] || 0;
  }
}

// Export singleton instance
export const backendStrandsApiClient = new BackendStrandsApiClient(config.apiEndpoint);