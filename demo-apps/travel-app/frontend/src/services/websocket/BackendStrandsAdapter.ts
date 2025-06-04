/**
 * Backend Strands WebSocket Adapter
 * 
 * This adapter provides compatibility between the backend-strands WebSocket API
 * and the existing frontend WebSocket expectations.
 */

import { WebSocketMessage } from '../common/apiClient';
import { dataTransformationService, StandardizedResult } from '../data/DataTransformationService';

/**
 * Backend Strands event types
 */
export enum BackendStrandsEventType {
  CONNECTION_ESTABLISHED = 'connection_established',
  CONNECTION_CLOSED = 'connection_closed',
  PLANNING_STARTED = 'planning_started',
  PLANNING_UPDATE = 'planning_update',
  PLANNING_COMPLETED = 'planning_completed',
  PLANNING_ERROR = 'planning_error',
  AGENT_THINKING = 'agent_thinking',
  AGENT_RESPONSE = 'agent_response',
  TOOL_CALL = 'tool_call',
  TOOL_RESULT = 'tool_result',
  FLIGHT_SEARCH_STARTED = 'flight_search_started',
  FLIGHT_SEARCH_COMPLETED = 'flight_search_completed',
  HOTEL_SEARCH_STARTED = 'hotel_search_started',
  HOTEL_SEARCH_COMPLETED = 'hotel_search_completed',
  ACTIVITY_SEARCH_STARTED = 'activity_search_started',
  ACTIVITY_SEARCH_COMPLETED = 'activity_search_completed',
  BOOKING_STARTED = 'booking_started',
  BOOKING_CONFIRMED = 'booking_confirmed',
  BOOKING_FAILED = 'booking_failed',
  USER_INPUT = 'user_input',
  USER_FEEDBACK = 'user_feedback'
}

/**
 * Frontend event types (existing)
 */
export enum FrontendEventType {
  PLAN_UPDATE = 'PLAN_UPDATE',
  INTERACTION_REQUEST = 'INTERACTION_REQUEST',
  SYSTEM_NOTIFICATION = 'SYSTEM_NOTIFICATION',
  CONNECTION_ACK = 'CONNECTION_ACK',
  NOTIFICATION = 'NOTIFICATION',
  ERROR = 'ERROR',
  STAGE_CHANGE = 'STAGE_CHANGE',
  AGENT_ACTIVATED = 'AGENT_ACTIVATED',
  RESULTS_UPDATED = 'RESULTS_UPDATED'
}

/**
 * Backend Strands message format
 */
export interface BackendStrandsMessage {
  type: string;
  data: any;
  timestamp: string;
}

/**
 * Maps backend-strands event types to frontend event types
 */
const EVENT_TYPE_MAPPING: Record<BackendStrandsEventType, FrontendEventType | null> = {
  [BackendStrandsEventType.CONNECTION_ESTABLISHED]: FrontendEventType.CONNECTION_ACK,
  [BackendStrandsEventType.CONNECTION_CLOSED]: FrontendEventType.SYSTEM_NOTIFICATION,
  [BackendStrandsEventType.PLANNING_STARTED]: FrontendEventType.STAGE_CHANGE,
  [BackendStrandsEventType.PLANNING_UPDATE]: FrontendEventType.PLAN_UPDATE,
  [BackendStrandsEventType.PLANNING_COMPLETED]: FrontendEventType.STAGE_CHANGE,
  [BackendStrandsEventType.PLANNING_ERROR]: FrontendEventType.ERROR,
  [BackendStrandsEventType.AGENT_THINKING]: FrontendEventType.AGENT_ACTIVATED,
  [BackendStrandsEventType.AGENT_RESPONSE]: FrontendEventType.PLAN_UPDATE,
  [BackendStrandsEventType.TOOL_CALL]: FrontendEventType.AGENT_ACTIVATED,
  [BackendStrandsEventType.TOOL_RESULT]: FrontendEventType.RESULTS_UPDATED,
  [BackendStrandsEventType.FLIGHT_SEARCH_STARTED]: FrontendEventType.AGENT_ACTIVATED,
  [BackendStrandsEventType.FLIGHT_SEARCH_COMPLETED]: FrontendEventType.RESULTS_UPDATED,
  [BackendStrandsEventType.HOTEL_SEARCH_STARTED]: FrontendEventType.AGENT_ACTIVATED,
  [BackendStrandsEventType.HOTEL_SEARCH_COMPLETED]: FrontendEventType.RESULTS_UPDATED,
  [BackendStrandsEventType.ACTIVITY_SEARCH_STARTED]: FrontendEventType.AGENT_ACTIVATED,
  [BackendStrandsEventType.ACTIVITY_SEARCH_COMPLETED]: FrontendEventType.RESULTS_UPDATED,
  [BackendStrandsEventType.BOOKING_STARTED]: FrontendEventType.AGENT_ACTIVATED,
  [BackendStrandsEventType.BOOKING_CONFIRMED]: FrontendEventType.RESULTS_UPDATED,
  [BackendStrandsEventType.BOOKING_FAILED]: FrontendEventType.ERROR,
  [BackendStrandsEventType.USER_INPUT]: FrontendEventType.INTERACTION_REQUEST,
  [BackendStrandsEventType.USER_FEEDBACK]: FrontendEventType.SYSTEM_NOTIFICATION
};

/**
 * Backend Strands WebSocket Adapter
 */
export class BackendStrandsAdapter {
  private streamingBuffer: Map<string, string[]> = new Map();
  
  /**
   * Transform backend-strands message to frontend format
   */
  public transformMessage(message: BackendStrandsMessage): WebSocketMessage | null {
    const eventType = message.type as BackendStrandsEventType;
    const mappedType = EVENT_TYPE_MAPPING[eventType];
    
    if (!mappedType) {
      console.warn(`Unknown backend-strands event type: ${message.type}`);
      return null;
    }
    
    // Transform based on event type
    switch (eventType) {
      case BackendStrandsEventType.CONNECTION_ESTABLISHED:
        return {
          type: FrontendEventType.CONNECTION_ACK,
          payload: {
            clientId: message.data.plan_id || 'anonymous',
            timestamp: message.timestamp,
            planId: message.data.plan_id
          },
          timestamp: message.timestamp
        };
        
      case BackendStrandsEventType.PLANNING_STARTED:
        return {
          type: FrontendEventType.STAGE_CHANGE,
          payload: {
            currentStage: 'planning',
            previousStage: 'idle',
            planId: message.data.plan_id,
            timestamp: message.timestamp
          },
          timestamp: message.timestamp
        };
        
      case BackendStrandsEventType.PLANNING_COMPLETED:
        return {
          type: FrontendEventType.STAGE_CHANGE,
          payload: {
            currentStage: 'complete',
            previousStage: 'executing',
            planId: message.data.plan_id,
            results: message.data.final_plan,
            timestamp: message.timestamp
          },
          timestamp: message.timestamp
        };
        
      case BackendStrandsEventType.PLANNING_ERROR:
        return {
          type: FrontendEventType.ERROR,
          payload: {
            error: message.data.error || 'Planning error occurred',
            details: message.data,
            timestamp: message.timestamp
          },
          timestamp: message.timestamp
        };
        
      case BackendStrandsEventType.AGENT_THINKING:
        return {
          type: FrontendEventType.AGENT_ACTIVATED,
          payload: {
            agentType: this.extractAgentType(message.data),
            agentName: message.data.agent || 'Agent',
            message: message.data.message,
            timestamp: message.timestamp
          },
          timestamp: message.timestamp
        };
        
      case BackendStrandsEventType.AGENT_RESPONSE:
        return this.handleAgentResponse(message);
        
      case BackendStrandsEventType.TOOL_CALL:
        return {
          type: FrontendEventType.AGENT_ACTIVATED,
          payload: {
            agentType: this.extractAgentTypeFromTool(message.data.tool),
            agentName: `${message.data.tool} Tool`,
            message: `Executing ${message.data.tool}...`,
            timestamp: message.timestamp
          },
          timestamp: message.timestamp
        };
        
      case BackendStrandsEventType.TOOL_RESULT:
        return this.transformToolResult(message);
        
      case BackendStrandsEventType.FLIGHT_SEARCH_STARTED:
      case BackendStrandsEventType.HOTEL_SEARCH_STARTED:
      case BackendStrandsEventType.ACTIVITY_SEARCH_STARTED:
      case BackendStrandsEventType.BOOKING_STARTED:
        return {
          type: FrontendEventType.AGENT_ACTIVATED,
          payload: {
            agentType: this.extractAgentTypeFromEvent(eventType),
            agentName: this.getAgentNameFromEvent(eventType),
            message: `${this.getAgentNameFromEvent(eventType)} started...`,
            timestamp: message.timestamp
          },
          timestamp: message.timestamp
        };
        
      case BackendStrandsEventType.FLIGHT_SEARCH_COMPLETED:
      case BackendStrandsEventType.HOTEL_SEARCH_COMPLETED:
      case BackendStrandsEventType.ACTIVITY_SEARCH_COMPLETED:
      case BackendStrandsEventType.BOOKING_CONFIRMED:
        return this.transformSearchResult(eventType, message);
        
      case BackendStrandsEventType.USER_INPUT:
        return {
          type: FrontendEventType.INTERACTION_REQUEST,
          payload: {
            interactionId: message.data.interaction_id,
            question: message.data.prompt,
            options: message.data.options,
            timestamp: message.timestamp
          },
          timestamp: message.timestamp
        };
        
      default:
        return {
          type: mappedType,
          payload: message.data,
          timestamp: message.timestamp
        };
    }
  }
  
  /**
   * Handle streaming agent responses
   */
  private handleAgentResponse(message: BackendStrandsMessage): WebSocketMessage | null {
    const agentId = message.data.agent_id || 'default';
    
    // Handle streaming chunks
    if (message.data.chunk) {
      // Buffer the chunk
      if (!this.streamingBuffer.has(agentId)) {
        this.streamingBuffer.set(agentId, []);
      }
      this.streamingBuffer.get(agentId)!.push(message.data.chunk);
      
      // Return update with partial content
      return {
        type: FrontendEventType.PLAN_UPDATE,
        payload: {
          streaming: true,
          content: this.streamingBuffer.get(agentId)!.join(''),
          agentId,
          timestamp: message.timestamp
        },
        timestamp: message.timestamp
      };
    }
    
    // Handle complete response
    if (message.data.complete) {
      const fullContent = this.streamingBuffer.get(agentId)?.join('') || message.data.content;
      this.streamingBuffer.delete(agentId);
      
      return {
        type: FrontendEventType.PLAN_UPDATE,
        payload: {
          streaming: false,
          content: fullContent,
          agentId,
          complete: true,
          timestamp: message.timestamp
        },
        timestamp: message.timestamp
      };
    }
    
    // Handle non-streaming response
    return {
      type: FrontendEventType.PLAN_UPDATE,
      payload: {
        content: message.data.content,
        agentId,
        timestamp: message.timestamp
      },
      timestamp: message.timestamp
    };
  }
  
  /**
   * Transform tool results to frontend format using unified data transformer
   */
  private transformToolResult(message: BackendStrandsMessage): WebSocketMessage {
    const tool = message.data.tool;
    const result = message.data.result;
    
    let rawResults: any[] = [];
    
    // Extract raw results based on tool type
    if (tool === 'search_flights' && result.outbound_flights) {
      rawResults = result.outbound_flights;
    } else if (tool === 'search_hotels' && result.hotels) {
      rawResults = result.hotels;
    } else if (tool === 'search_activities' && result.results) {
      rawResults = result.results;
    } else {
      console.warn(`Unknown tool result format for tool: ${tool}`, result);
      return {
        type: FrontendEventType.RESULTS_UPDATED,
        payload: {
          results: [],
          tool,
          timestamp: message.timestamp
        },
        timestamp: message.timestamp
      };
    }
    
    // Transform using unified data transformation service
    let transformedResults: StandardizedResult[] = [];
    
    try {
      transformedResults = dataTransformationService.transformResultsBatch(
        rawResults, 
        'backend-strands'
      );
    } catch (error) {
      console.error('Error transforming tool results:', error);
      const errorMessage = error instanceof Error ? error.message : String(error);
      // Return error result
      transformedResults = [{
        id: `error-${Date.now()}`,
        type: 'text',
        title: 'Transformation Error',
        description: `Failed to transform ${tool} results`,
        timestamp: message.timestamp,
        content: `Error transforming ${tool} results: ${errorMessage}\n\nRaw data:\n${JSON.stringify(result, null, 2)}`
      }];
    }
    
    return {
      type: FrontendEventType.RESULTS_UPDATED,
      payload: {
        results: transformedResults,
        tool,
        timestamp: message.timestamp
      },
      timestamp: message.timestamp
    };
  }
  
  /**
   * Transform search results to frontend format using unified data transformer
   */
  private transformSearchResult(eventType: BackendStrandsEventType, message: BackendStrandsMessage): WebSocketMessage {
    const results = message.data.results || [];
    
    let transformedResults: StandardizedResult[] = [];
    
    try {
      transformedResults = dataTransformationService.transformResultsBatch(
        results,
        'backend-strands'
      );
    } catch (error) {
      console.error('Error transforming search results:', error);
      const errorMessage = error instanceof Error ? error.message : String(error);
      // Return error result
      transformedResults = [{
        id: `error-${Date.now()}`,
        type: 'text',
        title: 'Transformation Error',
        description: `Failed to transform search results from ${eventType}`,
        timestamp: message.timestamp,
        content: `Error transforming search results: ${errorMessage}\n\nRaw data:\n${JSON.stringify(results, null, 2)}`
      }];
    }
    
    return {
      type: FrontendEventType.RESULTS_UPDATED,
      payload: {
        results: transformedResults,
        timestamp: message.timestamp
      },
      timestamp: message.timestamp
    };
  }
  
  /**
   * Extract agent type from data
   */
  private extractAgentType(data: any): string {
    const agent = data.agent?.toLowerCase() || '';
    
    if (agent.includes('flight')) return 'flight';
    if (agent.includes('hotel')) return 'hotel';
    if (agent.includes('activity') || agent.includes('attraction')) return 'attraction';
    if (agent.includes('budget')) return 'pricing';
    if (agent.includes('destination')) return 'destination';
    if (agent.includes('orchestrator')) return 'scheduling';
    
    return 'assistant';
  }
  
  /**
   * Extract agent type from tool name
   */
  private extractAgentTypeFromTool(tool: string): string {
    const toolLower = tool.toLowerCase();
    
    if (toolLower.includes('flight')) return 'flight';
    if (toolLower.includes('hotel')) return 'hotel';
    if (toolLower.includes('activity')) return 'attraction';
    if (toolLower.includes('budget')) return 'pricing';
    if (toolLower.includes('destination')) return 'destination';
    
    return 'assistant';
  }
  
  /**
   * Extract agent type from event type
   */
  private extractAgentTypeFromEvent(eventType: BackendStrandsEventType): string {
    if (eventType.includes('FLIGHT')) return 'flight';
    if (eventType.includes('HOTEL')) return 'hotel';
    if (eventType.includes('ACTIVITY')) return 'attraction';
    if (eventType.includes('BOOKING')) return 'booking';
    
    return 'assistant';
  }
  
  /**
   * Get agent name from event type
   */
  private getAgentNameFromEvent(eventType: BackendStrandsEventType): string {
    if (eventType.includes('FLIGHT')) return 'Flight Search';
    if (eventType.includes('HOTEL')) return 'Hotel Search';
    if (eventType.includes('ACTIVITY')) return 'Activity Search';
    if (eventType.includes('BOOKING')) return 'Booking';
    
    return 'Search';
  }
  
  /**
   * Transform frontend message to backend-strands format
   */
  public transformOutgoingMessage(type: string, payload: any): { type: string; data: any } {
    // Map frontend message types to backend-strands format
    switch (type) {
      case 'CONNECTION_ACK':
        return {
          type: 'connection_ack',
          data: {
            client_id: payload.clientId,
            user_agent: payload.userAgent
          }
        };
        
      case 'USER_RESPONSE':
        return {
          type: 'user_response',
          data: {
            interaction_id: payload.interactionId,
            response: payload.response
          }
        };
        
      default:
        // Pass through with lowercase type
        return {
          type: type.toLowerCase(),
          data: payload
        };
    }
  }
}

// Export singleton instance
export const backendStrandsAdapter = new BackendStrandsAdapter();