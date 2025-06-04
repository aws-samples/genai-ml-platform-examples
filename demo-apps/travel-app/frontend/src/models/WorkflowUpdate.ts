import { WorkflowStage } from '../context/ChatContext';

/**
 * Types of workflow updates that can be received from the backend
 */
export enum WorkflowUpdateType {
  // Workflow stage updates
  STAGE_CHANGE = 'STAGE_CHANGE',
  
  // Agent activity updates
  AGENT_ACTIVATED = 'AGENT_ACTIVATED',
  AGENT_DEACTIVATED = 'AGENT_DEACTIVATED',
  AGENT_PROCESSING = 'AGENT_PROCESSING',
  AGENT_COMPLETE = 'AGENT_COMPLETE',
  AGENT_ERROR = 'AGENT_ERROR',
  
  // System status updates
  CONNECTION_STATUS = 'CONNECTION_STATUS',
  SYSTEM_ERROR = 'SYSTEM_ERROR',
  SYSTEM_NOTIFICATION = 'SYSTEM_NOTIFICATION',
  
  // Plan updates (from backend-strands)
  PLAN_UPDATE = 'PLAN_UPDATE',
  
  // Results updates
  RESULTS_UPDATED = 'RESULTS_UPDATED'
}

/**
 * Agent types that correspond to the specialists in the workflow
 */
export type AgentType = 'flight' | 'hotel' | 'dining' | 'transportation' | 
  'attraction' | 'destination' | 'activity' | 'budget' | 'orchestrator' |
  'weather' | 'pricing' | 'scheduling';

/**
 * Connection status for the WebSocket connection
 */
export enum ConnectionStatus {
  CONNECTED = 'CONNECTED',
  DISCONNECTED = 'DISCONNECTED',
  CONNECTING = 'CONNECTING',
  ERROR = 'ERROR'
}

/**
 * Base interface for all workflow updates
 */
export interface BaseWorkflowUpdate {
  type: WorkflowUpdateType;
  timestamp: string;
  sessionId: string;
}

/**
 * Update for when the workflow stage changes
 */
export interface StageChangeUpdate extends BaseWorkflowUpdate {
  type: WorkflowUpdateType.STAGE_CHANGE;
  payload: {
    previousStage?: WorkflowStage;
    currentStage: WorkflowStage;
  };
}

/**
 * Update for when an agent is activated
 */
export interface AgentActivatedUpdate extends BaseWorkflowUpdate {
  type: WorkflowUpdateType.AGENT_ACTIVATED;
  payload: {
    agentType?: AgentType;
    agentName?: string;
    agent?: string; // Backend sends this
    message?: string; // Backend sends this
  };
}

/**
 * Update for when an agent is deactivated
 */
export interface AgentDeactivatedUpdate extends BaseWorkflowUpdate {
  type: WorkflowUpdateType.AGENT_DEACTIVATED;
  payload: {
    agentType?: AgentType;
    agentName?: string;
    agent?: string; // Backend sends this
  };
}

/**
 * Update for when an agent is processing
 */
export interface AgentProcessingUpdate extends BaseWorkflowUpdate {
  type: WorkflowUpdateType.AGENT_PROCESSING;
  payload: {
    agentType: AgentType;
    agentName: string;
    operationDescription: string;
    progressPercent?: number;
  };
}

/**
 * Update for when an agent has completed its task
 */
export interface AgentCompleteUpdate extends BaseWorkflowUpdate {
  type: WorkflowUpdateType.AGENT_COMPLETE;
  payload: {
    agentType?: AgentType;
    agentName?: string;
    agent?: string; // Backend sends this
    summary?: string;
    response_preview?: string; // Backend sends this
  };
}

/**
 * Update for when an agent encounters an error
 */
export interface AgentErrorUpdate extends BaseWorkflowUpdate {
  type: WorkflowUpdateType.AGENT_ERROR;
  payload: {
    agentType: AgentType;
    agentName: string;
    errorMessage: string;
    errorCode?: string;
  };
}

/**
 * Update for the connection status
 */
export interface ConnectionStatusUpdate extends BaseWorkflowUpdate {
  type: WorkflowUpdateType.CONNECTION_STATUS;
  payload: {
    status: ConnectionStatus;
    message?: string;
  };
}

/**
 * Update for system errors
 */
export interface SystemErrorUpdate extends BaseWorkflowUpdate {
  type: WorkflowUpdateType.SYSTEM_ERROR;
  payload: {
    errorMessage: string;
    errorCode?: string;
    severity: 'low' | 'medium' | 'high' | 'critical';
  };
}

/**
 * Update for when the results are updated
 */
export interface ResultsUpdatedUpdate extends BaseWorkflowUpdate {
  type: WorkflowUpdateType.RESULTS_UPDATED;
  payload: {
    results: any[];
    clearPrevious?: boolean;
    fadeOutResults?: boolean;
  };
}

/**
 * Update for plan content (from backend-strands)
 */
export interface PlanUpdate extends BaseWorkflowUpdate {
  type: WorkflowUpdateType.PLAN_UPDATE;
  payload: {
    content: string;
    agentId?: string;
    streaming?: boolean;
    complete?: boolean;
  };
}

/**
 * Update for system notifications
 */
export interface SystemNotificationUpdate extends BaseWorkflowUpdate {
  type: WorkflowUpdateType.SYSTEM_NOTIFICATION;
  payload: {
    message: string;
    data?: any;
    severity?: 'info' | 'warning' | 'error';
  };
}

/**
 * Union type of all possible workflow updates
 */
export type WorkflowUpdate = 
  | StageChangeUpdate
  | AgentActivatedUpdate
  | AgentDeactivatedUpdate
  | AgentProcessingUpdate
  | AgentCompleteUpdate
  | AgentErrorUpdate
  | ConnectionStatusUpdate
  | SystemErrorUpdate
  | PlanUpdate
  | ResultsUpdatedUpdate
  | SystemNotificationUpdate; 