import { WebSocketMessage } from '../common/apiClient';
import { config } from '../common/config';
import { backendStrandsAdapter, BackendStrandsMessage } from './BackendStrandsAdapter';
import { pollingService } from '../polling/PollingService';
import { backendStrandsApiClient } from '../api/BackendStrandsApiClient';

/**
 * WebSocket connection states
 */
export enum WebSocketState {
  CONNECTING = 'connecting',
  OPEN = 'open',
  CLOSING = 'closing',
  CLOSED = 'closed',
}

/**
 * WebSocket message types
 */
export enum WebSocketMessageType {
  PLAN_UPDATE = 'plan_update',
  INTERACTION_REQUEST = 'interaction_request',
  SYSTEM_NOTIFICATION = 'system_notification',
  CONNECTION_ACK = 'connection_ack',
  NOTIFICATION = 'NOTIFICATION',
  ERROR = 'error',
  STAGE_CHANGE = 'stage_change',
  AGENT_ACTIVATED = 'agent_activated',
  RESULTS_UPDATED = 'results_updated',
}

/**
 * WebSocket event listener type
 */
export type WebSocketEventListener = (event: WebSocketMessage) => void;

/**
 * WebSocket service for handling real-time communications
 */
class WebSocketService {
  private socket: WebSocket | null = null;
  private url: string;
  private reconnectAttempts: number = 0;
  private maxReconnectAttempts: number = 5;
  private reconnectTimeout: number = 0;
  private reconnectIntervalId?: number;
  private eventListeners: Map<string, Set<WebSocketEventListener>> = new Map();
  private connectionState: WebSocketState = WebSocketState.CLOSED;
  private userId?: string;
  private planId?: string;
  private useBackendStrands: boolean = false;
  private usePolling: boolean = false;
  private previousActiveAgents: Set<string> = new Set();

  constructor() {
    // WebSocket endpoint from configuration
    this.url = config.webSocketEndpoint;
    // Check if we should use backend-strands mode
    this.useBackendStrands = config.useBackendStrands || false;
    // Use polling if backend-strands is enabled but no valid WebSocket endpoint
    // Check for empty, whitespace-only, or URLs that don't start with ws/wss
    const hasValidWebSocketUrl = this.url && 
                                 this.url.trim() !== '' && 
                                 (this.url.startsWith('ws://') || this.url.startsWith('wss://'));
    this.usePolling = this.useBackendStrands && !hasValidWebSocketUrl;
    
    if (this.usePolling) {
      console.log('WebSocketService: Using polling mode (no valid WebSocket URL)');
    }
  }

  /**
   * Get the current connection state
   */
  public getState(): WebSocketState {
    return this.connectionState;
  }

  /**
   * Set the user ID for the connection
   * @param userId The user ID for the connection
   */
  public setUserId(userId: string): void {
    this.userId = userId;
    // If we already have an active connection, reconnect to add the user ID
    if (this.connectionState === WebSocketState.OPEN) {
      this.reconnect();
    }
  }

  /**
   * Set the plan ID for backend-strands connection
   * @param planId The plan ID for the connection
   */
  public setPlanId(planId: string): void {
    this.planId = planId;
    
    // If using polling mode, start polling for this plan
    if (this.usePolling && this.connectionState === WebSocketState.OPEN) {
      this.startPollingForPlan(planId);
    }
    // If we're using backend-strands WebSocket and already connected, reconnect with the plan ID
    else if (this.useBackendStrands && this.connectionState === WebSocketState.OPEN && !this.usePolling) {
      this.reconnect();
    }
  }

  /**
   * Connect to the WebSocket server
   */
  public connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      // If using polling mode, simulate connection
      if (this.usePolling) {
        this.connectionState = WebSocketState.OPEN;
        console.log('Using polling mode instead of WebSocket');
        
        // Start polling if we have a plan ID
        if (this.planId) {
          this.startPollingForPlan(this.planId);
        }
        
        resolve();
        return;
      }
      
      // Real WebSocket connection logic
      if (this.socket && this.connectionState === WebSocketState.OPEN) {
        resolve();
        return;
      }

      this.connectionState = WebSocketState.CONNECTING;

      // Build WebSocket URL based on mode
      let wsUrl = this.url;
      
      if (this.useBackendStrands) {
        // Backend-strands mode requires a plan ID
        if (!this.planId) {
          console.warn('Backend-strands mode requires a plan ID for WebSocket connection');
          this.connectionState = WebSocketState.CLOSED;
          reject(new Error('Plan ID required for backend-strands WebSocket connection'));
          return;
        }
        // Backend-strands mode: use plan-specific endpoint
        wsUrl = `${this.url}/ws/planning/${encodeURIComponent(this.planId)}`;
      } else {
        // Legacy mode: add user ID as query parameter
        if (this.userId) {
          wsUrl += `?userId=${encodeURIComponent(this.userId)}`;
        }
      }

      this.socket = new WebSocket(wsUrl);

      this.socket.onopen = () => {
        this.connectionState = WebSocketState.OPEN;
        this.reconnectAttempts = 0;
        this.clearReconnectInterval();
        
        console.log('WebSocket connection established');
        
        // Send initial connection message
        this.sendMessage(WebSocketMessageType.CONNECTION_ACK, {
          clientId: this.userId || 'anonymous',
          timestamp: new Date().toISOString(),
          userAgent: navigator.userAgent
        });
        
        resolve();
      };

      this.socket.onclose = (event) => {
        this.connectionState = WebSocketState.CLOSED;
        console.log(`WebSocket connection closed: ${event.code} - ${event.reason}`);
        
        if (!event.wasClean) {
          this.attemptReconnect();
        }
      };

      this.socket.onerror = (error) => {
        console.error('WebSocket error:', error);
        
        if (this.connectionState === WebSocketState.CONNECTING) {
          reject(new Error('Failed to establish WebSocket connection'));
        }
        
        // Emit an error event to all listeners
        this.emitEvent(WebSocketMessageType.ERROR, {
          error: 'Connection error',
          timestamp: Date.now(),
        });
      };

      this.socket.onmessage = (event) => {
        try {
          let message: WebSocketMessage;
          
          if (this.useBackendStrands) {
            // Parse as backend-strands format and transform
            const backendMessage = JSON.parse(event.data) as BackendStrandsMessage;
            const transformed = backendStrandsAdapter.transformMessage(backendMessage);
            
            if (!transformed) {
              console.warn('Could not transform backend-strands message:', backendMessage);
              return;
            }
            
            message = transformed;
          } else {
            // Parse as legacy format
            message = JSON.parse(event.data) as WebSocketMessage;
            
            // Route NOTIFICATION message type to appropriate listeners
            if (message.type === 'NOTIFICATION') {
              // Handle custom notification message routing
              const notificationType = message.payload?.data?.type || 'SYSTEM_NOTIFICATION';
              
              // Route to specific listener and also preserve original type
              this.handleMessage({
                type: WebSocketMessageType.SYSTEM_NOTIFICATION,
                payload: {
                  message: message.payload.message,
                  timestamp: message.payload.timestamp,
                  ...message.payload.data
                }
              });
              
              // Keep original message processing as well
              this.handleMessage(message);
              return;
            }
          }
          
          this.handleMessage(message);
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };
    });
  }

  /**
   * Disconnect from the WebSocket server
   */
  public disconnect(): void {
    // Stop polling if in polling mode
    if (this.usePolling) {
      if (this.planId) {
        pollingService.stopPolling(this.planId);
      }
      this.connectionState = WebSocketState.CLOSED;
      return;
    }
    
    this.clearReconnectInterval();
    
    // Normal disconnection logic
    if (this.socket && this.connectionState !== WebSocketState.CLOSED) {
      this.connectionState = WebSocketState.CLOSING;
      this.socket.close();
      this.socket = null;
    }
  }

  /**
   * Reconnect to the WebSocket server
   */
  public reconnect(): void {
    this.disconnect();
    this.connect().catch((error) => {
      console.error('Error reconnecting to WebSocket:', error);
      this.attemptReconnect();
    });
  }

  /**
   * Attempt to reconnect with exponential backoff
   */
  private attemptReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Maximum reconnection attempts reached');
      return;
    }

    this.clearReconnectInterval();
    
    this.reconnectAttempts++;
    this.reconnectTimeout = Math.min(30000, 1000 * Math.pow(2, this.reconnectAttempts));
    
    console.log(`Attempting to reconnect in ${this.reconnectTimeout / 1000} seconds...`);
    
    this.reconnectIntervalId = window.setTimeout(() => {
      this.connect().catch((error) => {
        console.error('Error during reconnection attempt:', error);
        this.attemptReconnect();
      });
    }, this.reconnectTimeout);
  }

  /**
   * Clear the reconnect interval
   */
  private clearReconnectInterval(): void {
    if (this.reconnectIntervalId) {
      clearTimeout(this.reconnectIntervalId);
      this.reconnectIntervalId = undefined;
    }
  }
  

  /**
   * Handle incoming WebSocket messages
   * @param message The received message
   */
  private handleMessage(message: WebSocketMessage): void {
    // Log the received message in development
    if (process.env.NODE_ENV === 'development') {
      console.log('WebSocket message received:', message);
    }

    // Special handling for NOTIFICATION messages from the AWS Step Functions
    if (message.type === WebSocketMessageType.NOTIFICATION) {
      // The payload structure from AWS Step Functions notification task
      const executionArn = message.payload?.data?.executionArn;
      const status = message.payload?.data?.status;
      const currentStage = message.payload?.data?.currentStage;
      const details = message.payload?.data?.details;
      
      // Create normalized messages for each type of information
      if (currentStage) {
        this.emitEvent(WebSocketMessageType.STAGE_CHANGE, {
          currentStage,
          previousStage: details?.previousStage,
          timestamp: message.payload?.timestamp || new Date().toISOString()
        });
      }
      
      if (details?.activeAgents) {
        details.activeAgents.forEach((agent: string) => {
          this.emitEvent(WebSocketMessageType.AGENT_ACTIVATED, {
            agentType: agent,
            timestamp: message.payload?.timestamp || new Date().toISOString()
          });
        });
      }
      
      if (details?.results) {
        this.emitEvent(WebSocketMessageType.RESULTS_UPDATED, {
          results: details.results,
          timestamp: message.payload?.timestamp || new Date().toISOString()
        });
      }
      
      // Also emit the original notification in case other listeners need it
      this.emitEvent(WebSocketMessageType.SYSTEM_NOTIFICATION, message.payload);
    }

    // Emit the event to all listeners for this type
    this.emitEvent(message.type, message.payload);
  }

  /**
   * Emit an event to all listeners for a specific type
   * @param type The event type
   * @param payload The event payload
   */
  private emitEvent(type: string, payload: any): void {
    const message: WebSocketMessage = { 
      type, 
      payload,
      timestamp: new Date().toISOString()
    };
    
    // Get listeners for this type
    const listeners = this.eventListeners.get(type);
    if (listeners) {
      listeners.forEach((listener) => {
        try {
          listener(message);
        } catch (error) {
          console.error(`Error in WebSocket event listener for type ${type}:`, error);
        }
      });
    }

    // Also notify the "all" listeners
    const allListeners = this.eventListeners.get('all');
    if (allListeners) {
      allListeners.forEach((listener) => {
        try {
          listener(message);
        } catch (error) {
          console.error(`Error in WebSocket "all" event listener:`, error);
        }
      });
    }
  }

  /**
   * Send a message to the WebSocket server
   * @param type The message type
   * @param payload The message payload
   */
  public sendMessage(type: string, payload: any): boolean {
    // Check connection state
    if (!this.socket || this.connectionState !== WebSocketState.OPEN) {
      console.error('Cannot send message: WebSocket not connected');
      return false;
    }

    try {
      let messageToSend: any;
      
      if (this.useBackendStrands) {
        // Transform to backend-strands format
        const transformed = backendStrandsAdapter.transformOutgoingMessage(type, payload);
        messageToSend = {
          ...transformed,
          timestamp: new Date().toISOString()
        };
      } else {
        // Use legacy format
        messageToSend = { type, payload };
      }
      
      this.socket.send(JSON.stringify(messageToSend));
      return true;
    } catch (error) {
      console.error('Error sending WebSocket message:', error);
      return false;
    }
  }
  
  /**
   * Start polling for a specific plan
   */
  private startPollingForPlan(planId: string): void {
    // Track the last known status to detect changes
    let lastKnownStatus: string | null = null;
    
    pollingService.startPolling(
      planId,
      backendStrandsApiClient,
      (statusData) => {
        // Log the full response to see what data we're receiving
        console.log('Polling response received:', JSON.stringify(statusData, null, 2));
        
        // Check if status has changed and emit stage change event
        if (statusData.status && statusData.status !== lastKnownStatus) {
          const previousStatus = lastKnownStatus;
          lastKnownStatus = statusData.status;
          
          // Map backend status to frontend workflow stages
          const statusToStageMap: Record<string, string> = {
            'idle': 'idle',
            'planning': 'planning',
            'processing': 'executing',
            'executing': 'executing',
            'routing': 'routing',
            'updating': 'updating',
            'completed': 'complete',
            'failed': 'complete',
            'cancelled': 'complete'
          };
          
          const currentStage = statusToStageMap[statusData.status] || statusData.status;
          const previousStage = previousStatus ? (statusToStageMap[previousStatus] || previousStatus) : 'idle';
          
          console.log(`Status changed from ${previousStatus} to ${statusData.status}, emitting stage change from ${previousStage} to ${currentStage}`);
          
          // Emit stage change event
          this.emitEvent(WebSocketMessageType.STAGE_CHANGE, {
            currentStage,
            previousStage,
            timestamp: new Date().toISOString()
          });
        }
        
        // Emit a simple plan update message
        this.emitEvent(WebSocketMessageType.PLAN_UPDATE, {
          planId,
          status: statusData.status,
          timestamp: new Date().toISOString()
        });
        
        // Check if there are agents in the response (now an object, not array)
        if (statusData.agents && typeof statusData.agents === 'object') {
          console.log('Agents status found:', statusData.agents);
          
          // Create a mapping from backend agent names to frontend agent types
          const agentNameMapping: Record<string, string> = {
            'search_flights': 'flight',
            'search_hotels': 'hotel',
            'search_activities': 'activity',
            'search_destinations': 'destination',
            'analyze_budget': 'budget',
            'compile_itinerary': 'orchestrator',
            'search_dining': 'dining',
            'search_transportation': 'transportation',
            'check_weather': 'weather',
            'optimize_pricing': 'pricing',
            'plan_scheduling': 'scheduling'
          };
          
          // Track currently active agents
          const currentActiveAgents = new Set<string>();
          
          // Process each agent in the response
          Object.entries(statusData.agents).forEach(([agentName, agentData]: [string, any]) => {
            // Map the backend agent name to frontend agent type
            const agentType = agentNameMapping[agentName] || agentName;
            
            if (agentData.status === 'active') {
              currentActiveAgents.add(agentType);
              
              // Always emit activation for active agents to refresh the 10-second timer
              console.log(`Agent ${agentName} (${agentType}) is active:`, agentData.message);
              
              this.emitEvent(WebSocketMessageType.AGENT_ACTIVATED, {
                agentType: agentType,
                agentName: agentName,
                message: agentData.message || `${agentType} is processing...`,
                timestamp: agentData.timestamp || new Date().toISOString()
              });
            }
          });
          
          // Update the tracked set of active agents
          this.previousActiveAgents = currentActiveAgents;
        }
        
        // Check for orchestrator_response in different possible locations
        const orchestratorResponse = statusData.orchestrator_response || 
                                    statusData.orchestratorResponse ||
                                    statusData.final_response ||
                                    statusData.finalResponse ||
                                    statusData.results?.orchestrator_response ||
                                    statusData.results?.final_response ||
                                    statusData.results;
        
        if (orchestratorResponse && typeof orchestratorResponse === 'string') {
          console.log('Travel plan completed! Displaying results...');
          // Transform the string response into a markdown result object
          const markdownResult = {
            id: `plan-${planId}-${Date.now()}`,
            type: 'markdown',
            content: orchestratorResponse
          };
          this.emitEvent(WebSocketMessageType.RESULTS_UPDATED, {
            planId,
            results: [markdownResult], // Wrap in array as expected by ChatContext
            timestamp: new Date().toISOString()
          });
        }
      },
      2000 // Poll every 2 seconds
    );
  }

  /**
   * Add event listener for WebSocket messages
   * @param type Message type to listen for, or 'all' for all messages
   * @param listener Event listener function
   */
  public addEventListener(type: string, listener: WebSocketEventListener): void {
    if (!this.eventListeners.has(type)) {
      this.eventListeners.set(type, new Set());
    }
    
    const listeners = this.eventListeners.get(type)!;
    listeners.add(listener);
  }

  /**
   * Remove event listener for WebSocket messages
   * @param type Message type
   * @param listener Event listener function to remove
   * @returns true if the listener was removed, false if not found
   */
  public removeEventListener(type: string, listener: WebSocketEventListener): boolean {
    const listeners = this.eventListeners.get(type);
    if (listeners && listeners.has(listener)) {
      listeners.delete(listener);
      return true;
    }
    return false;
  }

  /**
   * Remove all event listeners for a type or all types
   * @param type Optional message type, if not provided all listeners will be removed
   */
  public removeAllEventListeners(type?: string): void {
    if (type) {
      this.eventListeners.delete(type);
    } else {
      this.eventListeners.clear();
    }
  }
}

// Export singleton instance
const webSocketService = new WebSocketService();
export default webSocketService; 