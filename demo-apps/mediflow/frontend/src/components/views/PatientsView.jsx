import { useState, useEffect, useRef, useCallback } from 'react'
import { api } from '../../api/client'
import { useApp } from '../../context/AppContext'
import { Search, Phone, Mail, AlertTriangle, Calendar, Receipt, MessageSquare, Send, Bot, Check, Clock, X, ChevronLeft, Loader2, Brain, Heart, Stethoscope, Pencil, Plus } from 'lucide-react'

// Derive a pastel hue from a name string for avatar backgrounds
function nameHue(name) {
  let hash = 0
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash)
  return ((hash % 360) + 360) % 360
}

function avatarStyle(name) {
  const h = nameHue(name)
  return {
    backgroundColor: `hsla(${h}, 60%, 70%, 0.12)`,
    color: `hsla(${h}, 60%, 70%, 1)`,
  }
}

const statusPill = {
  scheduled: 'bg-mint/10 text-mint',
  confirmed: 'bg-mint/10 text-mint',
  completed: 'bg-emerald/10 text-emerald',
  cancelled: 'bg-coral/10 text-coral',
  pending: 'bg-gold/10 text-gold',
  paid: 'bg-emerald/10 text-emerald',
  outstanding: 'bg-gold/10 text-gold',
  overdue: 'bg-coral/10 text-coral',
}

const msgStatusConfig = {
  sending: { text: 'Sending...', color: 'text-mint bg-mint/10' },
  sent: { text: 'Sent', color: 'text-secondary bg-white/5' },
  delivered: { text: 'Delivered', color: 'text-mint bg-mint/10' },
  read: { text: 'Read', color: 'text-emerald bg-emerald/10' },
  responded: { text: 'Confirmed', color: 'text-emerald bg-emerald/10 font-semibold' },
}

function MsgStatusBadge({ status }) {
  const config = msgStatusConfig[status] || msgStatusConfig.sent
  return (
    <span className={`inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full ${config.color}`}>
      {(status === 'delivered' || status === 'responded') && <Check size={10} />}
      {status === 'sending' && <Clock size={10} />}
      {config.text}
    </span>
  )
}

export default function PatientsView() {
  const { navigateTo, comms, setComms, addComm, updateComm, trackAction, viewParams, setScreenContext, uiCommand, clearUiCommand, agentHighlight, illuminate, illuminateTarget } = useApp()
  const [patients, setPatients] = useState([])
  const [selected, setSelected] = useState(null)
  const [search, setSearch] = useState('')
  const [detail, setDetail] = useState(null)
  const [detailTab, setDetailTab] = useState('appointments')
  const [composeText, setComposeText] = useState('')
  const chatEndRef = useRef(null)
  const searchTimerRef = useRef(null)

  // Memory state
  const [memories, setMemories] = useState([])
  const [memoryCounts, setMemoryCounts] = useState({}) // { patientId: count }
  const [editingMemory, setEditingMemory] = useState(null) // memory id
  const [editText, setEditText] = useState('')
  const [addingMemory, setAddingMemory] = useState(false)
  const [newMemoryType, setNewMemoryType] = useState('preference')
  const [newMemoryText, setNewMemoryText] = useState('')

  // Debounced search tracking (fires 1s after last keystroke)
  const trackSearch = useCallback((q) => {
    clearTimeout(searchTimerRef.current)
    if (!q) return
    searchTimerRef.current = setTimeout(() => {
      trackAction('search_patient', q, 'patient', null)
    }, 1000)
  }, [trackAction])

  // Booking flow state
  const [bookingOpen, setBookingOpen] = useState(false)
  const [bookingStep, setBookingStep] = useState('select') // select | confirm | success
  const [doctors, setDoctors] = useState([])
  const [bookingDoctor, setBookingDoctor] = useState(null)
  const [bookingSlots, setBookingSlots] = useState({}) // { 'YYYY-MM-DD': { doctor_name, slots: [...] } }
  const [bookingLoading, setBookingLoading] = useState(false)
  const [selectedSlot, setSelectedSlot] = useState(null) // { date, time, displayDate }
  const [bookingError, setBookingError] = useState(null)

  // Ensure shared comms are loaded
  useEffect(() => {
    if (comms.length > 0) return
    api.comms().then(d => setComms(d.communications || d)).catch(() => setComms(getDemoComms()))
  }, [])

  useEffect(() => {
    api.patients(search || undefined).then(d => setPatients(d.patients || d)).catch(() => setPatients(getDemoPatients()))
  }, [search])

  useEffect(() => {
    if (selected) {
      api.patient(selected).then(setDetail).catch(() => {
        const p = getDemoPatients().find(p => p.id === selected)
        setDetail(p ? { ...p, ...getDemoDetail(p.first_name, p.last_name) } : null)
      })
    }
  }, [selected])

  const list = patients.length ? patients : getDemoPatients()
  const outstandingFilter = viewParams?.filter === 'outstanding'
  const displayList = outstandingFilter
    ? list.filter(p => (p.overdue_invoice_count || 0) > 0 || (p.outstanding_invoice_count || 0) > 0)
    : list
  const patientName = detail ? `${detail.first_name} ${detail.last_name}` : ''

  // Update screen context for agent awareness
  useEffect(() => {
    if (detail) {
      setScreenContext({ patientId: detail.id, patientName: `${detail.first_name} ${detail.last_name}`, tab: detailTab })
    } else {
      setScreenContext(null)
    }
  }, [detail, detailTab, setScreenContext])

  // Handle agent UI commands
  useEffect(() => {
    if (!uiCommand) return
    const { command } = uiCommand
    if (command === 'select_patient') {
      setSelected(uiCommand.patient_id)
      clearUiCommand()
    } else if (command === 'open_booking') {
      setSelected(uiCommand.patient_id)
      setTimeout(() => {
        setBookingOpen(true)
        setBookingStep('select')
        if (uiCommand.doctor_id) setBookingDoctor(uiCommand.doctor_id)
      }, 400)
      clearUiCommand()
    } else if (command === 'set_patient_tab') {
      setSelected(uiCommand.patient_id)
      setTimeout(() => setDetailTab(uiCommand.tab), 300)
      clearUiCommand()
    }
  }, [uiCommand, clearUiCommand])

  // Invoice counts for tab badge and indicators
  const invoices = detail?.invoices || []
  const overdueCount = invoices.filter(inv => inv.status === 'overdue').length
  const outstandingCount = invoices.filter(inv => inv.status === 'outstanding').length
  const unpaidCount = overdueCount + outstandingCount

  // Get this patient's messages from shared comms state
  const commsSource = comms.length ? comms : getDemoComms()
  const patientMessages = patientName ? commsSource.filter(c => c.patient_name === patientName) : []

  // Scroll chat to bottom when messages change or tab switches to messages
  useEffect(() => {
    if (detailTab === 'messages') chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [detailTab, patientMessages.length])

  const handleSendMessage = () => {
    trackAction('send_message', patientName, 'patient', selected)
    navigateTo('comms', { patientId: selected, patientName, compose: true })
  }

  // Fetch doctors list once
  useEffect(() => {
    api.doctors().then(d => setDoctors(d.doctors || [])).catch(() => {
      setDoctors([
        { id: 'dr-chen', name: 'Dr Sarah Chen', specialty: 'General Practice' },
        { id: 'dr-patel', name: 'Dr Raj Patel', specialty: 'General Practice' },
        { id: 'dr-kim', name: 'Dr Joon Kim', specialty: 'Paediatrics' },
        { id: 'dr-nguyen', name: 'Dr Mai Nguyen', specialty: "Women's Health" },
      ])
    })
  }, [])

  // Close booking panel when patient changes
  useEffect(() => {
    setBookingOpen(false)
    setBookingStep('select')
    setSelectedSlot(null)
    setBookingSlots({})
  }, [selected])

  // Load memory counts for list indicators
  useEffect(() => {
    api.memoriesSummary().then(data => {
      const counts = {}
      ;(data.patients || []).forEach(p => { counts[p.patient_id] = p.memory_count })
      setMemoryCounts(counts)
    }).catch(() => {})
  }, [])

  // Load memories when patient changes or memory tab selected
  useEffect(() => {
    if (selected) {
      api.patientMemories(selected).then(d => setMemories(d.memories || [])).catch(() => setMemories([]))
    }
  }, [selected])

  // Handle cross-linking from InsightsView (viewParams.patientId + tab)
  useEffect(() => {
    if (viewParams?.patientId) {
      setSelected(viewParams.patientId)
      if (viewParams.tab) setDetailTab(viewParams.tab)
    }
  }, [viewParams])

  // Handle invoiceId cross-link: scroll to row and illuminate after detail loads
  useEffect(() => {
    if (!viewParams?.invoiceId || !detail) return
    if (viewParams.tab && detailTab !== viewParams.tab) return
    const invoices = detail.invoices || []
    if (!invoices.some(inv => inv.id === viewParams.invoiceId)) return
    const t = setTimeout(() => {
      const el = document.querySelector(`[data-invoice-id="${viewParams.invoiceId}"]`)
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' })
        illuminate({ type: 'invoice', id: viewParams.invoiceId, duration: 1200 })
      }
    }, 200)
    return () => clearTimeout(t)
  }, [viewParams?.invoiceId, detail, detailTab, illuminate])

  const fetchAvailability = async (doctorId) => {
    setBookingLoading(true)
    setBookingSlots({})
    setSelectedSlot(null)
    setBookingError(null)
    try {
      const today = new Date()
      const dates = [0, 1, 2].map(offset => {
        const d = new Date(today)
        d.setDate(d.getDate() + offset)
        return d.toISOString().split('T')[0]
      })
      const results = await Promise.all(dates.map(d => api.availability(doctorId, d)))
      const slotMap = {}
      results.forEach((res, i) => {
        slotMap[dates[i]] = {
          doctor_name: res.doctor_name || doctorId,
          slots: res.available_slots || [],
          note: res.note || null,
        }
      })
      setBookingSlots(slotMap)
    } catch (err) {
      setBookingError('Could not load availability')
    }
    setBookingLoading(false)
  }

  const handleBookAppt = () => {
    trackAction('book_appointment', patientName, 'patient', selected)
    setBookingOpen(true)
    setBookingStep('select')
    setSelectedSlot(null)
    setBookingError(null)
    const defaultDoc = doctors[0]?.id || 'dr-chen'
    setBookingDoctor(defaultDoc)
    fetchAvailability(defaultDoc)
  }

  const handleDoctorChange = (doctorId) => {
    setBookingDoctor(doctorId)
    fetchAvailability(doctorId)
  }

  const handleSlotSelect = (date, time) => {
    const d = new Date(date + 'T00:00:00')
    const displayDate = d.toLocaleDateString('en-AU', { weekday: 'short', day: 'numeric', month: 'short' })
    setSelectedSlot({ date, time, displayDate })
    setBookingStep('confirm')
  }

  const handleConfirmBooking = async () => {
    if (!selectedSlot || !detail) return
    setBookingLoading(true)
    setBookingError(null)
    try {
      const result = await api.bookAppointment({
        patient_id: detail.id,
        doctor_id: bookingDoctor,
        date: selectedSlot.date,
        time: selectedSlot.time,
        type: 'standard',
      })
      setBookingStep('success')
      // Refresh patient detail to show new appointment
      setTimeout(() => {
        api.patient(selected).then(setDetail).catch(() => {})
        setDetailTab('appointments')
      }, 1200)
      setTimeout(() => setBookingOpen(false), 2000)
    } catch (err) {
      setBookingError('Booking failed — please try again')
    }
    setBookingLoading(false)
  }

  const doctorName = doctors.find(d => d.id === bookingDoctor)?.name || 'Doctor'

  // Memory CRUD handlers
  const handleConfirmMemory = async (memoryId) => {
    trackAction('confirm_memory', memoryId, 'memory', memoryId)
    await api.updateMemory(selected, memoryId, { source: 'user_confirmed' }).catch(() => {})
    setMemories(prev => prev.map(m => m.id === memoryId ? { ...m, source: 'user_confirmed', confidence: 1.0 } : m))
  }

  const handleDismissMemory = async (memoryId) => {
    trackAction('dismiss_memory', memoryId, 'memory', memoryId)
    await api.deleteMemory(selected, memoryId).catch(() => {})
    setMemories(prev => prev.filter(m => m.id !== memoryId))
    setMemoryCounts(prev => ({ ...prev, [selected]: Math.max(0, (prev[selected] || 1) - 1) }))
  }

  const handleEditMemory = async (memoryId) => {
    if (!editText.trim()) return
    trackAction('edit_memory', memoryId, 'memory', memoryId)
    await api.updateMemory(selected, memoryId, { content: editText.trim() }).catch(() => {})
    setMemories(prev => prev.map(m => m.id === memoryId ? { ...m, content: editText.trim() } : m))
    setEditingMemory(null)
    setEditText('')
  }

  const handleAddMemory = async () => {
    if (!newMemoryText.trim()) return
    trackAction('add_memory', newMemoryType, 'memory', selected)
    const result = await api.addMemory(selected, { memory_type: newMemoryType, content: newMemoryText.trim() }).catch(() => null)
    if (result?.id) {
      setMemories(prev => [...prev, {
        id: result.id,
        patient_id: selected,
        memory_type: newMemoryType,
        content: newMemoryText.trim(),
        source: 'user_confirmed',
        confidence: 1.0,
        first_observed: new Date().toISOString(),
        status: 'active',
      }])
      setMemoryCounts(prev => ({ ...prev, [selected]: (prev[selected] || 0) + 1 }))
    }
    setNewMemoryText('')
    setAddingMemory(false)
  }

  const handleSendFromTab = () => {
    if (!composeText.trim() || !patientName) return
    trackAction('send_message', `Messages tab: ${patientName}`, 'patient', selected)
    const newMsg = {
      id: `c-new-${Date.now()}`,
      patient_name: patientName,
      content: composeText.trim(),
      sent_time: 'Just now',
      status: 'sending',
      triggered_by: 'manual',
      direction: 'outbound',
    }
    addComm(newMsg)
    setComposeText('')
    setTimeout(() => {
      updateComm({ id: newMsg.id, status: 'delivered' })
    }, 1500)
  }

  return (
    <div className="h-full flex">
      {/* Patient List */}
      <div className="w-[320px] flex-shrink-0 bg-slate border-r border-border-subtle flex flex-col">
        <div className="p-3">
          <div className="flex items-center gap-2 bg-ash rounded-xl px-3 py-2 border border-border-subtle focus-within:border-border-active transition-colors">
            <Search size={14} className="text-tertiary flex-shrink-0" />
            <input
              type="text"
              value={search}
              onChange={e => { setSearch(e.target.value); trackSearch(e.target.value) }}
              placeholder="Search patients..."
              className="flex-1 bg-transparent text-sm text-primary placeholder:text-tertiary outline-none"
            />
          </div>
          {outstandingFilter && (
            <div className="mt-2 flex items-center justify-between text-[11px] px-2 py-1.5 rounded-lg bg-coral/10 text-coral">
              <span>Filter: outstanding invoices</span>
              <button
                onClick={() => navigateTo('patients', null)}
                className="text-coral/80 hover:text-coral transition-all duration-200 ease-out active:scale-95"
                title="Clear filter"
              >
                Clear
              </button>
            </div>
          )}
        </div>

        <div className="flex-1 overflow-y-auto">
          {displayList.map(p => {
            const isActive = selected === p.id
            const initials = `${(p.first_name || '')[0]}${(p.last_name || '')[0]}`.toUpperCase()
            const name = `${p.first_name} ${p.last_name}`
            const aStyle = avatarStyle(name)
            const isListHighlighted = agentHighlight?.target === 'list_item' && agentHighlight?.id === p.id
            return (
              <button
                key={p.id}
                onClick={() => { setSelected(p.id); trackAction('view_patient_detail', p.first_name + ' ' + p.last_name, 'patient', p.id) }}
                className={`w-full text-left px-3 py-3 flex items-center gap-3 border-l-2 transition-all
                  ${isListHighlighted ? 'agent-blink' : ''}
                  ${isActive
                    ? 'bg-mint/5 border-l-mint'
                    : 'border-l-transparent hover:bg-white/[0.02]'
                  }`}
              >
                <div className="w-9 h-9 rounded-full flex items-center justify-center text-xs font-semibold flex-shrink-0" style={aStyle}>
                  {initials}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-primary text-sm font-medium truncate">{name}</p>
                  <p className="text-tertiary text-xs">Last visit: {p.last_visit || 'N/A'}</p>
                </div>
                {memoryCounts[p.id] > 0 && (
                  <span className="flex items-center gap-0.5 text-violet text-[10px]" title={`${memoryCounts[p.id]} memories`}>
                    <Brain size={10} /> {memoryCounts[p.id]}
                  </span>
                )}
                {p.no_show_count > 0 && (
                  <span className="flex items-center gap-0.5 text-gold text-[10px]">
                    <AlertTriangle size={10} /> {p.no_show_count}
                  </span>
                )}
                {p.overdue_invoice_count > 0 && (
                  <span className="flex items-center gap-0.5 text-coral text-[10px]" title="Overdue invoices">
                    <AlertTriangle size={10} />
                  </span>
                )}
              </button>
            )
          })}
        </div>
      </div>

      {/* Detail */}
      <div className="flex-1 overflow-auto p-6">
        {!selected || !detail ? (
          <div className="h-full flex items-center justify-center text-tertiary text-sm">
            Select a patient to view details
          </div>
        ) : (
          <div key={selected}>
            {/* Header */}
            <div className="flex items-start gap-4 mb-4">
              <div className="w-14 h-14 rounded-2xl flex items-center justify-center text-lg font-semibold" style={avatarStyle(patientName)}>
                {`${(detail.first_name || '')[0]}${(detail.last_name || '')[0]}`.toUpperCase()}
              </div>
              <div>
                <h2 className="text-xl font-semibold text-primary tracking-tight">{patientName}</h2>
                <div className="flex items-center gap-4 mt-1 text-sm text-secondary">
                  {detail.dob && <span>DOB: {detail.dob}</span>}
                  {detail.phone && <span className="flex items-center gap-1"><Phone size={12} /> {detail.phone}</span>}
                  {detail.email && <span className="flex items-center gap-1"><Mail size={12} /> {detail.email}</span>}
                </div>
                {memories.length > 0 && (
                  <div className="flex items-center gap-1.5 mt-2 flex-wrap">
                    {memories.slice(0, 3).map(m => {
                      const cfg = memoryTypeConfig[m.memory_type] || memoryTypeConfig.preference
                      const Icon = cfg.icon
                      const text = m.content.length > 48 ? m.content.slice(0, 48).trim() + '…' : m.content
                      return (
                        <span
                          key={m.id}
                          title={m.content}
                          className={`inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full ${cfg.bg} ${cfg.color} transition-all duration-200 ease-out`}
                        >
                          <Icon size={11} className="flex-shrink-0" />
                          <span className="truncate">{text}</span>
                        </span>
                      )
                    })}
                    {memories.length > 3 && (
                      <span className="text-[10px] text-tertiary">+{memories.length - 3} more</span>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Action Bar */}
            <div className="flex items-center gap-2 mb-5">
              <button
                onClick={handleSendMessage}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-mint bg-mint/10 hover:bg-mint/15 transition-all duration-200 active:scale-95"
              >
                <Send size={12} /> Send Message
              </button>
              <button
                onClick={handleBookAppt}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 active:scale-95 ${
                  bookingOpen
                    ? 'text-mint bg-mint/15'
                    : 'text-secondary bg-white/5 hover:bg-white/10'
                }`}
              >
                <Calendar size={12} /> Book Appt
              </button>
            </div>

            {/* Inline Booking Panel */}
            {bookingOpen && (
              <div className="mb-5 bg-graphite rounded-xl border border-border-subtle overflow-hidden panel-slide-up">
                {/* Panel header */}
                <div className="flex items-center justify-between px-4 py-3 border-b border-border-subtle">
                  <div className="flex items-center gap-3">
                    <h3 className="text-sm font-medium text-primary">
                      {bookingStep === 'success' ? 'Appointment Booked' : 'Book Appointment'}
                    </h3>
                    {bookingStep === 'select' && (
                      <select
                        value={bookingDoctor || ''}
                        onChange={e => handleDoctorChange(e.target.value)}
                        className="text-xs bg-ash border border-border-subtle rounded-lg px-2 py-1 text-secondary outline-none focus:border-border-active"
                      >
                        {doctors.map(d => (
                          <option key={d.id} value={d.id}>{d.name}</option>
                        ))}
                      </select>
                    )}
                  </div>
                  <button
                    onClick={() => setBookingOpen(false)}
                    className="text-tertiary hover:text-secondary transition-colors"
                  >
                    <X size={14} />
                  </button>
                </div>

                {/* Panel body */}
                <div className="p-4">
                  {bookingLoading && bookingStep !== 'confirm' && (
                    <div className="flex items-center justify-center py-6 gap-2 text-tertiary text-sm">
                      <Loader2 size={14} className="animate-spin" /> Loading availability...
                    </div>
                  )}

                  {bookingError && (
                    <p className="text-coral text-xs text-center py-4">{bookingError}</p>
                  )}

                  {/* Slot selection grid */}
                  {bookingStep === 'select' && !bookingLoading && !bookingError && (
                    <div className="grid grid-cols-3 gap-3">
                      {Object.entries(bookingSlots).map(([date, data]) => {
                        const d = new Date(date + 'T00:00:00')
                        const label = d.toLocaleDateString('en-AU', { weekday: 'short', day: 'numeric', month: 'short' })
                        return (
                          <div key={date}>
                            <p className="text-xs font-medium text-secondary mb-2">{label}</p>
                            {data.note ? (
                              <p className="text-[11px] text-tertiary italic">{data.note}</p>
                            ) : data.slots.length === 0 ? (
                              <p className="text-[11px] text-tertiary italic">No slots available</p>
                            ) : (
                              <div className="grid grid-cols-2 gap-1">
                                {data.slots.map(time => (
                                  <button
                                    key={time}
                                    onClick={() => handleSlotSelect(date, time)}
                                    className="text-[11px] py-1.5 rounded-lg font-medium border border-mint/30 text-mint hover:bg-mint/10 transition-all duration-200 active:scale-95"
                                  >
                                    {time}
                                  </button>
                                ))}
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  )}

                  {/* Confirmation */}
                  {bookingStep === 'confirm' && selectedSlot && (
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <button
                          onClick={() => { setBookingStep('select'); setSelectedSlot(null) }}
                          className="text-tertiary hover:text-secondary transition-colors"
                        >
                          <ChevronLeft size={14} />
                        </button>
                        <p className="text-sm text-primary">
                          Book <span className="text-mint font-medium">{doctorName}</span> at{' '}
                          <span className="text-mint font-medium">{selectedSlot.time}</span> on{' '}
                          <span className="text-mint font-medium">{selectedSlot.displayDate}</span>?
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => { setBookingStep('select'); setSelectedSlot(null) }}
                          className="text-xs px-3 py-1.5 rounded-lg text-secondary bg-white/5 hover:bg-white/10 transition-all duration-200 active:scale-95"
                        >
                          Cancel
                        </button>
                        <button
                          onClick={handleConfirmBooking}
                          disabled={bookingLoading}
                          className="text-xs px-3 py-1.5 rounded-lg font-medium text-void bg-mint hover:bg-mint/90 disabled:opacity-50 transition-all duration-200 active:scale-95 flex items-center gap-1.5"
                        >
                          {bookingLoading ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />}
                          Confirm
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Success */}
                  {bookingStep === 'success' && (
                    <div className="flex items-center justify-center gap-2 py-2 text-mint text-sm font-medium">
                      <Check size={16} /> Booked — {doctorName} at {selectedSlot?.time}, {selectedSlot?.displayDate}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Tabs */}
            <div className="flex gap-6 border-b border-border-subtle mb-4">
              {['appointments', 'invoices', 'messages', 'memory'].map(tab => {
                const isTabHighlighted = agentHighlight?.target === 'tab' && agentHighlight?.id === tab
                return (
                <button
                  key={tab}
                  onClick={() => setDetailTab(tab)}
                  className={`pb-2 text-sm font-medium capitalize border-b-2 transition-all duration-200
                    ${isTabHighlighted ? 'agent-blink' : ''}
                    ${detailTab === tab
                      ? tab === 'memory' ? 'text-violet border-violet' : 'text-mint border-mint'
                      : 'text-tertiary border-transparent hover:text-secondary'
                    }`}
                >
                  {tab}
                  {tab === 'invoices' && unpaidCount > 0 && (
                    <span className={`ml-1.5 text-xs ${overdueCount > 0 ? 'text-coral' : 'text-gold'}`}>
                      ({unpaidCount})
                    </span>
                  )}
                  {tab === 'memory' && memoryCounts[selected] > 0 && (
                    <span className="ml-1.5 text-xs text-violet">
                      ({memoryCounts[selected]})
                    </span>
                  )}
                </button>
              )})}
            </div>

            {/* Tab content */}
            <div key={detailTab} className="content-enter space-y-3">
              {detailTab === 'appointments' && (detail.appointments || []).map((a, i) => (
                <div key={i} className="bg-graphite rounded-xl border border-border-subtle p-3 flex items-center justify-between group">
                  <div className="flex items-center gap-3">
                    <Calendar size={14} className="text-tertiary" />
                    <div>
                      <p className="text-sm text-primary">{a.date} at {a.time}</p>
                      <p className="text-xs text-tertiary">{a.doctor_name} · {a.type}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase tracking-wider ${statusPill[a.status] || ''}`}>
                      {a.status}
                    </span>
                    {(a.status === 'confirmed' || a.status === 'scheduled') && (
                      <div className="hidden group-hover:flex items-center gap-1">
                        <button className="text-[10px] text-tertiary hover:text-secondary px-1.5 py-0.5 rounded border border-border-subtle hover:border-border-active transition-all duration-200 active:scale-95">
                          Reschedule
                        </button>
                        <button className="text-[10px] text-tertiary hover:text-coral px-1.5 py-0.5 rounded border border-border-subtle hover:border-coral/30 transition-all duration-200 active:scale-95">
                          Cancel
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {detailTab === 'invoices' && (detail.invoices || []).map((inv, i) => {
                const isIlluminated = illuminateTarget?.type === 'invoice' && illuminateTarget?.id === inv.id
                return (
                <div
                  key={i}
                  data-invoice-id={inv.id}
                  className={`bg-graphite rounded-xl border p-3 flex items-center justify-between group transition-all duration-300
                    ${isIlluminated ? 'border-mint shadow-[0_0_20px_rgba(0,210,229,0.3)]' : 'border-border-subtle'}`}
                >
                  <div className="flex items-center gap-3">
                    <Receipt size={14} className="text-tertiary" />
                    <div>
                      <p className="text-sm text-primary">{inv.id} — ${inv.amount?.toFixed(2)}</p>
                      <p className="text-xs text-tertiary">Due: {inv.due_date}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase tracking-wider ${statusPill[inv.status] || ''}`}>
                      {inv.status}
                    </span>
                    {(inv.status === 'outstanding' || inv.status === 'overdue') && (
                      <button
                        onClick={() => { trackAction('send_reminder', `Invoice ${inv.id}`, 'invoice', inv.id); handleSendMessage() }}
                        className="hidden group-hover:flex items-center gap-1 text-[10px] text-tertiary hover:text-gold px-1.5 py-0.5 rounded border border-border-subtle hover:border-gold/30 transition-colors"
                      >
                        Send Reminder
                      </button>
                    )}
                  </div>
                </div>
              )})}

              {detailTab === 'messages' && (
                <div className="flex flex-col" style={{ height: 'calc(100vh - 340px)', minHeight: '300px' }}>
                  {/* Chat messages */}
                  <div className="flex-1 overflow-y-auto bg-graphite rounded-t-xl border border-b-0 border-border-subtle p-4 space-y-3">
                    {patientMessages.length === 0 ? (
                      <p className="text-tertiary text-sm text-center py-8">No messages yet</p>
                    ) : (
                      patientMessages.map(msg => {
                        const isOutbound = msg.direction === 'outbound'
                        const isAgent = msg.triggered_by === 'agent' || msg.triggered_by === 'skill'
                        return (
                          <div key={msg.id} className={`flex ${isOutbound ? 'justify-end' : 'justify-start'}`}>
                            <div className={`max-w-[80%] flex flex-col ${isOutbound ? 'items-end' : 'items-start'}`}>
                              <div className={`px-3 py-2 text-xs leading-relaxed rounded-lg
                                ${isOutbound
                                  ? `bg-ash ${isAgent ? 'border-l-2 border-l-mint' : ''}`
                                  : 'bg-slate'
                                }`}
                              >
                                <p className="text-primary whitespace-pre-wrap">{msg.content}</p>
                              </div>
                              <div className={`flex items-center gap-1.5 mt-0.5 ${isOutbound ? 'flex-row-reverse' : ''}`}>
                                {isAgent && <Bot size={8} className="text-mint" />}
                                <span className="text-tertiary text-[9px]">{msg.sent_time}</span>
                                {isOutbound && msg.status && <MsgStatusBadge status={msg.status} />}
                              </div>
                            </div>
                          </div>
                        )
                      })
                    )}
                    <div ref={chatEndRef} />
                  </div>

                  {/* Slim compose bar */}
                  <div className="bg-graphite rounded-b-xl border border-t-0 border-border-subtle px-4 py-2.5 border-t border-t-border-subtle">
                    <div className="flex items-center gap-2 bg-ash rounded-lg border border-border-subtle focus-within:border-border-active transition-colors px-3 py-1.5">
                      <input
                        type="text"
                        value={composeText}
                        onChange={e => setComposeText(e.target.value)}
                        onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleSendFromTab()}
                        placeholder="Type a message..."
                        className="flex-1 bg-transparent text-xs text-primary placeholder:text-tertiary outline-none"
                      />
                      <button
                        onClick={handleSendFromTab}
                        disabled={!composeText.trim()}
                        className="text-mint hover:text-mint/80 disabled:text-tertiary/30 transition-all duration-200 active:scale-95"
                      >
                        <Send size={14} />
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {detailTab === 'memory' && (
                <MemoryTab
                  memories={memories}
                  onConfirm={handleConfirmMemory}
                  onDismiss={handleDismissMemory}
                  onEdit={handleEditMemory}
                  editingMemory={editingMemory}
                  setEditingMemory={setEditingMemory}
                  editText={editText}
                  setEditText={setEditText}
                  addingMemory={addingMemory}
                  setAddingMemory={setAddingMemory}
                  newMemoryType={newMemoryType}
                  setNewMemoryType={setNewMemoryType}
                  newMemoryText={newMemoryText}
                  setNewMemoryText={setNewMemoryText}
                  onAdd={handleAddMemory}
                />
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

const memoryTypeConfig = {
  preference: { label: 'Preferences', icon: Heart, color: 'text-mint', bg: 'bg-mint/10' },
  behavioral: { label: 'Behavioral Patterns', icon: Calendar, color: 'text-violet', bg: 'bg-violet/10' },
  communication: { label: 'Communication', icon: MessageSquare, color: 'text-periwinkle', bg: 'bg-periwinkle/10' },
  medical_context: { label: 'Medical Context', icon: Stethoscope, color: 'text-gold', bg: 'bg-gold/10' },
}

const sourceConfig = {
  agent_observed: { label: 'Observed', color: 'bg-mint/15 text-mint' },
  system_detected: { label: 'Detected', color: 'bg-violet/15 text-violet' },
  user_confirmed: { label: 'Confirmed', color: 'bg-emerald/15 text-emerald' },
}

function MemoryTab({
  memories, onConfirm, onDismiss, onEdit,
  editingMemory, setEditingMemory, editText, setEditText,
  addingMemory, setAddingMemory, newMemoryType, setNewMemoryType,
  newMemoryText, setNewMemoryText, onAdd,
}) {
  // Group by type
  const grouped = {}
  for (const m of memories) {
    const t = m.memory_type || 'preference'
    if (!grouped[t]) grouped[t] = []
    grouped[t].push(m)
  }

  if (memories.length === 0 && !addingMemory) {
    return (
      <div className="text-center py-12">
        <Brain size={28} className="text-violet/30 mx-auto mb-3" />
        <p className="text-secondary text-sm mb-1">No memories yet</p>
        <p className="text-tertiary text-xs max-w-xs mx-auto mb-4">
          I haven't learned anything specific about this patient yet. Memories are built from conversations and behavior patterns over time.
        </p>
        <button
          onClick={() => setAddingMemory(true)}
          className="text-xs text-violet font-medium flex items-center gap-1 mx-auto hover:text-violet/80 transition-all duration-200 active:scale-95"
        >
          <Plus size={12} /> Add Memory
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {Object.entries(memoryTypeConfig).map(([type, config]) => {
        const items = grouped[type]
        if (!items?.length) return null
        const Icon = config.icon
        return (
          <div key={type}>
            <div className="flex items-center gap-2 mb-2">
              <Icon size={14} className={config.color} />
              <h4 className="text-xs font-semibold text-secondary tracking-wide uppercase">{config.label}</h4>
            </div>
            <div className="space-y-2">
              {items.map(m => {
                const src = sourceConfig[m.source] || sourceConfig.agent_observed
                const isEditing = editingMemory === m.id
                return (
                  <div key={m.id} className="bg-graphite rounded-xl border border-border-subtle p-3 group hover:border-border-glow transition-all duration-200">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        {isEditing ? (
                          <div className="flex items-center gap-2">
                            <input
                              type="text"
                              value={editText}
                              onChange={e => setEditText(e.target.value)}
                              onKeyDown={e => e.key === 'Enter' && onEdit(m.id)}
                              className="flex-1 bg-ash rounded-lg border border-border-subtle px-2 py-1 text-xs text-primary outline-none focus:border-border-active"
                              autoFocus
                            />
                            <button onClick={() => onEdit(m.id)} className="text-mint hover:text-mint/80 transition-colors"><Check size={14} /></button>
                            <button onClick={() => setEditingMemory(null)} className="text-tertiary hover:text-secondary transition-colors"><X size={14} /></button>
                          </div>
                        ) : (
                          <p className="text-sm text-primary leading-relaxed">{m.content}</p>
                        )}
                      </div>
                      <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase tracking-wider flex-shrink-0 ${src.color}`}>
                        {src.label}
                      </span>
                    </div>

                    {/* Confidence bar */}
                    <div className="mt-2 flex items-center gap-2">
                      <div className="flex-1 h-1 bg-void rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-500 ${
                            m.confidence >= 0.8 ? 'bg-emerald' : m.confidence >= 0.5 ? 'bg-gold' : 'bg-coral/50'
                          }`}
                          style={{ width: `${(m.confidence || 0.5) * 100}%` }}
                        />
                      </div>
                      <span className="text-[10px] text-tertiary">{Math.round((m.confidence || 0.5) * 100)}%</span>
                    </div>

                    {/* Timestamp + actions */}
                    <div className="mt-2 flex items-center justify-between">
                      <span className="text-[10px] text-tertiary">
                        {m.first_observed ? `Observed: ${new Date(m.first_observed).toLocaleDateString()}` : ''}
                        {m.last_confirmed ? ` · Confirmed: ${new Date(m.last_confirmed).toLocaleDateString()}` : ''}
                      </span>
                      <div className="hidden group-hover:flex items-center gap-1">
                        {m.source !== 'user_confirmed' && (
                          <button
                            onClick={() => onConfirm(m.id)}
                            className="text-[10px] text-tertiary hover:text-emerald px-1.5 py-0.5 rounded border border-border-subtle hover:border-emerald/30 transition-all duration-200 active:scale-95 flex items-center gap-0.5"
                          >
                            <Check size={10} /> Confirm
                          </button>
                        )}
                        <button
                          onClick={() => { setEditingMemory(m.id); setEditText(m.content) }}
                          className="text-[10px] text-tertiary hover:text-secondary px-1.5 py-0.5 rounded border border-border-subtle hover:border-border-active transition-all duration-200 active:scale-95 flex items-center gap-0.5"
                        >
                          <Pencil size={10} /> Edit
                        </button>
                        <button
                          onClick={() => onDismiss(m.id)}
                          className="text-[10px] text-tertiary hover:text-coral px-1.5 py-0.5 rounded border border-border-subtle hover:border-coral/30 transition-all duration-200 active:scale-95 flex items-center gap-0.5"
                        >
                          <X size={10} /> Dismiss
                        </button>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )
      })}

      {/* Add Memory */}
      {addingMemory ? (
        <div className="bg-graphite rounded-xl border border-border-active p-3 space-y-2 animate-[count-up-fade_200ms_ease-out]">
          <div className="flex items-center gap-2">
            <select
              value={newMemoryType}
              onChange={e => setNewMemoryType(e.target.value)}
              className="text-xs bg-ash border border-border-subtle rounded-lg px-2 py-1.5 text-secondary outline-none focus:border-border-active"
            >
              {Object.entries(memoryTypeConfig).map(([val, cfg]) => (
                <option key={val} value={val}>{cfg.label}</option>
              ))}
            </select>
          </div>
          <input
            type="text"
            value={newMemoryText}
            onChange={e => setNewMemoryText(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && onAdd()}
            placeholder="What did you learn about this patient?"
            className="w-full bg-ash rounded-lg border border-border-subtle px-3 py-2 text-xs text-primary placeholder:text-tertiary outline-none focus:border-border-active"
            autoFocus
          />
          <div className="flex items-center gap-2 justify-end">
            <button onClick={() => setAddingMemory(false)} className="text-xs text-tertiary hover:text-secondary px-2 py-1 transition-colors">Cancel</button>
            <button
              onClick={onAdd}
              disabled={!newMemoryText.trim()}
              className="text-xs text-void bg-violet px-3 py-1 rounded-lg font-medium hover:bg-violet/90 disabled:opacity-50 transition-all duration-200 active:scale-95"
            >
              Save
            </button>
          </div>
        </div>
      ) : (
        <button
          onClick={() => setAddingMemory(true)}
          className="w-full flex items-center justify-center gap-1.5 py-2.5 rounded-lg border border-dashed border-border-subtle text-xs text-tertiary hover:text-violet hover:border-violet/30 transition-all duration-200"
        >
          <Plus size={12} /> Add Memory
        </button>
      )}
    </div>
  )
}

function getDemoPatients() {
  return [
    { id: 'p1', first_name: 'Sarah', last_name: 'Johnson', dob: '15 Mar 1985', phone: '0412-345-678', email: 'sarah.j@email.com', no_show_count: 2, overdue_invoice_count: 1, last_visit: 'Mar 28', notes: 'Prefers morning appointments. Allergic to penicillin.' },
    { id: 'p2', first_name: 'James', last_name: 'Wilson', dob: '22 Jul 1990', phone: '0423-456-789', email: 'j.wilson@email.com', no_show_count: 0, overdue_invoice_count: 0, last_visit: 'Mar 15' },
    { id: 'p3', first_name: 'Maria', last_name: 'Garcia', dob: '8 Nov 1978', phone: '0434-567-890', email: 'mgarcia@email.com', no_show_count: 0, overdue_invoice_count: 0, last_visit: 'Feb 20' },
    { id: 'p4', first_name: 'Robert', last_name: 'MacLeod', dob: '3 Jan 1965', phone: '0445-678-901', email: 'r.macleod@email.com', no_show_count: 1, overdue_invoice_count: 1, last_visit: 'Mar 10' },
    { id: 'p5', first_name: 'Emily', last_name: 'Davis', dob: '19 Sep 1992', phone: '0456-789-012', email: 'emily.d@email.com', no_show_count: 0, overdue_invoice_count: 0, last_visit: 'Mar 25' },
    { id: 'p6', first_name: 'Thomas', last_name: 'Brown', dob: '14 Jun 1988', phone: '0467-890-123', email: 'tbrown@email.com', no_show_count: 0, overdue_invoice_count: 0, last_visit: 'Mar 30' },
    { id: 'p7', first_name: 'Lisa', last_name: 'Wang', dob: '27 Apr 1975', phone: '0478-901-234', email: 'lisa.w@email.com', no_show_count: 0, overdue_invoice_count: 0, last_visit: 'Mar 22' },
    { id: 'p8', first_name: 'Michael', last_name: 'Taylor', dob: '11 Dec 1982', phone: '0489-012-345', email: 'mtaylor@email.com', no_show_count: 3, overdue_invoice_count: 0, last_visit: 'Feb 28' },
  ]
}

function getDemoDetail(firstName, lastName) {
  const name = `${firstName} ${lastName}`
  const invoicesByPatient = {
    'Sarah Johnson': [
      { id: 'INV-2001', amount: 175, due_date: '15 Apr 2026', status: 'outstanding' },
      { id: 'INV-1890', amount: 220, due_date: '10 Feb 2026', status: 'overdue' },
      { id: 'INV-1923', amount: 85, due_date: '1 Mar 2026', status: 'paid' },
    ],
    'Robert MacLeod': [
      { id: 'INV-1847', amount: 175, due_date: '1 Mar 2026', status: 'overdue' },
      { id: 'INV-1780', amount: 120, due_date: '15 Jan 2026', status: 'paid' },
    ],
    'James Wilson': [
      { id: 'INV-2010', amount: 95, due_date: '20 Apr 2026', status: 'outstanding' },
      { id: 'INV-1923', amount: 85, due_date: '1 Mar 2026', status: 'paid' },
    ],
  }
  return {
    appointments: [
      { date: '2 Apr 2026', time: '9:00', doctor_name: 'Dr Chen', type: 'General', status: 'confirmed' },
      { date: '28 Mar 2026', time: '10:30', doctor_name: 'Dr Patel', type: 'Follow-up', status: 'completed' },
      { date: '15 Mar 2026', time: '14:00', doctor_name: 'Dr Chen', type: 'General', status: 'cancelled' },
    ],
    invoices: invoicesByPatient[name] || [
      { id: 'INV-1923', amount: 85, due_date: '1 Mar 2026', status: 'paid' },
    ],
  }
}

function getDemoComms() {
  return [
    { id: 'c1a', patient_name: 'Sarah Johnson', content: 'Hi Sarah, this is a reminder about your appointment with Dr Chen tomorrow at 9:00am. Reply YES to confirm or call us to reschedule.', sent_time: '9:15am', sent_at: '2 Apr 2026', status: 'responded', triggered_by: 'agent', direction: 'outbound', sort_order: 6 },
    { id: 'c1b', patient_name: 'Sarah Johnson', content: 'YES', sent_time: '9:22am', sent_at: '2 Apr 2026', status: 'read', triggered_by: 'patient', direction: 'inbound', sort_order: 5 },
    { id: 'c1c', patient_name: 'Sarah Johnson', content: 'Great, your appointment is confirmed. See you tomorrow at 9am!', sent_time: '9:22am', sent_at: '2 Apr 2026', status: 'delivered', triggered_by: 'agent', direction: 'outbound', sort_order: 4 },
    { id: 'c2a', patient_name: 'James Wilson', content: 'Dear James, this is a reminder that invoice INV-1923 for $85.00 is due. Please contact our office if you have any questions.', sent_time: '9:00am', sent_at: '2 Apr 2026', status: 'delivered', triggered_by: 'agent', direction: 'outbound', sort_order: 3 },
    { id: 'c3a', patient_name: 'Robert MacLeod', content: 'Hi Robert, invoice INV-1847 for $175.00 is overdue. Please call us on (02) 9876-5432 to arrange payment.', sent_time: '8:45am', sent_at: '2 Apr 2026', status: 'sent', triggered_by: 'agent', direction: 'outbound', sort_order: 2 },
    { id: 'c4a', patient_name: 'Maria Garcia', content: 'Dear Maria, welcome to our practice! Your appointment with Dr Patel is confirmed for 10:00am today.', sent_time: '8:30am', sent_at: '2 Apr 2026', status: 'read', triggered_by: 'manual', direction: 'outbound', sort_order: 1 },
    { id: 'c4b', patient_name: 'Maria Garcia', content: 'Thank you! Should I bring anything else besides my Medicare card?', sent_time: '8:45am', sent_at: '2 Apr 2026', status: 'read', triggered_by: 'patient', direction: 'inbound', sort_order: 0 },
    { id: 'c5a', patient_name: 'Emily Davis', content: 'Hi Emily, your lab results are now available. Please contact our office to discuss with Dr Patel.', sent_time: '8:00am', sent_at: '2 Apr 2026', status: 'delivered', triggered_by: 'manual', direction: 'outbound', sort_order: -1 },
    { id: 'c6a', patient_name: 'Thomas Brown', content: 'Hi Thomas, reminder about your appointment with Dr Chen at 11:30am today. Reply YES to confirm.', sent_time: '7:45am', sent_at: '2 Apr 2026', status: 'responded', triggered_by: 'agent', direction: 'outbound', sort_order: -2 },
    { id: 'c6b', patient_name: 'Thomas Brown', content: 'YES', sent_time: '7:52am', sent_at: '2 Apr 2026', status: 'read', triggered_by: 'patient', direction: 'inbound', sort_order: -3 },
  ]
}
