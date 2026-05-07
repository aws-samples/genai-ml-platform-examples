import { useState, useEffect, useCallback, useRef } from 'react'
import { api } from '../../api/client'
import { useApp } from '../../context/AppContext'
import { ChevronLeft, ChevronRight, X } from 'lucide-react'

const doctorColors = {
  'dr-chen': { border: 'border-l-mint', bg: 'bg-mint/5', dot: 'bg-mint' },
  'dr-patel': { border: 'border-l-periwinkle', bg: 'bg-periwinkle/5', dot: 'bg-periwinkle' },
  'dr-kim': { border: 'border-l-apricot', bg: 'bg-apricot/5', dot: 'bg-apricot' },
  'dr-nguyen': { border: 'border-l-violet', bg: 'bg-violet/5', dot: 'bg-violet' },
}

const defaultColors = { border: 'border-l-mint', bg: 'bg-mint/5', dot: 'bg-mint' }

const hours = Array.from({ length: 21 }, (_, i) => {
  const h = Math.floor(i / 2) + 8
  const m = i % 2 === 0 ? '00' : '30'
  return `${h}:${m}`
})

const dayLabels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']

function formatWeekHeader(mondayStr) {
  if (!mondayStr) return ''
  const mon = new Date(mondayStr + 'T00:00:00')
  const fri = new Date(mon)
  fri.setDate(fri.getDate() + 4)
  const fmt = (d) => `${d.getDate()} ${d.toLocaleDateString('en-AU', { month: 'short' })}`
  return `${fmt(mon)} — ${fmt(fri)} ${mon.getFullYear()}`
}

function getDayDates(mondayStr) {
  if (!mondayStr) return dayLabels.map(() => '')
  const mon = new Date(mondayStr + 'T00:00:00')
  return dayLabels.map((_, i) => {
    const d = new Date(mon)
    d.setDate(d.getDate() + i)
    return `${d.getDate()} ${d.toLocaleDateString('en-AU', { month: 'short' })}`
  })
}

function isToday(mondayStr, dayIndex) {
  if (!mondayStr) return false
  const d = new Date(mondayStr + 'T00:00:00')
  d.setDate(d.getDate() + dayIndex)
  const now = new Date()
  return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth() && d.getDate() === now.getDate()
}

function ApptBlock({ appt, laneIndex, laneCount, onClick, isOpen }) {
  const colors = doctorColors[appt.doctor_id] || defaultColors
  const durationSlots = (appt.duration_mins || 30) / 30
  const widthPct = 100 / laneCount
  const leftPct = laneIndex * widthPct

  return (
    <button
      type="button"
      onClick={(e) => { e.stopPropagation(); onClick?.(appt, e.currentTarget) }}
      className={`absolute rounded-lg border text-left ${colors.border} ${colors.bg} border-l-4 ring-1 ring-border-subtle/30 px-1.5 py-1 overflow-hidden cursor-pointer
        transition-all duration-200 ease-out active:scale-95 hover:border-border-glow hover:shadow-[0_0_15px_rgba(99,220,190,0.05)] hover:z-10
        ${isOpen ? 'border-border-glow shadow-[0_0_15px_rgba(99,220,190,0.12)] z-10' : 'border-border-subtle'}`}
      style={{
        height: `${durationSlots * 56 - 6}px`,
        left: `${leftPct}%`,
        width: `${widthPct - 1}%`,
      }}
    >
      <p className="text-primary text-xs font-medium truncate leading-tight">{appt.patient_name}</p>
      {laneCount <= 2 && durationSlots >= 1 && <p className="text-tertiary text-[10px] truncate">{appt.doctor_name}</p>}
    </button>
  )
}

const statusLabel = {
  scheduled: { text: 'Confirmed', cls: 'text-emerald bg-emerald/10' },
  confirmed: { text: 'Confirmed', cls: 'text-emerald bg-emerald/10' },
  pending: { text: 'Pending', cls: 'text-gold bg-gold/10' },
  pending_reply: { text: 'Pending', cls: 'text-gold bg-gold/10' },
  needs_reschedule: { text: 'Reschedule', cls: 'text-apricot bg-apricot/10' },
  rescheduling: { text: 'Reschedule', cls: 'text-apricot bg-apricot/10' },
  completed: { text: 'Completed', cls: 'text-tertiary bg-white/5' },
  cancelled: { text: 'Cancelled', cls: 'text-coral bg-coral/10' },
  'no-show': { text: 'No-show', cls: 'text-coral bg-coral/10' },
  no_show: { text: 'No-show', cls: 'text-coral bg-coral/10' },
}

function addMinutes(time, mins) {
  try {
    const [h, m] = time.split(':').map(Number)
    const total = h * 60 + m + mins
    const nh = Math.floor(total / 60)
    const nm = total % 60
    return `${String(nh).padStart(2, '0')}:${String(nm).padStart(2, '0')}`
  } catch {
    return time
  }
}

function AppointmentPopover({ appt, anchorRect, patients, onClose, onNavigate, onStub }) {
  const popoverRef = useRef(null)
  const [pos, setPos] = useState({ top: 0, left: 0, placement: 'right' })

  // Esc to close
  useEffect(() => {
    const handler = (e) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  // Click outside to close
  useEffect(() => {
    const handler = (e) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target)) onClose()
    }
    const t = setTimeout(() => window.addEventListener('mousedown', handler), 0)
    return () => {
      clearTimeout(t)
      window.removeEventListener('mousedown', handler)
    }
  }, [onClose])

  // Position with flip logic
  useEffect(() => {
    if (!anchorRect || !popoverRef.current) return
    const POP_W = 280
    const POP_H = popoverRef.current.offsetHeight || 180
    const margin = 8
    const vw = window.innerWidth
    const vh = window.innerHeight

    let left = anchorRect.right + margin
    let placement = 'right'
    if (left + POP_W > vw - 12) {
      left = anchorRect.left - POP_W - margin
      placement = 'left'
    }
    if (left < 12) left = 12

    let top = anchorRect.top
    if (top + POP_H > vh - 12) {
      top = Math.max(12, anchorRect.bottom - POP_H)
    }
    setPos({ top, left, placement })
  }, [anchorRect])

  const badge = statusLabel[appt.status] || statusLabel.pending
  const endTime = addMinutes(appt.time, appt.duration_mins || 30)
  const resolved = appt.patient_id && patients.find(p => p.id === appt.patient_id)

  return (
    <div
      ref={popoverRef}
      role="dialog"
      className="fixed z-50 w-[280px] bg-graphite border border-border-subtle rounded-xl shadow-xl p-4 animate-[count-up-fade_160ms_ease-out]"
      style={{ top: pos.top, left: pos.left }}
      data-testid="appt-popover"
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <h3 className="text-sm font-semibold text-primary tracking-tight truncate">{appt.patient_name}</h3>
        <button
          type="button"
          onClick={onClose}
          className="text-tertiary hover:text-secondary transition-all duration-200 ease-out active:scale-95 flex-shrink-0"
          aria-label="Close"
        >
          <X size={14} />
        </button>
      </div>
      <div className="h-px bg-border-subtle mb-2" />
      <div className="space-y-1">
        <p className="text-xs text-secondary">
          <span className="tabular-nums">{appt.time}–{endTime}</span>
          {' · '}
          <span className="text-tertiary">{appt.type || 'Consultation'}</span>
        </p>
        <div className="flex items-center gap-2">
          <span className="text-xs text-secondary">{appt.doctor_name || appt.doctor_id}</span>
          <span className={`text-[10px] px-2 py-0.5 rounded-full ${badge.cls}`}>{badge.text}</span>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 mt-4">
        {resolved ? (
          <button
            type="button"
            onClick={() => onNavigate(appt)}
            className="text-[11px] text-tertiary hover:text-mint px-2 py-1 rounded border border-border-subtle hover:border-mint/30 transition-all duration-200 ease-out active:scale-95"
            data-testid="popover-view-patient"
          >
            View Patient →
          </button>
        ) : (
          <span
            className="text-[11px] text-tertiary/40 px-2 py-1 rounded border border-border-subtle/50 cursor-default"
            title="Patient record unavailable"
            data-testid="popover-view-patient-disabled"
          >
            View Patient →
          </span>
        )}
        <button
          type="button"
          onClick={() => onStub('Reschedule')}
          className="text-[11px] text-tertiary hover:text-gold px-2 py-1 rounded border border-border-subtle hover:border-gold/30 transition-all duration-200 ease-out active:scale-95"
        >
          Reschedule
        </button>
        <button
          type="button"
          onClick={() => onStub('Cancel Appt')}
          className="text-[11px] text-tertiary hover:text-coral px-2 py-1 rounded border border-border-subtle hover:border-coral/30 transition-all duration-200 ease-out active:scale-95"
        >
          Cancel Appt
        </button>
      </div>
    </div>
  )
}

export default function CalendarView() {
  const { viewParams, setScreenContext, uiCommand, clearUiCommand, navigateTo, addActivity, trackAction } = useApp()
  const [data, setData] = useState(null)
  const [weekOffset, setWeekOffset] = useState(0)
  const [doctors, setDoctors] = useState([])
  const [selectedDoctor, setSelectedDoctor] = useState(viewParams?.doctorId || null)
  const [patients, setPatients] = useState([])
  const [popover, setPopover] = useState(null) // { appt, rect }
  const [unavailability, setUnavailability] = useState([]) // rows overlapping the current week

  // Load patients once (used to verify popover patient_id resolves)
  useEffect(() => {
    api.patients().then(d => setPatients(d.patients || d)).catch(() => setPatients([]))
  }, [])

  const handleApptClick = (appt, el) => {
    if (!el) return
    trackAction('view_appointment', appt.patient_name || '', 'appointment', appt.id)
    const rect = el.getBoundingClientRect()
    setPopover({ appt, rect: { top: rect.top, bottom: rect.bottom, left: rect.left, right: rect.right } })
  }

  const handlePopoverNavigate = (appt) => {
    setPopover(null)
    if (appt.patient_id) {
      trackAction('navigate_to_patient', appt.patient_name, 'patient', appt.patient_id)
      navigateTo('patients', { patientId: appt.patient_id, patientName: appt.patient_name, tab: 'appointments' })
    }
  }

  const handlePopoverStub = (label) => {
    addActivity({ id: `stub-${Date.now()}`, text: `${label} — not yet implemented`, active: true, icon: '◎' })
  }

  // Compute the Monday for the current offset
  const getMonday = useCallback((offset) => {
    const now = new Date()
    const day = now.getDay()
    const diff = day === 0 ? -6 : 1 - day
    const mon = new Date(now)
    mon.setDate(mon.getDate() + diff + offset * 7)
    return mon.toISOString().split('T')[0]
  }, [])

  // Fetch doctors list once
  useEffect(() => {
    api.doctors()
      .then(d => setDoctors(d.doctors || []))
      .catch(() => setDoctors([
        { id: 'dr-chen', name: 'Dr Sarah Chen', specialty: 'General Practice' },
        { id: 'dr-patel', name: 'Dr Raj Patel', specialty: 'General Practice' },
        { id: 'dr-kim', name: 'Dr Joon Kim', specialty: 'Paediatrics' },
        { id: 'dr-nguyen', name: 'Dr Mai Nguyen', specialty: "Women's Health" },
      ]))
  }, [])

  // On first load with no explicit doctorId nav param, default to the first doctor.
  // Only fires while selectedDoctor is still the initial null — never overrides a user's later "All" selection.
  useEffect(() => {
    if (selectedDoctor === null && doctors.length > 0 && !viewParams?.doctorId) {
      setSelectedDoctor(doctors[0].id)
    }
  }, [doctors, selectedDoctor, viewParams])

  // Fetch calendar data when week or doctor filter changes
  useEffect(() => {
    if (selectedDoctor === null) return
    const monday = getMonday(weekOffset)
    const doctorParam = selectedDoctor !== 'all' ? selectedDoctor : undefined
    const url = `/api/data/calendar?week=${monday}${doctorParam ? `&doctor_id=${doctorParam}` : ''}`
    fetch(url)
      .then(r => r.json())
      .then(setData)
      .catch(() => setData(getDemoCalendar()))
  }, [weekOffset, selectedDoctor, getMonday])

  // Fetch unavailability rows overlapping the visible week, for every doctor
  useEffect(() => {
    if (!doctors.length) return
    const monday = getMonday(weekOffset)
    const friday = (() => {
      const d = new Date(monday + 'T00:00:00')
      d.setDate(d.getDate() + 4)
      return d.toISOString().slice(0, 10)
    })()
    let cancelled = false
    Promise.all(
      doctors.map(doc =>
        api.doctorAvailabilityWindow(doc.id, monday, friday)
          .then(b => (b.unavailability || []).map(u => ({ ...u, doctor_name: doc.name })))
          .catch(() => [])
      )
    ).then(lists => {
      if (!cancelled) setUnavailability(lists.flat())
    })
    return () => { cancelled = true }
  }, [weekOffset, doctors, getMonday])

  const calendar = data || getDemoCalendar()
  const dayDates = getDayDates(calendar.week_start)

  // Compute per-cell unavailability overlay. Cells are keyed by (dayIndex, slotIndex).
  // When the user filters to a single doctor, only that doctor's overlays show.
  const overlayBySlot = (() => {
    const map = new Map() // key: `${dayIndex}-${slotIndex}` → { reason, doctors }
    if (!calendar.week_start) return map
    const monday = new Date(calendar.week_start + 'T00:00:00')
    const slotToTime = (slotIndex) => {
      const totalMin = slotIndex * 30 + 8 * 60 // grid starts at 8:00
      const h = Math.floor(totalMin / 60)
      const m = totalMin % 60
      return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
    }
    for (const row of unavailability) {
      if (selectedDoctor !== 'all' && row.doctor_id !== selectedDoctor) continue
      for (let di = 0; di < 5; di++) {
        const d = new Date(monday)
        d.setDate(d.getDate() + di)
        const dIso = d.toISOString().slice(0, 10)
        if (row.start_date > dIso || row.end_date < dIso) continue
        for (let si = 0; si < hours.length; si++) {
          const slotTime = slotToTime(si)
          // Full-day row: block all slots; partial: block if start_time <= slot < end_time
          const blocked = (!row.start_time && !row.end_time)
            || (row.start_time && row.end_time && row.start_time <= slotTime && slotTime < row.end_time)
          if (!blocked) continue
          const key = `${di}-${si}`
          const existing = map.get(key) || { reasons: [], doctors: [] }
          existing.reasons.push(row.reason)
          existing.doctors.push(row.doctor_name || row.doctor_id)
          map.set(key, existing)
        }
      }
    }
    return map
  })()

  // Update screen context for agent awareness
  useEffect(() => {
    if (selectedDoctor === null) return
    if (selectedDoctor !== 'all') {
      const doc = doctors.find(d => d.id === selectedDoctor)
      setScreenContext({ doctorId: selectedDoctor, doctorName: doc?.name || selectedDoctor })
    } else {
      setScreenContext(null)
    }
  }, [selectedDoctor, doctors, setScreenContext])

  // Respond to agent navigation with doctorId param
  useEffect(() => {
    if (viewParams?.doctorId && viewParams.doctorId !== selectedDoctor) {
      setSelectedDoctor(viewParams.doctorId)
    }
  }, [viewParams])

  // Handle agent UI commands
  useEffect(() => {
    if (!uiCommand) return
    if (uiCommand.command === 'select_doctor') {
      setSelectedDoctor(uiCommand.doctor_id)
      clearUiCommand()
    }
  }, [uiCommand, clearUiCommand])

  return (
    <div className="h-full flex flex-col p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-primary tracking-tight">Calendar</h1>
          <p className="text-sm text-tertiary">{formatWeekHeader(calendar.week_start)}</p>
        </div>
        <div className="flex items-center gap-3">
          {/* Week navigation */}
          <div className="flex items-center gap-1">
            <button
              onClick={() => setWeekOffset(w => w - 1)}
              className="w-8 h-8 rounded-lg flex items-center justify-center text-tertiary hover:text-secondary hover:bg-white/[0.04] transition-all duration-200 active:scale-95"
            >
              <ChevronLeft size={16} />
            </button>
            <button
              onClick={() => setWeekOffset(0)}
              className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-all duration-200 active:scale-95 ${
                weekOffset === 0
                  ? 'text-mint bg-mint/10'
                  : 'text-secondary bg-white/5 hover:bg-white/10'
              }`}
            >
              This week
            </button>
            <button
              onClick={() => setWeekOffset(w => w + 1)}
              className="w-8 h-8 rounded-lg flex items-center justify-center text-tertiary hover:text-secondary hover:bg-white/[0.04] transition-all duration-200 active:scale-95"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      </div>

      {/* Doctor filter pills */}
      {doctors.length > 0 && (
        <div className="flex items-center gap-2.5 mb-4">
          <button
            type="button"
            onClick={() => { setSelectedDoctor('all'); trackAction('filter_doctor', 'all', 'doctor', null) }}
            className={`flex items-center gap-2 text-sm px-3.5 py-1.5 rounded-md border transition-all duration-200 ease-out active:scale-95 ${
              selectedDoctor === 'all'
                ? 'border-mint/40 bg-mint/10 text-primary'
                : 'border-border-subtle text-tertiary hover:text-secondary'
            }`}
          >
            All
          </button>
          {doctors.map(d => {
            const c = doctorColors[d.id] || defaultColors
            const isActive = selectedDoctor === d.id
            return (
              <button
                key={d.id}
                type="button"
                onClick={() => { setSelectedDoctor(d.id); trackAction('filter_doctor', d.name, 'doctor', d.id) }}
                className={`flex items-center gap-2 text-sm px-3.5 py-1.5 rounded-md border transition-all duration-200 ease-out active:scale-95 ${
                  isActive
                    ? 'border-mint/40 bg-mint/10 text-primary'
                    : 'border-border-subtle text-tertiary hover:text-secondary'
                }`}
              >
                <span className={`w-2.5 h-2.5 rounded-full ${c.dot}`} />
                {d.name.replace('Dr ', '')}
              </button>
            )
          })}
        </div>
      )}

      {/* Grid */}
      <div className="flex-1 overflow-auto">
        <div className="grid grid-cols-[60px_repeat(5,1fr)] min-w-[700px]">
          {/* Header row */}
          <div className="sticky top-0 z-10 bg-void" />
          {dayLabels.map((day, i) => {
            const today = isToday(calendar.week_start, i)
            return (
              <div key={day} className={`sticky top-0 z-10 text-center py-2 text-xs font-medium border-b border-border-subtle
                ${today ? 'text-mint bg-mint/[0.02]' : 'text-tertiary bg-void'}`}>
                {day}
                <span className="block text-[10px] text-tertiary/60 mt-0.5">{dayDates[i]}</span>
              </div>
            )
          })}

          {/* Time slots */}
          {hours.map((time, ti) => (
            <div key={time} className="contents">
              <div className="text-[10px] text-tertiary/60 text-right pr-2 pt-1 h-14 border-t border-border-subtle/30">
                {time}
              </div>
              {dayLabels.map((day, di) => {
                const today = isToday(calendar.week_start, di)
                const cellAppts = calendar.appointments?.filter(a => a.day_index === di && a.slot_index === ti) || []
                const visibleAppts = cellAppts.length > 2 ? cellAppts.slice(0, 2) : cellAppts
                const overflowCount = cellAppts.length - visibleAppts.length
                const laneCount = visibleAppts.length || 1
                const overlay = overlayBySlot.get(`${di}-${ti}`)
                const reasonLabelText = (r) => r === 'sick' ? 'Sick leave' : r === 'leave' ? 'On leave' : 'Unavailable'
                const tooltip = overlay
                  ? overlay.doctors.map((n, i) => `${n} · ${reasonLabelText(overlay.reasons[i])}`).join(', ')
                  : null
                return (
                  <div
                    key={`${day}-${time}`}
                    className={`h-14 border-t border-l border-border-subtle/30 relative
                      ${today ? 'bg-mint/[0.01]' : ''}
                    `}
                  >
                    {overlay && (
                      <div
                        data-testid="calendar-unavailable-overlay"
                        aria-label={tooltip}
                        className="unavailable-stripe absolute inset-0 pointer-events-none group"
                      >
                        <span className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-150 bg-graphite/95 text-[10px] text-secondary flex items-center justify-center pointer-events-none border border-gold/30 rounded">
                          {tooltip}
                        </span>
                      </div>
                    )}
                    {visibleAppts.map((appt, ai) => (
                      <ApptBlock
                        key={ai}
                        appt={appt}
                        laneIndex={ai}
                        laneCount={laneCount}
                        onClick={handleApptClick}
                        isOpen={popover?.appt && (popover.appt.id === appt.id || (popover.appt === appt))}
                      />
                    ))}
                    {overflowCount > 0 && (
                      <span className="absolute bottom-0 right-1 text-[8px] text-tertiary font-medium">+{overflowCount}</span>
                    )}
                  </div>
                )
              })}
            </div>
          ))}
        </div>
      </div>

      {popover && (
        <AppointmentPopover
          appt={popover.appt}
          anchorRect={popover.rect}
          patients={patients}
          onClose={() => setPopover(null)}
          onNavigate={handlePopoverNavigate}
          onStub={handlePopoverStub}
        />
      )}
    </div>
  )
}

function getDemoCalendar() {
  return {
    week_start: '2026-04-06',
    week_end: '2026-04-10',
    appointments: [
      { patient_name: 'David Thompson', doctor_name: 'Dr Sarah Chen', doctor_id: 'dr-chen', day_index: 0, slot_index: 2, duration_mins: 30 },
      { patient_name: 'Aisha Rahman', doctor_name: 'Dr Sarah Chen', doctor_id: 'dr-chen', day_index: 0, slot_index: 4, duration_mins: 30 },
      { patient_name: 'Priya Sharma', doctor_name: 'Dr Raj Patel', doctor_id: 'dr-patel', day_index: 1, slot_index: 1, duration_mins: 30 },
      { patient_name: 'Margaret Wilson', doctor_name: 'Dr Sarah Chen', doctor_id: 'dr-chen', day_index: 2, slot_index: 2, duration_mins: 30 },
      { patient_name: 'Liam Walsh', doctor_name: 'Dr Joon Kim', doctor_id: 'dr-kim', day_index: 2, slot_index: 4, duration_mins: 45 },
      { patient_name: 'Emma Fitzgerald', doctor_name: 'Dr Mai Nguyen', doctor_id: 'dr-nguyen', day_index: 3, slot_index: 8, duration_mins: 30 },
      { patient_name: 'Ben O\'Sullivan', doctor_name: 'Dr Raj Patel', doctor_id: 'dr-patel', day_index: 4, slot_index: 1, duration_mins: 30 },
      { patient_name: 'Grace Taylor', doctor_name: 'Dr Mai Nguyen', doctor_id: 'dr-nguyen', day_index: 4, slot_index: 10, duration_mins: 30 },
    ],
  }
}
