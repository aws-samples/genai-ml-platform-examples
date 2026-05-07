import { useState, useRef, useEffect, memo, useCallback } from 'react'
import { useApp } from '../../context/AppContext'
import { api } from '../../api/client'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  Minus, X, Send, Paperclip, Bot,
} from 'lucide-react'
import PatientCard from '../chat/PatientCard'
import AvailabilityGrid from '../chat/AvailabilityGrid'
import ActionConfirmation from '../chat/ActionConfirmation'
import InvoiceCard from '../chat/InvoiceCard'
import InsightMessage from '../chat/InsightMessage'
import PatternCard from '../chat/PatternCard'
import ImpactCard from '../chat/ImpactCard'
import SkillApprovalCard from '../chat/SkillApprovalCard'
import RescheduleCascadeCard from '../chat/RescheduleCascadeCard'

const CHARS_PER_TICK = 2
const TICK_MS = 30

function StreamingText({ content, streaming }) {
  const [cursor, setCursor] = useState(content.length)
  const targetRef = useRef(content.length)

  targetRef.current = content.length

  useEffect(() => {
    const id = setInterval(() => {
      setCursor(prev => {
        const target = targetRef.current
        if (prev >= target) return prev
        return Math.min(prev + CHARS_PER_TICK, target)
      })
    }, TICK_MS)
    return () => clearInterval(id)
  }, [])

  const finished = !streaming && cursor >= content.length

  if (finished) {
    return <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
  }

  const revealed = content.slice(0, cursor)
  return (
    <div className="streaming-cursor">
      <p>{revealed}</p>
    </div>
  )
}

const ChatMessage = memo(function ChatMessage({ msg, index, onApproveSkill, onCancelSkill, onCascadeComplete }) {
  const isUser = msg.role === 'user'

  return (
    <div
      className={`flex ${isUser ? 'justify-end' : 'justify-start'} ${
        isUser ? 'animate-[count-up-fade_300ms_ease-out]' : ''
      }`}
      style={{ animationDelay: `${index * 50}ms` }}
    >
      {!isUser && (
        <div className="w-7 h-7 rounded-lg bg-mint/10 flex items-center justify-center mr-2 mt-0.5 flex-shrink-0">
          <Bot size={14} className="text-mint" />
        </div>
      )}
      <div
        className={`max-w-[85%] ${
          isUser
            ? 'bg-ash rounded-2xl rounded-br-md px-4 py-2.5'
            : ''
        }`}
      >
        {isUser ? (
          <p className="text-sm leading-relaxed text-primary">{msg.content}</p>
        ) : (
          <div className="text-sm leading-relaxed text-secondary prose-agent">
            <StreamingText content={msg.content || ''} streaming={!!msg.streaming} />
          </div>
        )}

        {/* Rich cards embedded in agent messages */}
        {msg.cards?.map((card, ci) => (
          <div key={ci} className="mt-3" style={{ animationDelay: `${ci * 150}ms` }}>
            <RichCard
              card={card}
              onApproveSkill={onApproveSkill}
              onCancelSkill={onCancelSkill}
              onCascadeComplete={onCascadeComplete}
            />
          </div>
        ))}
      </div>
    </div>
  )
})

function RichCard({ card, onApproveSkill, onCancelSkill, onCascadeComplete }) {
  switch (card.type) {
    case 'patient': return <PatientCard data={card.data} />
    case 'availability': return <AvailabilityGrid data={card.data} />
    case 'confirmation': return <ActionConfirmation data={card.data} />
    case 'invoice': return <InvoiceCard data={card.data} />
    case 'insight': return <InsightMessage data={card.data} />
    case 'pattern': return <PatternCard data={card.data} />
    case 'impact': return <ImpactCard data={card.data} />
    case 'skill_approval':
      return (
        <SkillApprovalCard
          data={card.data}
          disabled={card.resolved}
          onApprove={onApproveSkill}
          onCancel={onCancelSkill}
        />
      )
    case 'reschedule_cascade':
      return <RescheduleCascadeCard data={card.data} onComplete={onCascadeComplete} />
    default: return null
  }
}

function ThinkingIndicator() {
  return (
    <div className="flex items-center gap-2 text-secondary text-sm animate-[count-up-fade_200ms_ease-out]">
      <div className="w-7 h-7 rounded-lg bg-mint/10 flex items-center justify-center flex-shrink-0">
        <Bot size={14} className="text-mint" />
      </div>
      <div className="flex gap-1">
        <span className="w-1.5 h-1.5 rounded-full bg-mint/60 animate-bounce" style={{ animationDelay: '0ms' }} />
        <span className="w-1.5 h-1.5 rounded-full bg-mint/60 animate-bounce" style={{ animationDelay: '150ms' }} />
        <span className="w-1.5 h-1.5 rounded-full bg-mint/60 animate-bounce" style={{ animationDelay: '300ms' }} />
      </div>
    </div>
  )
}

export default function AgentPanel() {
  const {
    agentState, setAgentState, messages, addMessage, updateLastMessage,
    sessionId, setSession, addActivity, setInsightsAvailable, illuminate,
    pendingPrompt, clearPendingPrompt, toggleAgentPanel, agentPanelOpen,
    activeView, viewParams, screenContext,
    navigateTo, dispatch, addComm, updateComm, setAgentHighlight,
  } = useApp()

  const [input, setInput] = useState('')
  const [isThinking, setIsThinking] = useState(false)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)
  const sendRef = useRef(null)
  const hasScrolledOnceRef = useRef(false)

  // Cascade sequencing: hold post-animation text until the card signals completion
  const cascadePendingRef = useRef(null) // { text, resolve } when waiting

  useEffect(() => {
    // Never scroll while the panel is closed — the panel is always mounted but translated
    // off-screen, so scrollIntoView would drag ancestor scroll containers sideways.
    if (!agentPanelOpen) return

    // First scroll after the panel opens is deferred past the 300ms open animation so the
    // list doesn't jump while the wrapper is still translating in.
    if (!hasScrolledOnceRef.current) {
      hasScrolledOnceRef.current = true
      const t = setTimeout(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
      }, 320)
      return () => clearTimeout(t)
    }
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isThinking, agentPanelOpen])

  // Auto-send pendingPrompt from "Try It" buttons
  useEffect(() => {
    if (pendingPrompt && !isThinking) {
      clearPendingPrompt()
      // Small delay so panel is visible before sending
      setTimeout(() => {
        sendRef.current?.(pendingPrompt)
      }, 200)
    }
  }, [pendingPrompt, isThinking, clearPendingPrompt])

  const handleSend = () => {
    const text = input.trim()
    if (!text || isThinking) return
    setInput('')
    doSend(text)
  }

  const doSend = (text) => {
    if (!text || isThinking) return

    addMessage({ role: 'user', content: text })
    setIsThinking(true)
    setAgentState('thinking')
    let streamingStarted = false

    addActivity({ id: Date.now().toString(), text: `Processing: "${text.slice(0, 40)}..."`, active: true, icon: '◎' })

    // Build conversation history from existing messages (text-only, last 20 turns)
    const history = messages
      .filter(m => m.role === 'user' || m.role === 'assistant')
      .map(m => ({ role: m.role, content: m.content || '' }))
      .slice(-20)

    // Build view context from current screen state (merge screenContext from active view)
    const viewContext = { view: activeView, params: { ...(viewParams || {}), ...(screenContext || {}) } }

    api.chatSSE(text, sessionId, (event, data) => {
      if (event === 'tool_call') {
        const toolName = data.tool || 'unknown'
        addActivity({
          id: `tc-${Date.now()}`,
          text: `${toolName.replace(/_/g, ' ')}`,
          active: true,
          icon: '⚙',
        })
        setAgentState('acting')
        if (streamingStarted) updateLastMessage({ streaming: false })
        streamingStarted = false
      }

      if (event === 'ui_action') {
        const action = data.ui_action
        if (action === 'pre_highlight') {
          // Blink the target element before the agent acts on it
          setAgentHighlight({ target: data.target, id: data.id, duration: data.duration || 600 })
          return // no activity bar entry for pre_highlight
        }

        if (action === 'skill_approval') {
          // Surface the approval request as a rich card in chat
          addMessage({
            role: 'assistant',
            content: `Ready to run **${data.name}**. Review the plan before I act.`,
            cards: [{ type: 'skill_approval', data, resolved: false }],
          })
          addActivity({
            id: `stage-${Date.now()}`,
            text: `Staged: ${data.name}`,
            active: true,
            icon: '◉',
          })
          streamingStarted = false
          return
        }

        if (action === 'reschedule_cascade') {
          const doctorName = data.doctor_name
            || (data.entries && data.entries[0]?.original_doctor_name)
            || 'the doctor'
          addMessage({
            role: 'assistant',
            content: `Rescheduling ${data.total_affected} patients affected by ${doctorName}'s absence…`,
            cards: [{ type: 'reschedule_cascade', data }],
          })
          addActivity({
            id: `reschedule-${Date.now()}`,
            text: `Rescheduling ${data.total_affected} patients`,
            active: true,
            icon: '↻',
          })
          streamingStarted = false
          // Hold subsequent text until cascade animation calls onCascadeComplete
          cascadePendingRef.current = { text: '' }
          return
        }

        const label = action === 'navigate' ? `→ ${data.view}`
          : action === 'select_patient' ? `→ ${data.patient_name || data.patient_id}`
          : action === 'select_doctor' ? `→ ${data.doctor_name || data.doctor_id}`
          : action === 'open_booking' ? 'Opening booking...'
          : action === 'set_patient_tab' ? `→ ${data.tab} tab`
          : action === 'add_message' ? `Sent to ${data.patient_name || 'patient'}`
          : action === 'illuminate' ? '✦'
          : action

        addActivity({
          id: `ui-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
          text: label,
          active: true,
          icon: action === 'add_message' ? '✉' : '↗',
        })

        if (action === 'navigate') {
          navigateTo(data.view, data.params || null)
        } else if (action === 'illuminate') {
          illuminate({ type: data.type, id: data.id, duration: data.duration || 800 })
        } else if (action === 'add_message') {
          if (data.message) addComm(data.message)
        } else if (action === 'update_message') {
          if (data.message_id) updateComm({ id: data.message_id, ...data.updates })
        } else {
          // select_patient, select_doctor, open_booking, set_patient_tab
          dispatch({ type: 'AGENT_UI_COMMAND', payload: { command: action, ...data } })
        }
      }

      if (event === 'text_delta') {
        if (!sessionId && data.session_id) setSession(data.session_id)
        // If cascade animation is playing, accumulate text for onCascadeComplete
        if (cascadePendingRef.current) {
          cascadePendingRef.current.text += data.delta
          return
        }
        if (!streamingStarted) {
          addMessage({ role: 'assistant', content: data.delta, streaming: true })
          streamingStarted = true
        } else {
          updateLastMessage({ appendContent: data.delta })
        }
      }

      if (event === 'message') {
        if (!sessionId && data.session_id) setSession(data.session_id)

        // Clear streaming flag on the last message
        if (streamingStarted) {
          updateLastMessage({ streaming: false })
        }

        // If cascade is holding text, don't add the full message (onCascadeComplete handles it)
        if (!streamingStarted && !cascadePendingRef.current) {
          const parsed = parseAgentResponse(data.content, data.tool_calls)
          addMessage({ role: 'assistant', content: parsed.text, cards: parsed.cards })
        }
        // Otherwise, streamed text_delta messages are already in place — don't overwrite

        addActivity({
          id: `done-${Date.now()}`,
          text: 'Response delivered',
          active: false,
          icon: '✓',
        })
      }

      if (event === 'done') {
        setIsThinking(false)
        setAgentState('idle')
      }

      if (event === 'error') {
        addMessage({ role: 'assistant', content: `Something went wrong. ${data.error || ''}` })
        setIsThinking(false)
        setAgentState('idle')
      }
    }, { history, viewContext })
  }

  // Keep sendRef current for useEffect auto-send
  sendRef.current = doSend

  const onCascadeComplete = () => {
    const pending = cascadePendingRef.current
    if (pending?.text) {
      addMessage({ role: 'assistant', content: pending.text })
    }
    cascadePendingRef.current = null
  }

  const resolveSkillCard = (skillId) => {
    dispatch({ type: 'RESOLVE_SKILL_CARD', payload: skillId })
  }

  const handleApproveSkill = (skillId, payload) => {
    addActivity({
      id: `approve-${skillId}-${Date.now()}`,
      text: `Running: ${payload?.name || skillId}`,
      active: true,
      icon: '◎',
    })
    resolveSkillCard(skillId)

    api.runSkill(skillId, (evt, data) => {
      if (evt === 'progress') {
        addActivity({
          id: `run-${skillId}-${data.executed}-${Date.now()}`,
          text: data.entity_name || `Item ${data.executed}/${data.total}`,
          active: true,
          icon: '✦',
        })
      } else if (evt === 'complete') {
        addMessage({
          role: 'assistant',
          content: `Done. Ran ${payload?.name || 'the skill'} across ${data.executed || data.total || 'all'} items.`,
        })
        addActivity({
          id: `done-${skillId}-${Date.now()}`,
          text: `Completed: ${payload?.name || skillId}`,
          active: false,
          icon: '✓',
        })
      } else if (evt === 'error') {
        addMessage({
          role: 'assistant',
          content: `Couldn't run that skill. ${data.error || ''}`.trim(),
        })
      }
    })
  }

  const handleCancelSkill = (skillId, payload) => {
    resolveSkillCard(skillId)
    addMessage({
      role: 'assistant',
      content: `Okay — not running ${payload?.name || 'that skill'}.`,
    })
    addActivity({
      id: `cancel-${skillId}-${Date.now()}`,
      text: `Cancelled: ${payload?.name || skillId}`,
      active: false,
      icon: '×',
    })
  }

  const borderClass = {
    idle: 'border-border-subtle',
    listening: 'border-border-glow',
    thinking: 'border-border-active',
    acting: 'border-border-active',
    insight_ready: 'border-border-violet',
  }[agentState] || 'border-border-subtle'

  return (
    <div
      className={`w-full h-full bg-slate flex flex-col border-l ${borderClass} transition-colors duration-200`}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border-subtle">
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${
            agentState === 'idle'
              ? 'bg-tertiary'
              : 'bg-mint animate-pulse shadow-[0_0_6px_rgba(0,210,229,0.5)]'
          }`} />
          <div>
            <span className="text-primary text-sm font-medium tracking-tight">MediFlow Assistant</span>
            <span className="text-tertiary text-xs ml-2">
              {agentState === 'thinking' ? 'Thinking...' : agentState === 'acting' ? 'Working...' : agentState === 'idle' ? '' : 'Active'}
            </span>
          </div>
        </div>
        <div className="flex gap-1">
          <button onClick={toggleAgentPanel} className="w-7 h-7 rounded-lg flex items-center justify-center text-tertiary hover:text-secondary hover:bg-white/[0.04] transition-all duration-200 active:scale-95">
            <Minus size={14} />
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center py-12">
            <div className="w-12 h-12 rounded-2xl bg-mint/10 flex items-center justify-center mx-auto mb-3">
              <Bot size={24} className="text-mint" />
            </div>
            <p className="text-secondary text-sm">How can I help today?</p>
            <p className="text-tertiary text-xs mt-1">Ask about patients, appointments, invoices...</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <ChatMessage
            key={i}
            msg={msg}
            index={i}
            onApproveSkill={handleApproveSkill}
            onCancelSkill={handleCancelSkill}
            onCascadeComplete={onCascadeComplete}
          />
        ))}
        {isThinking && <ThinkingIndicator />}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="px-3 pb-3">
        <div className={`flex items-center gap-2 bg-ash rounded-full px-4 py-2.5 border transition-colors duration-200
          ${input ? 'border-border-active' : 'border-border-subtle'}
        `}>
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="Message MediFlow..."
            className="flex-1 bg-transparent text-sm text-primary placeholder:text-tertiary outline-none"
            disabled={isThinking}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isThinking}
            className={`w-7 h-7 rounded-full flex items-center justify-center transition-all duration-200 active:scale-95
              ${input.trim() && !isThinking
                ? 'bg-mint text-inverse hover:bg-mint/90'
                : 'bg-white/5 text-tertiary'
              }`}
          >
            <Send size={14} />
          </button>
        </div>
      </div>
    </div>
  )
}

// Parse agent text for embedded data references and create rich cards
function parseAgentResponse(text, toolCalls = []) {
  const cards = []

  // Check tool calls for card-worthy data
  for (const tc of toolCalls) {
    const tool = typeof tc === 'string' ? tc : tc.tool
    const params = typeof tc === 'object' ? tc.params || {} : {}

    if (tool === 'search_patient' || tool === 'get_patient') {
      // Will be resolved when we get real data
    }
  }

  return { text: text || '', cards }
}
