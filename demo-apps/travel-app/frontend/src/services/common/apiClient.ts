import axios, { AxiosError, AxiosInstance, AxiosRequestConfig, AxiosResponse, CancelTokenSource } from 'axios';
import { config } from './config';
import { backendStrandsApiClient } from '../api/BackendStrandsApiClient';

// Define API response interface
export interface ApiResponse<T = any> {
  data: T;
  status: number;
  message?: string;
}

// Define error response interface
export interface ApiError {
  message: string;
  status: number;
  code?: string;
  details?: any;
}

// Travel plan interfaces
export interface TravelPlanRequest {
  userId: string;
  userGoal: string;
  userPreferences: {
    budget?: number;
    startDate?: string;
    endDate?: string;
    travelers?: number;
    destination?: string;
    activities?: string[];
    accommodation?: string;
    transportMode?: string;
    [key: string]: any;
  };
}

export interface TravelPlanResponse {
  planId: string;
  userId: string;
  status: string;
  executionArn?: string;
  createdAt: number;
  updatedAt: number;
}

export interface PlanStatusResponse {
  planId: string;
  status: string;
  currentStage?: string;
  progress?: number;
  updatedAt: number;
  results?: any;
  orchestrator_response?: string;
  agents?: string[];
}

// Interaction interfaces
export interface InteractionResponse {
  interactionId: string;
  response: any;
}

// WebSocket message interface
export interface WebSocketMessage {
  type: string;
  payload: any;
  timestamp?: string;
  sessionId?: string;
}

/**
 * API Client Service for Travel Planning Application
 * 
 * Handles all communications with the backend API Gateway endpoints
 * and provides utilities for error handling, cancellation, and retries.
 */
class ApiClient {
  private client: AxiosInstance;
  private baseURL: string;
  private apiKey?: string;
  private authToken?: string;
  private activeRequests: Map<string, CancelTokenSource>;
  private maxRetries: number = config.maxRetries;

  constructor() {
    // API endpoint from configuration
    this.baseURL = config.apiEndpoint;
    
    this.activeRequests = new Map();
    
    // Create Axios instance with default configs
    this.client = axios.create({
      baseURL: this.baseURL,
      timeout: config.requestTimeout,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Setup request interceptor for adding auth headers and logging
    this.setupInterceptors();
  }

  /**
   * Configure request and response interceptors
   */
  private setupInterceptors(): void {
    // Request interceptor
    this.client.interceptors.request.use(
      (config) => {
        // Add auth token if available
        if (this.authToken) {
          config.headers['Authorization'] = `Bearer ${this.authToken}`;
        }

        // Add API key if available
        if (this.apiKey) {
          config.headers['x-api-key'] = this.apiKey;
        }

        // Log request (only in development)
        if (process.env.NODE_ENV === 'development') {
          console.log(`API Request: ${config.method?.toUpperCase()} ${config.url}`, config.data);
        }

        return config;
      },
      (error) => {
        return Promise.reject(this.handleError(error));
      }
    );

    // Response interceptor
    this.client.interceptors.response.use(
      (response) => {
        // Log response (only in development)
        if (process.env.NODE_ENV === 'development') {
          console.log(`API Response: ${response.status}`, response.data);
        }

        return response;
      },
      async (error) => {
        const originalRequest = error.config;

        // Implement retry logic for network errors or 5xx server errors
        if (
          (error.message.includes('Network Error') || 
          (error.response && error.response.status >= 500)) && 
          originalRequest._retry < this.maxRetries
        ) {
          originalRequest._retry = (originalRequest._retry || 0) + 1;
          
          // Exponential backoff delay
          const delay = Math.pow(2, originalRequest._retry) * 1000;
          await new Promise(resolve => setTimeout(resolve, delay));
          
          return this.client(originalRequest);
        }

        return Promise.reject(this.handleError(error));
      }
    );
  }

  /**
   * Set authentication token
   * @param token JWT or similar auth token
   */
  public setAuthToken(token: string): void {
    this.authToken = token;
  }

  /**
   * Set API key for requests
   * @param apiKey API key string
   */
  public setApiKey(apiKey: string): void {
    this.apiKey = apiKey;
  }

  /**
   * Handle API errors and standardize error format
   * @param error Original error object
   * @returns Standardized API error
   */
  private handleError(error: AxiosError): ApiError {
    if (error.response) {
      // Server responded with a non-2xx status
      const serverError = error.response.data as any;
      return {
        message: serverError.message || 'Server error occurred',
        status: error.response.status,
        code: serverError.code || `HTTP-${error.response.status}`,
        details: serverError,
      };
    } else if (error.request) {
      // Request was made but no response received
      return {
        message: 'No response received from server',
        status: 0,
        code: 'NETWORK_ERROR',
        details: error.request,
      };
    } else {
      // Error setting up the request
      return {
        message: error.message || 'Error setting up request',
        status: 0,
        code: 'REQUEST_SETUP_ERROR',
      };
    }
  }

  /**
   * Make a request with cancellation support
   * @param config Request configuration
   * @param requestId Unique identifier for the request
   * @returns Promise with response
   */
  private async request<T>(
    config: AxiosRequestConfig,
    requestId?: string
  ): Promise<ApiResponse<T>> {
    // If a request with this ID is already in progress, cancel it
    if (requestId && this.activeRequests.has(requestId)) {
      this.cancelRequest(requestId);
    }

    // Create a new cancel token
    const source = axios.CancelToken.source();
    if (requestId) {
      this.activeRequests.set(requestId, source);
    }

    try {
      // Include the cancel token in the request
      const response = await this.client({
        ...config,
        cancelToken: source.token,
      });

      return {
        data: response.data,
        status: response.status,
      };
    } catch (error) {
      throw this.handleError(error as AxiosError);
    } finally {
      // Clean up after the request is complete
      if (requestId) {
        this.activeRequests.delete(requestId);
      }
    }
  }

  /**
   * Cancel a specific request by its ID
   * @param requestId Unique identifier for the request
   * @returns true if request was cancelled, false if not found
   */
  public cancelRequest(requestId: string): boolean {
    const source = this.activeRequests.get(requestId);
    if (source) {
      source.cancel(`Request ${requestId} cancelled by user`);
      this.activeRequests.delete(requestId);
      return true;
    }
    return false;
  }

  /**
   * Cancel all active requests
   */
  public cancelAllRequests(): void {
    this.activeRequests.forEach((source, id) => {
      source.cancel(`Request ${id} cancelled by user`);
    });
    this.activeRequests.clear();
  }

  /**
   * Create a new travel plan
   * @param planData Travel plan data
   * @returns Promise with the created travel plan
   */
  public async createTravelPlan(
    planData: TravelPlanRequest
  ): Promise<ApiResponse<TravelPlanResponse>> {
    // Use backend-strands client if enabled
    if (config.useBackendStrands) {
      return backendStrandsApiClient.startPlanning(planData);
    }
    
    // Use legacy endpoint
    return this.request<TravelPlanResponse>(
      {
        method: 'POST',
        url: '/plan',
        data: planData,
      },
      'create-travel-plan'
    );
  }

  /**
   * Get travel plan status
   * @param planId Travel plan ID
   * @returns Promise with the travel plan status
   */
  public async getTravelPlanStatus(
    planId: string
  ): Promise<ApiResponse<PlanStatusResponse>> {
    // Use backend-strands client if enabled
    if (config.useBackendStrands) {
      return backendStrandsApiClient.getPlanningStatus(planId);
    }
    
    // Use legacy endpoint
    return this.request<PlanStatusResponse>(
      {
        method: 'GET',
        url: `/plan/${encodeURIComponent(planId)}`,
      },
      `get-plan-status-${planId}`
    );
  }

  /**
   * Submit a response to an interaction
   * @param interactionId Interaction ID
   * @param response User's response
   * @returns Promise with the interaction response
   */
  public async submitInteractionResponse(
    interactionId: string,
    response: any
  ): Promise<ApiResponse<InteractionResponse>> {
    // In backend-strands mode, interactions are handled differently
    if (config.useBackendStrands) {
      // Extract plan ID from interaction ID (assuming format: planId_interactionId)
      const [planId] = interactionId.split('_');
      const result = await backendStrandsApiClient.continuePlanning(planId, response);
      
      // Transform to expected format
      return {
        data: {
          interactionId,
          response: result.data
        },
        status: result.status
      };
    }
    
    // Use legacy endpoint
    return this.request<InteractionResponse>(
      {
        method: 'POST',
        url: `/interaction/${encodeURIComponent(interactionId)}`,
        data: { response },
      },
      `submit-interaction-${interactionId}`
    );
  }
  
  /**
   * Continue planning with user input (backend-strands specific)
   * @param planId Plan ID
   * @param userInput User's input
   * @returns Promise with the response
   */
  public async continuePlanning(
    planId: string,
    userInput: string
  ): Promise<ApiResponse<any>> {
    if (!config.useBackendStrands) {
      throw new Error('continuePlanning is only available in backend-strands mode');
    }
    
    return backendStrandsApiClient.continuePlanning(planId, userInput);
  }

  /**
   * Health check endpoint
   * @returns Promise with the health check response
   */
  public async healthCheck(): Promise<ApiResponse<{ status: string }>> {
    return this.request<{ status: string }>(
      {
        method: 'GET',
        url: `/health`,
      },
      'health-check'
    );
  }
}

// Export singleton instance
const apiClient = new ApiClient();
export default apiClient; 