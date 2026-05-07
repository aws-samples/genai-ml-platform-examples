import { useState, useEffect, useRef } from 'react'
import { api } from '../../api/client'
import { useApp } from '../../context/AppContext'
import { Bot, Check, Clock, Send as SendIcon, ChevronRight } from 'lucide-react'

const statusConfig = {
  draft: { text: 'Draft', color: 'text-tertiary bg-white/5' },
  sending: { text: 'Sending...', color: 'text-mint bg-mint/10 shimmer' },
  sent: { text: 'Sent', color: 'text-secondary bg-white/5' },
  delivered: { text: 'Delivered', color: 'text-mint bg-mint/10' },
  read: { text: 'Read', color: 'text-emerald bg-emerald/10' },
  responded: { text: 'Confirmed', color: 'text-emerald bg-emerald/10 font-semibold' },
  failed: { text: 'Failed', color: 'text-coral bg-coral/10' },
}

function StatusBadge({ status }) {
  const config = statusConfig[status] || statusConfig.sent
  return (
    <span className={`inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full ${config.color}`}>
      {status === 'delivered' || status === 'responded' ? <Check size={10} /> : status === 'sending' ? <Clock size={10} /> : null}
      {config.text}
    </span>
  )
}

function ChatBubble({ message, isOutbound }) {
  const isAgent = message.triggered_by === 'agent' || message.triggered_by === 'skill'

  return (
    <div className={`flex ${isOutbound ? 'justify-end' : 'justify-start'} mb-3`}
      style={message.cascade ? { animation: `cascade-in 300ms ease-out ${(message.cascadeIndex || 0) * 100}ms both` } : {}}>
      <div className={`max-w-[75%] ${isOutbound ? 'items-end' : 'items-start'} flex flex-col`}>
        <div className={`px-4 py-3 text-sm leading-relaxed
          ${isOutbound
            ? `bg-graphite rounded-xl rounded-br-sm ${isAgent ? 'border-l-2 border-l-mint' : ''}`
            : 'bg-slate rounded-xl rounded-bl-sm'
          }`}
        >
          <p className="text-primary whitespace-pre-wrap">{message.content}</p>
        </div>
        <div className={`flex items-center gap-2 mt-1 ${isOutbound ? 'flex-row-reverse' : ''}`}>
          {isAgent && <Bot size={10} className="text-mint" />}
          <span className="text-tertiary text-[10px]">
            {isOutbound ? (isAgent ? 'MediFlow AI' : 'Clinic') : message.patient_name}
          </span>
          <span className="text-tertiary/50 text-[10px]">{message.sent_time}</span>
          {isOutbound && message.status && <StatusBadge status={message.status} />}
        </div>
      </div>
    </div>
  )
}

function ThreadItem({ thread, isActive, onClick }) {
  const latest = thread.messages[thread.messages.length - 1]
  const isAgent = latest?.triggered_by === 'agent' || latest?.triggered_by === 'workflow'
  const hasUnread = thread.messages.some(m => m.is_new)
  const isEmpty = thread.messages.length === 0

  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-4 py-3 border-b border-border-subtle/50 transition-all
        ${isActive ? 'bg-mint/5 border-l-2 border-l-mint' : 'hover:bg-white/[0.02] border-l-2 border-l-transparent'}
        ${hasUnread ? 'border-l-mint/30' : ''}
      `}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          {isAgent && <Bot size={12} className="text-mint flex-shrink-0" />}
          <span className={`text-sm truncate ${hasUnread ? 'text-primary font-semibold' : 'text-primary font-medium'}`}>
            {thread.patientName}
          </span>
        </div>
        {!isEmpty && <span className="text-tertiary text-[10px] flex-shrink-0">{latest?.sent_time}</span>}
      </div>
      {isEmpty ? (
        <p className="text-tertiary/70 text-xs mt-0.5 italic">New conversation</p>
      ) : (
        <>
          <p className="text-secondary text-xs mt-0.5 truncate">{latest?.content?.slice(0, 60)}...</p>
          <div className="flex items-center justify-between mt-1.5">
            <StatusBadge status={latest?.status || 'sent'} />
            <span className="text-tertiary/50 text-[10px]">{thread.messages.length} msg{thread.messages.length !== 1 ? 's' : ''}</span>
          </div>
        </>
      )}
    </button>
  )
}

export default function CommsView() {
  const { viewParams, comms, setComms, addComm, updateComm, trackAction, uiCommand, clearUiCommand, navigateTo } = useApp()
  const [activeThread, setActiveThread] = useState(null)
  const [composeText, setComposeText] = useState('')
  const [patients, setPatients] = useState([])
  const chatEndRef = useRef(null)
  const composeRef = useRef(null)

  // Load comms into shared state on mount (only if empty)
  useEffect(() => {
    if (comms.length > 0) return
    api.comms().then(d => setComms(d.communications || d)).catch(() => setComms(getDemoComms()))
  }, [])

  // Load patient list (for resolving patientId → patient_name)
  useEffect(() => {
    api.patients().then(d => setPatients(d.patients || d)).catch(() => setPatients([]))
  }, [])

  // Resolve patientId → patient_name via the loaded patient list
  const resolveNameFromId = (pid) => {
    if (!pid) return null
    const p = patients.find(x => x.id === pid)
    if (!p) return null
    return `${p.first_name || ''} ${p.last_name || ''}`.trim()
  }

  // Find the current thread's patient_id by looking up the patient list by name
  const findPatientIdByName = (name) => {
    if (!name) return null
    const p = patients.find(x => `${x.first_name || ''} ${x.last_name || ''}`.trim() === name)
    return p?.id || null
  }

  // Group messages into threads by patient
  const list = comms.length ? comms : getDemoComms()
  const baseThreads = groupByThread(list)

  // Synthesize an empty thread for an incoming patient who has no existing comms.
  // Ephemeral: disappears once a real message is sent (which feeds into comms state).
  const requestedName = resolveNameFromId(viewParams?.patientId) || viewParams?.patientName
  const requestedIsKnownPatient =
    !!viewParams?.patientId ||
    (!!requestedName && patients.some(x => `${x.first_name || ''} ${x.last_name || ''}`.trim() === requestedName))
  const needsSynthetic =
    requestedName &&
    requestedIsKnownPatient &&
    !baseThreads.some(t => t.patientName === requestedName)
  const threads = needsSynthetic
    ? [{ patientName: requestedName, messages: [], synthetic: true }, ...baseThreads]
    : baseThreads

  // Auto-select thread from viewParams (cross-link from Patients)
  // Prefer patientId; fall back to patientName as a display hint.
  useEffect(() => {
    const name = resolveNameFromId(viewParams?.patientId) || viewParams?.patientName
    if (!name) return
    const match = threads.find(t => t.patientName === name)
    if (match) {
      setActiveThread(match.patientName)
      if (viewParams?.compose) {
        setTimeout(() => composeRef.current?.focus(), 100)
      }
    }
  }, [viewParams?.patientId, viewParams?.patientName, viewParams?.compose, threads.length, patients.length])

  // Handle agent UI commands
  useEffect(() => {
    if (!uiCommand) return
    if (uiCommand.command === 'select_patient') {
      const name = uiCommand.patient_name
      if (name) {
        const match = threads.find(t => t.patientName === name)
        if (match) setActiveThread(match.patientName)
      }
      clearUiCommand()
    }
  }, [uiCommand, clearUiCommand, threads])

  const currentThread = threads.find(t => t.patientName === activeThread)

  // Scroll to bottom when thread changes
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [activeThread, currentThread?.messages.length])

  const handleSend = () => {
    if (!composeText.trim() || !currentThread) return
    trackAction('send_message', currentThread.patientName, 'patient', null)
    const newMsg = {
      id: `c-new-${Date.now()}`,
      patient_name: currentThread.patientName,
      content: composeText.trim(),
      sent_time: 'Just now',
      status: 'sending',
      triggered_by: 'manual',
      direction: 'outbound',
    }
    addComm(newMsg)
    setComposeText('')
    // Simulate delivery
    setTimeout(() => {
      updateComm({ id: newMsg.id, status: 'delivered' })
    }, 1500)
  }

  return (
    <div className="h-full flex">
      {/* Thread List */}
      <div className="w-[320px] flex-shrink-0 bg-slate border-r border-border-subtle flex flex-col">
        <div className="px-4 py-3 border-b border-border-subtle flex items-center justify-between">
          <h2 className="text-sm font-semibold text-primary tracking-tight">Conversations</h2>
          <span className="text-[10px] text-tertiary">{threads.length} threads</span>
        </div>
        <div className="flex-1 overflow-y-auto">
          {threads.map(thread => (
            <ThreadItem
              key={thread.patientName}
              thread={thread}
              isActive={activeThread === thread.patientName}
              onClick={() => setActiveThread(thread.patientName)}
            />
          ))}
        </div>
      </div>

      {/* Conversation */}
      <div className="flex-1 flex flex-col min-h-0">
        {!currentThread ? (
          <div className="flex-1 flex items-center justify-center text-tertiary text-sm">
            Select a conversation to view
          </div>
        ) : (
          <div key={activeThread} className="flex-1 flex flex-col min-h-0">
            {/* Thread header */}
            <div className="px-6 py-3 border-b border-border-subtle flex items-center justify-between bg-slate/50">
              <div>
                {(() => {
                  const pid = findPatientIdByName(currentThread.patientName)
                  return pid ? (
                    <button
                      type="button"
                      onClick={() => navigateTo('patients', { patientId: pid, patientName: currentThread.patientName })}
                      className="text-sm font-semibold text-primary hover:text-mint transition-all duration-200 ease-out active:scale-95"
                    >
                      {currentThread.patientName}
                    </button>
                  ) : (
                    <h3 className="text-sm font-semibold text-primary">{currentThread.patientName}</h3>
                  )
                })()}
                <p className="text-[10px] text-tertiary mt-0.5">{currentThread.messages.length} messages</p>
              </div>
            </div>

            {/* Chat messages */}
            <div className="flex-1 overflow-y-auto px-6 py-4">
              {currentThread.messages.length === 0 ? (
                <div className="h-full flex items-center justify-center">
                  <p className="text-tertiary text-xs italic">No messages yet — start the conversation below</p>
                </div>
              ) : (
                currentThread.messages.map((msg, i) => {
                  const isOutbound = msg.direction === 'outbound'
                  // Show date separator for time gaps
                  const showSep = i === 0 || shouldShowSeparator(currentThread.messages[i - 1], msg)
                  return (
                    <div key={msg.id}>
                      {showSep && (
                        <div className="flex items-center gap-3 my-4">
                          <div className="flex-1 h-px bg-border-subtle" />
                          <span className="text-[10px] text-tertiary">{msg.sent_at || msg.sent_time}</span>
                          <div className="flex-1 h-px bg-border-subtle" />
                        </div>
                      )}
                      <ChatBubble message={msg} isOutbound={isOutbound} />
                    </div>
                  )
                })
              )}
              <div ref={chatEndRef} />
            </div>

            {/* Compose bar */}
            <div className="px-6 py-3 border-t border-border-subtle bg-slate/30">
              <div className="flex items-center gap-3 bg-graphite rounded-xl border border-border-subtle focus-within:border-border-active transition-colors px-4 py-2">
                <input
                  ref={composeRef}
                  type="text"
                  value={composeText}
                  onChange={e => setComposeText(e.target.value)}
                  onFocus={() => trackAction('compose_message', currentThread?.patientName || '', 'patient', null)}
                  onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleSend()}
                  placeholder={`Message ${currentThread.patientName}...`}
                  className="flex-1 bg-transparent text-sm text-primary placeholder:text-tertiary outline-none"
                />
                <button
                  onClick={handleSend}
                  disabled={!composeText.trim()}
                  className="text-mint hover:text-mint/80 disabled:text-tertiary/30 transition-all duration-200 active:scale-95"
                >
                  <SendIcon size={16} />
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function groupByThread(messages) {
  const map = {}
  messages.forEach(msg => {
    const name = msg.patient_name
    if (!map[name]) map[name] = { patientName: name, messages: [] }
    map[name].messages.push(msg)
  })
  // Sort threads by most recent message
  return Object.values(map).sort((a, b) => {
    const aLast = a.messages[a.messages.length - 1]
    const bLast = b.messages[b.messages.length - 1]
    return (bLast?.sort_order || 0) - (aLast?.sort_order || 0)
  })
}

function shouldShowSeparator(prev, curr) {
  // Simple heuristic: show separator between messages
  return false // In demo, all messages are close together
}

function getDemoComms() {
  return [
    // Sarah Johnson thread
    { id: 'c1a', patient_name: 'Sarah Johnson', content: 'Hi Sarah, this is a reminder about your appointment with Dr Chen tomorrow at 9:00am. Reply YES to confirm or call us to reschedule.', sent_time: '9:15am', sent_at: '2 Apr 2026', status: 'responded', triggered_by: 'agent', direction: 'outbound', sort_order: 6 },
    { id: 'c1b', patient_name: 'Sarah Johnson', content: 'YES', sent_time: '9:22am', sent_at: '2 Apr 2026', status: 'read', triggered_by: 'patient', direction: 'inbound', sort_order: 5 },
    { id: 'c1c', patient_name: 'Sarah Johnson', content: 'Great, your appointment is confirmed. See you tomorrow at 9am!', sent_time: '9:22am', sent_at: '2 Apr 2026', status: 'delivered', triggered_by: 'agent', direction: 'outbound', sort_order: 4 },

    // James Wilson thread
    { id: 'c2a', patient_name: 'James Wilson', content: 'Dear James, this is a reminder that invoice INV-1923 for $85.00 is due. Please contact our office if you have any questions.', sent_time: '9:00am', sent_at: '2 Apr 2026', status: 'delivered', triggered_by: 'agent', direction: 'outbound', sort_order: 3 },

    // Robert MacLeod thread
    { id: 'c3a', patient_name: 'Robert MacLeod', content: 'Hi Robert, invoice INV-1847 for $175.00 is overdue. Please call us on (02) 9876-5432 to arrange payment.', sent_time: '8:45am', sent_at: '2 Apr 2026', status: 'sent', triggered_by: 'agent', direction: 'outbound', sort_order: 2 },

    // Maria Garcia thread
    { id: 'c4a', patient_name: 'Maria Garcia', content: 'Dear Maria, welcome to our practice! Your appointment with Dr Patel is confirmed for 10:00am today.', sent_time: '8:30am', sent_at: '2 Apr 2026', status: 'read', triggered_by: 'manual', direction: 'outbound', sort_order: 1 },
    { id: 'c4b', patient_name: 'Maria Garcia', content: 'Thank you! Should I bring anything else besides my Medicare card?', sent_time: '8:45am', sent_at: '2 Apr 2026', status: 'read', triggered_by: 'patient', direction: 'inbound', sort_order: 0 },

    // Emily Davis thread
    { id: 'c5a', patient_name: 'Emily Davis', content: 'Hi Emily, your lab results are now available. Please contact our office to discuss with Dr Patel.', sent_time: '8:00am', sent_at: '2 Apr 2026', status: 'delivered', triggered_by: 'manual', direction: 'outbound', sort_order: -1 },

    // Thomas Brown thread
    { id: 'c6a', patient_name: 'Thomas Brown', content: 'Hi Thomas, reminder about your appointment with Dr Chen at 11:30am today. Reply YES to confirm.', sent_time: '7:45am', sent_at: '2 Apr 2026', status: 'responded', triggered_by: 'agent', direction: 'outbound', sort_order: -2 },
    { id: 'c6b', patient_name: 'Thomas Brown', content: 'YES', sent_time: '7:52am', sent_at: '2 Apr 2026', status: 'read', triggered_by: 'patient', direction: 'inbound', sort_order: -3 },
  ]
}
