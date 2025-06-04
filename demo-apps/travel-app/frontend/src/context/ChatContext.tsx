import React, { createContext, useContext, useReducer, ReactNode, useEffect } from 'react';
import workflowUpdateService from '../services/websocket/WorkflowUpdateService';
import { ConnectionStatus, WorkflowUpdate, WorkflowUpdateType, AgentType } from '../models/WorkflowUpdate';
import { config } from '../services/common/config';
import { dataTransformationService } from '../services/data/DataTransformationService';

// Define types
export type MessageType = {
  id: string;
  text: string;
  sender: 'user' | 'system';
  timestamp: Date;
};

export type WorkflowStage = 'idle' | 'planning' | 'routing' | 'executing' | 'updating' | 'complete';

interface AgentStatus {
  name: string;
  isActive: boolean;
  statusMessage?: string;
  progress?: number;
  lastActivity?: string;
}

interface ChatState {
  messages: MessageType[];
  isProcessing: boolean;
  workflowStage: WorkflowStage;
  results: any[];
  connectionStatus: ConnectionStatus;
  activeAgents: string[];
  agentStatuses: Record<string, AgentStatus>;
  error: string | null;
}

// Define actions
type ChatAction = 
  | { type: 'ADD_USER_MESSAGE'; payload: string }
  | { type: 'ADD_SYSTEM_MESSAGE'; payload: string }
  | { type: 'SET_PROCESSING'; payload: boolean }
  | { type: 'SET_WORKFLOW_STAGE'; payload: WorkflowStage }
  | { type: 'SET_RESULTS'; payload: any[] }
  | { type: 'SET_CONNECTION_STATUS'; payload: ConnectionStatus }
  | { type: 'SET_ACTIVE_AGENTS'; payload: string[] }
  | { type: 'ADD_ACTIVE_AGENT'; payload: string }
  | { type: 'REMOVE_ACTIVE_AGENT'; payload: string }
  | { type: 'UPDATE_AGENT_STATUS'; payload: AgentStatus }
  | { type: 'SET_ERROR'; payload: string | null }
  | { type: 'HANDLE_WORKFLOW_UPDATE'; payload: WorkflowUpdate }
  | { type: 'RESET' };

// Initial state
const initialState: ChatState = {
  messages: [],
  isProcessing: false,
  workflowStage: 'idle',
  results: [],
  connectionStatus: ConnectionStatus.DISCONNECTED,
  activeAgents: [],
  agentStatuses: {},
  error: null
};

// Create context
const ChatContext = createContext<{
  state: ChatState;
  dispatch: React.Dispatch<ChatAction>;
  connectToWorkflowUpdates: () => void;
  disconnectFromWorkflowUpdates: () => void;
} | undefined>(undefined);

// Create reducer
function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case 'ADD_USER_MESSAGE':
      return {
        ...state,
        messages: [
          ...state.messages,
          {
            id: Date.now().toString(),
            text: action.payload,
            sender: 'user',
            timestamp: new Date()
          }
        ]
      };
    case 'ADD_SYSTEM_MESSAGE':
      return {
        ...state,
        messages: [
          ...state.messages,
          {
            id: Date.now().toString(),
            text: action.payload,
            sender: 'system',
            timestamp: new Date()
          }
        ]
      };
    case 'SET_PROCESSING':
      return {
        ...state,
        isProcessing: action.payload
      };
    case 'SET_WORKFLOW_STAGE':
      return {
        ...state,
        workflowStage: action.payload
      };
    case 'SET_RESULTS':
      return {
        ...state,
        results: action.payload
      };
    case 'SET_CONNECTION_STATUS':
      return {
        ...state,
        connectionStatus: action.payload
      };
    case 'SET_ACTIVE_AGENTS':
      return {
        ...state,
        activeAgents: action.payload
      };
    case 'ADD_ACTIVE_AGENT':
      if (state.activeAgents.includes(action.payload)) {
        return state;
      }
      return {
        ...state,
        activeAgents: [...state.activeAgents, action.payload]
      };
    case 'REMOVE_ACTIVE_AGENT':
      return {
        ...state,
        activeAgents: state.activeAgents.filter(agent => agent !== action.payload)
      };
    case 'UPDATE_AGENT_STATUS':
      return {
        ...state,
        agentStatuses: {
          ...state.agentStatuses,
          [action.payload.name]: action.payload
        }
      };
    case 'SET_ERROR':
      return {
        ...state,
        error: action.payload
      };
    case 'HANDLE_WORKFLOW_UPDATE':
      return handleWorkflowUpdate(state, action.payload);
    case 'RESET':
      return initialState;
    default:
      return state;
  }
}

// Helper function to handle workflow updates
function handleWorkflowUpdate(state: ChatState, update: WorkflowUpdate): ChatState {
  switch (update.type) {
    case WorkflowUpdateType.STAGE_CHANGE:
      return {
        ...state,
        workflowStage: update.payload.currentStage
      };
    
    case WorkflowUpdateType.AGENT_ACTIVATED:
      const agentType = update.payload.agentType || update.payload.agent as AgentType;
      const agentName = update.payload.agentName || update.payload.agent || agentType;
      const statusMessage = update.payload.message || `${agentName} is working...`;
      
      // Update agent status
      const newAgentStatus: AgentStatus = {
        name: agentType,
        isActive: true,
        statusMessage: statusMessage,
        lastActivity: new Date().toLocaleTimeString()
      };
      
      return {
        ...state,
        activeAgents: state.activeAgents.includes(agentType) 
          ? state.activeAgents 
          : [...state.activeAgents, agentType],
        agentStatuses: {
          ...state.agentStatuses,
          [agentType]: newAgentStatus
        }
      };
    
    case WorkflowUpdateType.AGENT_DEACTIVATED:
      const deactivatedAgent = update.payload.agentType || update.payload.agent as AgentType;
      return {
        ...state,
        activeAgents: state.activeAgents.filter(agent => agent !== deactivatedAgent),
        agentStatuses: {
          ...state.agentStatuses,
          [deactivatedAgent]: {
            ...state.agentStatuses[deactivatedAgent],
            isActive: false,
            statusMessage: 'Completed',
            lastActivity: new Date().toLocaleTimeString()
          }
        }
      };
    
    case WorkflowUpdateType.AGENT_COMPLETE:
      // When an agent completes, remove it from the active agents list
      const completedAgent = update.payload.agentType || update.payload.agent as AgentType;
      return {
        ...state,
        activeAgents: state.activeAgents.filter(agent => agent !== completedAgent),
        agentStatuses: {
          ...state.agentStatuses,
          [completedAgent]: {
            ...state.agentStatuses[completedAgent],
            isActive: false,
            statusMessage: 'Completed',
            lastActivity: new Date().toLocaleTimeString()
          }
        }
      };
    
    case WorkflowUpdateType.PLAN_UPDATE:
      // Handle text-based plan updates from backend-strands
      if (update.payload.content && typeof update.payload.content === 'string') {
        // Use configuration-based detection instead of hardcoded heuristics
        const isBackendStrandsText = config.useBackendStrands && 
          (update.payload.complete || update.payload.content.length > 200);
        
        if (isBackendStrandsText) {
          // Transform to standardized result using data transformation service
          try {
            const standardizedResult = dataTransformationService.transformToStandardizedResult(
              update.payload.content,
              'backend-strands'
            );
            
            return {
              ...state,
              results: [standardizedResult],
              workflowStage: 'complete',
              isProcessing: false,
              messages: [
                ...state.messages,
                {
                  id: Date.now().toString(),
                  text: "Your comprehensive travel plan is ready!",
                  sender: 'system',
                  timestamp: new Date()
                }
              ]
            };
          } catch (error) {
            console.error('Error transforming plan update content:', error);
            // Fallback to adding as message
          }
        }
        
        // Add as regular message if not a complete plan
        return {
          ...state,
          messages: [
            ...state.messages,
            {
              id: Date.now().toString(),
              text: update.payload.content,
              sender: 'system',
              timestamp: new Date()
            }
          ]
        };
      }
      
      return state;
    
  case WorkflowUpdateType.SYSTEM_NOTIFICATION:
      // Check if this is a completion notification
      if (update.payload.data?.status === "COMPLETED") {
        return {
          ...state,
          isProcessing: false,
          messages: [
            ...state.messages,
            {
              id: Date.now().toString(),
              text: update.payload.message || "Your travel plan is complete!",
              sender: 'system',
              timestamp: new Date()
            }
          ]
        };
      }
      
      // Normal notification
      return {
        ...state,
        messages: [
          ...state.messages,
          {
            id: Date.now().toString(),
            text: update.payload.message || "System notification",
            sender: 'system',
            timestamp: new Date()
          }
        ]
      };
    
    case WorkflowUpdateType.AGENT_ERROR:
    case WorkflowUpdateType.SYSTEM_ERROR:
      // Add the error message to the chat
      return {
        ...state,
        messages: [
          ...state.messages,
          {
            id: Date.now().toString(),
            text: `Error: ${update.payload.errorMessage}`,
            sender: 'system',
            timestamp: new Date()
          }
        ],
        error: update.payload.errorMessage
      };
    
    case WorkflowUpdateType.CONNECTION_STATUS:
      return {
        ...state,
        connectionStatus: update.payload.status
      };
    
    case WorkflowUpdateType.RESULTS_UPDATED:
      // Get current results
      const currentResults = state.results || [];
      
      // Get new results
      const newResults = update.payload.results || [];
      
      // Check if we received a fade-out instruction
      if (update.payload.fadeOutResults) {
        // Mark existing results for fade-out animation
        const fadeOutResults = currentResults.map(result => ({
          ...result,
          fadeOut: true // Add a flag to indicate this result should fade out
        }));
        
        return {
          ...state,
          results: fadeOutResults
        };
      }
      
      // Check if we received a clear previous instruction
      if (update.payload.clearPrevious) {
        // Clear all existing results
        return {
          ...state,
          results: []
        };
      }
      
      // Check if we received a markdown result (final travel plan)
      const containsMarkdown = newResults.some(result => result.type === 'markdown');
      
      // Check if we received a final itinerary (any itinerary result)
      const containsItinerary = newResults.some(result => result.type === 'itinerary');
      
      if (containsMarkdown) {
        // Only include the markdown result and remove all previous results
        const markdownResults = newResults.filter(result => result.type === 'markdown');
        return {
          ...state,
          results: markdownResults,
          workflowStage: 'complete' // Mark as complete when we get the final plan
        };
      } else if (containsItinerary) {
        // Only include the itinerary and remove all previous individual results
        // This causes an immediate clear effect before showing just the itinerary
        const itineraryResults = newResults.filter(result => result.type === 'itinerary');
        return {
          ...state,
          results: itineraryResults
        };
      } else {
        // Otherwise combine results, but prevent duplicates by checking IDs
        const combinedResults = [...currentResults];
        
        // Process each new result
        newResults.forEach(newResult => {
          // Check if this result already exists by ID
          const existingIndex = combinedResults.findIndex(r => r.id === newResult.id);
          
          if (existingIndex >= 0) {
            // Replace the existing result with the updated one
            combinedResults[existingIndex] = newResult;
          } else {
            // Add the new result
            combinedResults.push(newResult);
          }
        });
        
        return {
          ...state,
          results: combinedResults
        };
      }
    
    default:
      return state;
  }
}

// Create provider
export const ChatProvider: React.FC<{children: ReactNode}> = ({ children }) => {
  const [state, dispatch] = useReducer(chatReducer, initialState);
  
  
  // Setup workflow update handlers
  useEffect(() => {
    const unsubscribe = workflowUpdateService.subscribeToUpdates((update) => {
      dispatch({ type: 'HANDLE_WORKFLOW_UPDATE', payload: update });
    });
    
    const unsubscribeConnectionStatus = workflowUpdateService.subscribeToConnectionStatus((status) => {
      dispatch({ type: 'SET_CONNECTION_STATUS', payload: status });
    });
    
    // Don't auto-connect when component mounts - wait for user interaction
    
    // Cleanup on unmount
    return () => {
      unsubscribe();
      unsubscribeConnectionStatus();
      workflowUpdateService.disconnect();
    };
  }, []);
  
  const connectToWorkflowUpdates = () => {
    workflowUpdateService.connect();
  };
  
  const disconnectFromWorkflowUpdates = () => {
    workflowUpdateService.disconnect();
  };
  
  return (
    <ChatContext.Provider value={{ 
      state, 
      dispatch,
      connectToWorkflowUpdates,
      disconnectFromWorkflowUpdates
    }}>
      {children}
    </ChatContext.Provider>
  );
};

// Create custom hook
export const useChatContext = () => {
  const context = useContext(ChatContext);
  if (context === undefined) {
    throw new Error('useChatContext must be used within a ChatProvider');
  }
  return context;
};

// Helper functions
export const sendUserMessage = (dispatch: React.Dispatch<ChatAction>, message: string) => {
  dispatch({ type: 'ADD_USER_MESSAGE', payload: message });
};

export const sendSystemMessage = (dispatch: React.Dispatch<ChatAction>, message: string) => {
  dispatch({ type: 'ADD_SYSTEM_MESSAGE', payload: message });
};

export const setProcessing = (dispatch: React.Dispatch<ChatAction>, isProcessing: boolean) => {
  dispatch({ type: 'SET_PROCESSING', payload: isProcessing });
};

export const setWorkflowStage = (dispatch: React.Dispatch<ChatAction>, stage: WorkflowStage) => {
  dispatch({ type: 'SET_WORKFLOW_STAGE', payload: stage });
};

export const setResults = (dispatch: React.Dispatch<ChatAction>, results: any[]) => {
  dispatch({ type: 'SET_RESULTS', payload: results });
};

export const setError = (dispatch: React.Dispatch<ChatAction>, error: string | null) => {
  dispatch({ type: 'SET_ERROR', payload: error });
}; 