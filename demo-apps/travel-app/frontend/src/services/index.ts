// Import all service files
import apiClient from './common/apiClient';
import webSocketService from './websocket/WebSocketService';
import notificationService from './common/NotificationService';
import travelPlanService from './travel/TravelPlanService';
import interactionService from './travel/InteractionService';
import { config } from './common/config';

// Export service classes
export { default as ApiClient } from './common/apiClient';
export { default as WebSocketService } from './websocket/WebSocketService';
export { default as NotificationService } from './common/NotificationService';
export { default as TravelPlanService } from './travel/TravelPlanService';
export { default as InteractionService } from './travel/InteractionService';
export { config };

// Export singleton instances
export {
  apiClient,
  webSocketService,
  notificationService,
  travelPlanService,
  interactionService
};

// Export types and enums
export type {
  ApiResponse,
  ApiError,
  TravelPlanRequest,
  TravelPlanResponse,
  PlanStatusResponse,
  InteractionResponse,
  WebSocketMessage,
} from './common/apiClient';

export {
  WebSocketState,
  WebSocketMessageType,
} from './websocket/WebSocketService';

export type { WebSocketEventListener } from './websocket/WebSocketService';

export {
  NotificationSeverity,
} from './common/NotificationService';

export type {
  Notification,
  NotificationListener,
} from './common/NotificationService';

export type {
  TravelPlan,
  TravelItineraryItem,
} from './travel/TravelPlanService';

export {
  InteractionType,
} from './travel/InteractionService';

export type {
  Interaction,
  InteractionListener,
} from './travel/InteractionService'; 