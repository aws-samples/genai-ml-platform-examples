import { 
  ConnectionStatus, 
  WorkflowUpdate, 
  WorkflowUpdateType 
} from '../../models/WorkflowUpdate';

import { config } from '../common/config';
import webSocketService from './WebSocketService';

/**
 * Configuration options for the WorkflowUpdateService
 */
interface WorkflowUpdateServiceConfig {
  /** The WebSocket endpoint URL */
  endpoint: string;
  /** Auto-reconnect when connection is lost */
  autoReconnect?: boolean;
  /** Maximum number of reconnect attempts */
  maxReconnectAttempts?: number;
  /** Initial reconnect delay in milliseconds */
  initialReconnectDelay?: number;
  /** Maximum reconnect delay in milliseconds */
  maxReconnectDelay?: number;
}

/**
 * Constants for default configuration
 */
const DEFAULT_CONFIG: WorkflowUpdateServiceConfig = {
  endpoint: process.env.REACT_APP_WEBSOCKET_ENDPOINT || 'wss://example.com/workflow-updates',
  autoReconnect: true,
  maxReconnectAttempts: 10,
  initialReconnectDelay: 1000,
  maxReconnectDelay: 30000
};

/**
 * Event handler type for workflow updates
 */
type WorkflowUpdateHandler = (update: WorkflowUpdate) => void;

/**
 * Service for managing workflow updates via WebSocket
 */
export class WorkflowUpdateService {
  private socket: WebSocket | null = null;
  private config: WorkflowUpdateServiceConfig;
  private updateHandlers: WorkflowUpdateHandler[] = [];
  
  private connectionStatusHandlers: ((status: ConnectionStatus) => void)[] = [];
  private reconnectAttempts: number = 0;
  private reconnectTimeout: NodeJS.Timeout | null = null;
  private currentConnectionStatus: ConnectionStatus = ConnectionStatus.DISCONNECTED;
  private sessionId: string = '';

  /**
   * Creates a new instance of the WorkflowUpdateService
   * @param config Configuration options
   */
  constructor(config: Partial<WorkflowUpdateServiceConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.sessionId = this.generateSessionId();
  }

  /**
   * Connects to the WebSocket server
   */
  public connect(): void {
    if (this.socket) {
      return; // Already connected or connecting
    }

    this.setConnectionStatus(ConnectionStatus.CONNECTING);

    // Check if backend-strands mode is enabled
    if (config.useBackendStrands) {
      console.log('WorkflowUpdateService: Backend-strands mode enabled, using WebSocketService');
      
      // Set up message handler for backend-strands
      webSocketService.addEventListener('all', (message) => {
        console.log('WorkflowUpdateService: Received message from WebSocketService:', message);
        
        // Map WebSocket message types to WorkflowUpdate types
        const typeMapping: Record<string, WorkflowUpdateType> = {
          'stage_change': WorkflowUpdateType.STAGE_CHANGE,
          'agent_activated': WorkflowUpdateType.AGENT_ACTIVATED,
          'agent_deactivated': WorkflowUpdateType.AGENT_DEACTIVATED,
          'agent_complete': WorkflowUpdateType.AGENT_COMPLETE,
          'agent_error': WorkflowUpdateType.AGENT_ERROR,
          'system_notification': WorkflowUpdateType.SYSTEM_NOTIFICATION,
          'system_error': WorkflowUpdateType.SYSTEM_ERROR,
          'plan_update': WorkflowUpdateType.PLAN_UPDATE,
          'PLAN_UPDATE': WorkflowUpdateType.PLAN_UPDATE,
          'results_updated': WorkflowUpdateType.RESULTS_UPDATED,
          'connection_status': WorkflowUpdateType.CONNECTION_STATUS,
          'error': WorkflowUpdateType.SYSTEM_ERROR,
          'NOTIFICATION': WorkflowUpdateType.SYSTEM_NOTIFICATION
        };
        
        const mappedType = typeMapping[message.type] || message.type as WorkflowUpdateType;
        
        // Convert the WebSocketService message to WorkflowUpdate format
        const update: WorkflowUpdate = {
          type: mappedType,
          timestamp: message.timestamp || new Date().toISOString(),
          sessionId: this.sessionId,
          payload: message.payload
        };
        
        this.notifyUpdateHandlers(update);
      });
      
      // Update connection status based on WebSocketService state
      const checkConnectionStatus = () => {
        const wsState = webSocketService.getState();
        if (wsState === 'open') {
          this.setConnectionStatus(ConnectionStatus.CONNECTED);
        } else if (wsState === 'connecting') {
          this.setConnectionStatus(ConnectionStatus.CONNECTING);
        } else if (wsState === 'closed') {
          this.setConnectionStatus(ConnectionStatus.DISCONNECTED);
        }
      };
      
      // Check status immediately and set up periodic check
      checkConnectionStatus();
      const statusInterval = setInterval(checkConnectionStatus, 1000);
      
      // Store the interval ID for cleanup
      this.reconnectTimeout = statusInterval as any;
      
      // WebSocketService should already be connected from TravelPlanService
      if (webSocketService.getState() !== 'open') {
        console.log('WorkflowUpdateService: WebSocketService not connected, waiting...');
      }
      
      return;
    }

    try {
      console.log('WorkflowUpdateService: Connecting to real WebSocket at', this.config.endpoint);
      this.socket = new WebSocket(this.config.endpoint);
      
      this.socket.onopen = this.handleSocketOpen.bind(this);
      this.socket.onmessage = this.handleSocketMessage.bind(this);
      this.socket.onclose = this.handleSocketClose.bind(this);
      this.socket.onerror = this.handleSocketError.bind(this);
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
      this.setConnectionStatus(ConnectionStatus.ERROR);
      this.attemptReconnect();
    }
  }

  /**
   * Disconnects from the WebSocket server
   */
  public disconnect(): void {
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }

    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    
    this.setConnectionStatus(ConnectionStatus.DISCONNECTED);
  }

  /**
   * Subscribe to workflow updates
   * @param handler Function to call when updates are received
   * @returns Unsubscribe function
   */
  public subscribeToUpdates(handler: WorkflowUpdateHandler): () => void {
    this.updateHandlers.push(handler);
    
    return () => {
      const index = this.updateHandlers.indexOf(handler);
      if (index > -1) {
        this.updateHandlers.splice(index, 1);
      }
    };
  }

  /**
   * Subscribe to connection status changes
   * @param handler Function to call when connection status changes
   * @returns Unsubscribe function
   */
  public subscribeToConnectionStatus(handler: (status: ConnectionStatus) => void): () => void {
    this.connectionStatusHandlers.push(handler);
    
    // Immediately notify of current status
    handler(this.currentConnectionStatus);
    
    return () => {
      const index = this.connectionStatusHandlers.indexOf(handler);
      if (index > -1) {
        this.connectionStatusHandlers.splice(index, 1);
      }
    };
  }

  /**
   * Get the current connection status
   */
  public getConnectionStatus(): ConnectionStatus {
    return this.currentConnectionStatus;
  }

  /**
   * Send a message to the server (if connected)
   * @param message The message to send
   */
  public sendMessage(message: any): void {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(message));
    } else if (config.useBackendStrands) {
      // Use WebSocketService for backend-strands mode
      webSocketService.sendMessage(message.type, message.payload);
    } else {
      console.warn('Cannot send message: WebSocket not connected');
    }
  }

  /**
   * Handle WebSocket open event
   */
  private handleSocketOpen(event: Event): void {
    console.log('WebSocket connection established');
    this.setConnectionStatus(ConnectionStatus.CONNECTED);
    this.reconnectAttempts = 0;
    
    // Send initial connection message if needed
    this.sendMessage({
      type: 'CONNECTION_INIT',
      payload: {
        sessionId: this.sessionId,
        timestamp: new Date().toISOString()
      }
    });
  }

  /**
   * Handle WebSocket message event
   */
  private handleSocketMessage(event: MessageEvent): void {
    try {
      const data = JSON.parse(event.data);
      
      // Convert to WorkflowUpdate format
      const update: WorkflowUpdate = {
        type: data.type || WorkflowUpdateType.SYSTEM_NOTIFICATION,
        timestamp: data.timestamp || new Date().toISOString(),
        sessionId: data.sessionId || this.sessionId,
        payload: data.payload || data
      };
      
      this.notifyUpdateHandlers(update);
    } catch (error) {
      console.error('Failed to parse WebSocket message:', error);
    }
  }

  /**
   * Handle WebSocket close event
   */
  private handleSocketClose(event: CloseEvent): void {
    console.log('WebSocket connection closed:', event.code, event.reason);
    this.socket = null;
    
    if (event.code !== 1000 && this.config.autoReconnect) {
      // Abnormal closure, attempt to reconnect
      this.setConnectionStatus(ConnectionStatus.DISCONNECTED);
      this.attemptReconnect();
    } else {
      // Normal closure
      this.setConnectionStatus(ConnectionStatus.DISCONNECTED);
    }
  }

  /**
   * Handle WebSocket error event
   */
  private handleSocketError(event: Event): void {
    console.error('WebSocket error:', event);
    this.setConnectionStatus(ConnectionStatus.ERROR);
  }

  /**
   * Attempt to reconnect to the WebSocket server
   */
  private attemptReconnect(): void {
    if (this.reconnectAttempts >= (this.config.maxReconnectAttempts || 10)) {
      console.error('Maximum reconnection attempts reached');
      return;
    }

    this.reconnectAttempts++;
    
    // Calculate backoff delay
    const delay = Math.min(
      (this.config.initialReconnectDelay || 1000) * Math.pow(2, this.reconnectAttempts - 1),
      this.config.maxReconnectDelay || 30000
    );
    
    console.log(`Attempting to reconnect in ${delay}ms (attempt ${this.reconnectAttempts})`);
    
    this.reconnectTimeout = setTimeout(() => {
      this.connect();
    }, delay);
  }

  /**
   * Set the connection status and notify handlers
   */
  private setConnectionStatus(status: ConnectionStatus): void {
    if (this.currentConnectionStatus !== status) {
      this.currentConnectionStatus = status;
      this.connectionStatusHandlers.forEach(handler => handler(status));
    }
  }

  /**
   * Notify all update handlers of a new update
   */
  private notifyUpdateHandlers(update: WorkflowUpdate): void {
    this.updateHandlers.forEach(handler => {
      try {
        handler(update);
      } catch (error) {
        console.error('Error in update handler:', error);
      }
    });
  }

  /**
   * Generate a unique session ID
   */
  private generateSessionId(): string {
    return `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }
}

// Export singleton instance
const workflowUpdateService = new WorkflowUpdateService();
export default workflowUpdateService;