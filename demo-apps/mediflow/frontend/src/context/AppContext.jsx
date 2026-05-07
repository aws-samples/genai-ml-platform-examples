import { createContext, useContext, useReducer, useCallback, useEffect, useRef } from 'react'
import { useActivityTracker } from '../hooks/useActivityTracker'

const AppContext = createContext(null)

export const AGENT_PANEL_MIN_WIDTH = 320
export const AGENT_PANEL_MAX_WIDTH = 640
export const AGENT_PANEL_DEFAULT_WIDTH = 380
export const AGENT_PANEL_WIDTH_STORAGE_KEY = 'mediflow:agentPanel:width'
export const AGENT_PANEL_OPEN_STORAGE_KEY = 'mediflow:agentPanel:open'

const clampPanelWidth = (n) => {
  if (typeof n !== 'number' || Number.isNaN(n)) return AGENT_PANEL_DEFAULT_WIDTH
  return Math.max(AGENT_PANEL_MIN_WIDTH, Math.min(AGENT_PANEL_MAX_WIDTH, n))
}

const readPersistedPanelWidth = () => {
  try {
    if (typeof window === 'undefined' || !window.localStorage) return AGENT_PANEL_DEFAULT_WIDTH
    const raw = window.localStorage.getItem(AGENT_PANEL_WIDTH_STORAGE_KEY)
    if (raw == null) return AGENT_PANEL_DEFAULT_WIDTH
    const parsed = parseFloat(raw)
    if (Number.isNaN(parsed)) return AGENT_PANEL_DEFAULT_WIDTH
    return clampPanelWidth(parsed)
  } catch {
    return AGENT_PANEL_DEFAULT_WIDTH
  }
}

const readPersistedPanelOpen = () => {
  try {
    if (typeof window === 'undefined' || !window.localStorage) return false
    const raw = window.localStorage.getItem(AGENT_PANEL_OPEN_STORAGE_KEY)
    if (raw == null) return false
    return raw === 'true'
  } catch {
    return false
  }
}

const initialState = {
  activeView: 'today',
  viewParams: null, // { patientId, patientName, ... } passed when cross-linking between views
  screenContext: null, // { patientId, patientName, doctorId, doctorName, tab, ... } set by active view for agent awareness
  agentPanelOpen: readPersistedPanelOpen(),
  agentPanelWidth: readPersistedPanelWidth(),
  agentPanelResizing: false, // true while the resize handle is being dragged — suppresses wrapper transition
  agentState: 'idle', // idle | listening | thinking | acting | insight_ready
  sessionId: null,
  messages: [],
  comms: [], // shared communications — synced between CommsView and PatientsView
  activityFeed: [{ id: 'init', text: 'MediFlow Assistant — Ready', active: false, icon: '◎' }],
  insightsAvailable: false,
  insightCount: 0,
  illuminateTarget: null, // { type, id, duration }
  pendingPrompt: null, // string — set by "Try It" to auto-send in AgentPanel
  uiCommand: null, // { command, patient_id, doctor_id, tab, ... } — set by agent ui_action events, consumed by views
  agentHighlight: null, // { target: 'nav'|'list_item'|'tab'|'button', id: string } — pre-highlight blink before agent acts
}

function reducer(state, action) {
  switch (action.type) {
    case 'SET_VIEW':
      return { ...state, activeView: action.payload, viewParams: null, screenContext: null }
    case 'NAVIGATE_TO':
      return { ...state, activeView: action.payload.view, viewParams: action.payload.params || null, screenContext: null }
    case 'SET_SCREEN_CONTEXT':
      return { ...state, screenContext: action.payload }
    case 'TOGGLE_AGENT_PANEL':
      return { ...state, agentPanelOpen: !state.agentPanelOpen }
    case 'SET_AGENT_PANEL_WIDTH':
      return { ...state, agentPanelWidth: clampPanelWidth(action.payload) }
    case 'SET_AGENT_PANEL_RESIZING':
      return { ...state, agentPanelResizing: !!action.payload }
    case 'SET_AGENT_STATE':
      return { ...state, agentState: action.payload }
    case 'SET_SESSION':
      return { ...state, sessionId: action.payload }
    case 'ADD_MESSAGE':
      return { ...state, messages: [...state.messages, action.payload] }
    case 'SET_COMMS':
      return { ...state, comms: action.payload }
    case 'ADD_COMM':
      return { ...state, comms: [...state.comms, action.payload] }
    case 'UPDATE_COMM':
      return { ...state, comms: state.comms.map(c => c.id === action.payload.id ? { ...c, ...action.payload } : c) }
    case 'UPDATE_LAST_MESSAGE': {
      const last = state.messages.length - 1
      if (last < 0) return state
      const prev = state.messages[last]
      const updated = {
        ...prev,
        ...action.payload,
        content: action.payload.appendContent
          ? (prev.content || '') + action.payload.appendContent
          : (action.payload.content !== undefined ? action.payload.content : prev.content),
      }
      const next = state.messages.slice()
      next[last] = updated
      return { ...state, messages: next }
    }
    case 'RESOLVE_SKILL_CARD': {
      const skillId = action.payload
      return {
        ...state,
        messages: state.messages.map(m => {
          if (!m.cards?.length) return m
          let touched = false
          const nextCards = m.cards.map(c => {
            if (c.type === 'skill_approval' && c.data?.skill_id === skillId && !c.resolved) {
              touched = true
              return { ...c, resolved: true }
            }
            return c
          })
          return touched ? { ...m, cards: nextCards } : m
        }),
      }
    }
    case 'ADD_ACTIVITY': {
      const feed = [...state.activityFeed.map(a => ({ ...a, active: false })), action.payload]
      return { ...state, activityFeed: feed.slice(-20) }
    }
    case 'SET_INSIGHTS_AVAILABLE':
      return { ...state, insightsAvailable: true, insightCount: action.payload || 0 }
    case 'ILLUMINATE':
      return { ...state, illuminateTarget: action.payload }
    case 'CLEAR_ILLUMINATE':
      return { ...state, illuminateTarget: null }
    case 'SET_PENDING_PROMPT':
      return { ...state, pendingPrompt: action.payload }
    case 'CLEAR_PENDING_PROMPT':
      return { ...state, pendingPrompt: null }
    case 'AGENT_UI_COMMAND':
      return { ...state, uiCommand: action.payload }
    case 'CLEAR_UI_COMMAND':
      return { ...state, uiCommand: null }
    case 'SET_AGENT_HIGHLIGHT':
      return { ...state, agentHighlight: action.payload }
    case 'CLEAR_AGENT_HIGHLIGHT':
      return { ...state, agentHighlight: null }
    default:
      return state
  }
}

export function AppProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, initialState)
  const trackAction = useActivityTracker(state.sessionId)

  // Auto-track view navigation
  const prevView = useRef(state.activeView)
  useEffect(() => {
    if (state.activeView !== prevView.current) {
      trackAction('navigate_view', state.activeView, 'view', state.activeView)
      prevView.current = state.activeView
    }
  }, [state.activeView, trackAction])

  // Debounced persistence of agent panel width to localStorage.
  const isFirstWidthWrite = useRef(true)
  useEffect(() => {
    // Skip the very first run (hydration) so we don't overwrite storage with the same value.
    if (isFirstWidthWrite.current) {
      isFirstWidthWrite.current = false
      return
    }
    const t = setTimeout(() => {
      try {
        if (typeof window !== 'undefined' && window.localStorage) {
          window.localStorage.setItem(AGENT_PANEL_WIDTH_STORAGE_KEY, String(state.agentPanelWidth))
        }
      } catch {
        // localStorage unavailable — silently skip
      }
    }, 250)
    return () => clearTimeout(t)
  }, [state.agentPanelWidth])

  // Persist agent panel open/closed state to localStorage on toggle.
  const isFirstOpenWrite = useRef(true)
  useEffect(() => {
    if (isFirstOpenWrite.current) {
      isFirstOpenWrite.current = false
      return
    }
    try {
      if (typeof window !== 'undefined' && window.localStorage) {
        window.localStorage.setItem(AGENT_PANEL_OPEN_STORAGE_KEY, String(state.agentPanelOpen))
      }
    } catch {
      // localStorage unavailable — silently skip
    }
  }, [state.agentPanelOpen])

  const setView = useCallback((v) => dispatch({ type: 'SET_VIEW', payload: v }), [])
  const navigateTo = useCallback((view, params) => dispatch({ type: 'NAVIGATE_TO', payload: { view, params } }), [])
  const setScreenContext = useCallback((ctx) => dispatch({ type: 'SET_SCREEN_CONTEXT', payload: ctx }), [])
  const toggleAgentPanel = useCallback(() => dispatch({ type: 'TOGGLE_AGENT_PANEL' }), [])
  const setAgentPanelWidth = useCallback((w) => dispatch({ type: 'SET_AGENT_PANEL_WIDTH', payload: w }), [])
  const setAgentPanelResizing = useCallback((v) => dispatch({ type: 'SET_AGENT_PANEL_RESIZING', payload: v }), [])
  const setAgentState = useCallback((s) => dispatch({ type: 'SET_AGENT_STATE', payload: s }), [])
  const setSession = useCallback((id) => dispatch({ type: 'SET_SESSION', payload: id }), [])
  const addMessage = useCallback((msg) => dispatch({ type: 'ADD_MESSAGE', payload: msg }), [])
  const setComms = useCallback((list) => dispatch({ type: 'SET_COMMS', payload: list }), [])
  const addComm = useCallback((msg) => dispatch({ type: 'ADD_COMM', payload: msg }), [])
  const updateComm = useCallback((update) => dispatch({ type: 'UPDATE_COMM', payload: update }), [])
  const updateLastMessage = useCallback((updates) => dispatch({ type: 'UPDATE_LAST_MESSAGE', payload: updates }), [])
  const addActivity = useCallback((a) => dispatch({ type: 'ADD_ACTIVITY', payload: a }), [])
  const setInsightsAvailable = useCallback((count) => dispatch({ type: 'SET_INSIGHTS_AVAILABLE', payload: count }), [])
  const illuminate = useCallback((target) => {
    dispatch({ type: 'ILLUMINATE', payload: target })
    setTimeout(() => dispatch({ type: 'CLEAR_ILLUMINATE' }), target.duration || 600)
  }, [])
  const sendToAgent = useCallback((prompt) => {
    dispatch({ type: 'SET_PENDING_PROMPT', payload: prompt })
    // Ensure agent panel is open
    if (!state.agentPanelOpen) dispatch({ type: 'TOGGLE_AGENT_PANEL' })
  }, [state.agentPanelOpen])
  const clearPendingPrompt = useCallback(() => dispatch({ type: 'CLEAR_PENDING_PROMPT' }), [])
  const clearUiCommand = useCallback(() => dispatch({ type: 'CLEAR_UI_COMMAND' }), [])
  const setAgentHighlight = useCallback((hl) => {
    dispatch({ type: 'SET_AGENT_HIGHLIGHT', payload: hl })
    setTimeout(() => dispatch({ type: 'CLEAR_AGENT_HIGHLIGHT' }), hl?.duration || 600)
  }, [])

  return (
    <AppContext.Provider value={{
      ...state, dispatch, trackAction,
      setView, navigateTo, setScreenContext, toggleAgentPanel, setAgentPanelWidth, setAgentPanelResizing,
      setAgentState, setSession,
      addMessage, updateLastMessage, setComms, addComm, updateComm, addActivity,
      setInsightsAvailable, illuminate, sendToAgent, clearPendingPrompt, clearUiCommand, setAgentHighlight,
    }}>
      {children}
    </AppContext.Provider>
  )
}

export const useApp = () => useContext(AppContext)
