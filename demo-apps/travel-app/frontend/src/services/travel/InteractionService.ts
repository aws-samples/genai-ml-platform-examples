import apiClient, { InteractionResponse, ApiResponse } from '../common/apiClient';
import { WebSocketMessageType } from '../websocket/WebSocketService';
import webSocketService from '../websocket/WebSocketService';
import notificationService, { NotificationSeverity } from '../common/NotificationService';

/**
 * Interaction types
 */
export enum InteractionType {
  CLARIFICATION = 'clarification',
  APPROVAL = 'approval',
  FEEDBACK = 'feedback',
  CONFIRMATION = 'confirmation',
}

/**
 * Interaction data format
 */
export interface Interaction {
  interactionId: string;
  type: InteractionType;
  question: string;
  options?: string[];
  details?: any;
  timestamp: number;
  status: 'pending' | 'responded' | 'timeout' | 'error';
  response?: any;
}

/**
 * Interaction listener type
 */
export type InteractionListener = (interaction: Interaction) => void;

/**
 * Service for handling user interactions with the workflow
 */
class InteractionService {
  private interactions: Map<string, Interaction> = new Map();
  private listeners: Set<InteractionListener> = new Set();

  constructor() {
    // Initialize WebSocket listeners for interactions
    this.initWebSocketListeners();
  }

  /**
   * Initialize WebSocket listeners for interaction events
   */
  private initWebSocketListeners(): void {
    // Listen for interaction requests
    webSocketService.addEventListener(
      WebSocketMessageType.INTERACTION_REQUEST,
      (event) => {
        const { interactionId, type, question, options, details } = event.payload;
        
        // Create a new interaction
        const interaction: Interaction = {
          interactionId,
          type: type || InteractionType.CLARIFICATION,
          question,
          options,
          details,
          timestamp: Date.now(),
          status: 'pending',
        };
        
        // Store the interaction
        this.interactions.set(interactionId, interaction);
        
        // Notify listeners
        this.notifyListeners(interaction);
        
        // Show a notification
        notificationService.showNotification({
          title: 'Your Input Needed',
          message: question,
          severity: NotificationSeverity.WARNING,
          autoClose: false,
          data: { interactionId, type },
        });
      }
    );
  }

  /**
   * Notify all listeners of an interaction update
   * @param interaction The interaction
   */
  private notifyListeners(interaction: Interaction): void {
    this.listeners.forEach((listener) => {
      try {
        listener(interaction);
      } catch (error) {
        console.error('Error in interaction listener:', error);
      }
    });
  }

  /**
   * Get all interactions
   */
  public getInteractions(): Interaction[] {
    return Array.from(this.interactions.values());
  }

  /**
   * Get a specific interaction by ID
   * @param interactionId Interaction ID
   */
  public getInteraction(interactionId: string): Interaction | undefined {
    return this.interactions.get(interactionId);
  }

  /**
   * Get pending interactions
   */
  public getPendingInteractions(): Interaction[] {
    return this.getInteractions().filter(
      (interaction) => interaction.status === 'pending'
    );
  }

  /**
   * Submit a response to an interaction
   * @param interactionId Interaction ID
   * @param response User's response
   */
  public async submitResponse(
    interactionId: string,
    response: any
  ): Promise<ApiResponse<InteractionResponse>> {
    // Get the interaction
    const interaction = this.interactions.get(interactionId);
    if (!interaction) {
      throw new Error(`Interaction ${interactionId} not found`);
    }
    
    try {
      // Format the response according to what the backend expects
      const formattedResponse = {
        interactionId,
        response: response,
        timestamp: Date.now(),
        userId: 'user123' // This should be replaced with actual user ID if authentication is implemented
      };
      
      // Send the response to the API
      const result = await apiClient.submitInteractionResponse(interactionId, formattedResponse);
      
      // Update the interaction
      interaction.status = 'responded';
      interaction.response = response;
      
      // Notify listeners
      this.notifyListeners(interaction);
      
      // Show a success notification
      notificationService.showNotification({
        title: 'Response Submitted',
        message: 'Your response has been submitted successfully',
        severity: NotificationSeverity.SUCCESS,
      });
      
      console.log(`Interaction ${interactionId} response submitted successfully:`, result);
      
      return result;
    } catch (error) {
      // Update the interaction
      interaction.status = 'error';
      
      // Notify listeners
      this.notifyListeners(interaction);
      
      // Show an error notification
      notificationService.showNotification({
        title: 'Response Failed',
        message: 'There was an error submitting your response. Please try again.',
        severity: NotificationSeverity.ERROR,
      });
      
      console.error(`Error submitting response for interaction ${interactionId}:`, error);
      
      throw error;
    }
  }

  /**
   * Add an interaction listener
   * @param listener The listener function
   */
  public addListener(listener: InteractionListener): void {
    this.listeners.add(listener);
  }

  /**
   * Remove an interaction listener
   * @param listener The listener function to remove
   */
  public removeListener(listener: InteractionListener): boolean {
    return this.listeners.delete(listener);
  }

  /**
   * Clear all interactions
   */
  public clearInteractions(): void {
    this.interactions.clear();
  }
}

// Export as singleton
export const interactionService = new InteractionService();
export default interactionService; 