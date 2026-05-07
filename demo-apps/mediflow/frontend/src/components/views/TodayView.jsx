import { useState, useEffect, useMemo } from 'react'
import { api } from '../../api/client'
import { useApp } from '../../context/AppContext'
import {
  Calendar, ChevronRight, Send, Bot, AlertTriangle, Stethoscope,
  ChevronUp, ChevronDown,
} from 'lucide-react'
import DonutChart from '../charts/DonutChart'
import LineChart from '../charts/LineChart'

const doctorColors = {
  'dr-chen': 'bg-mint',
  'dr-patel': 'bg-periwinkle',
  'dr-kim': 'bg-apricot',
  'dr-nguyen': 'bg-violet',
}

const statusBadge = {
  confirmed: { text: 'Confirmed', cls: 'text-emerald bg-emerald/10' },
  scheduled: { text: 'Confirmed', cls: 'text-emerald bg-emerald/10' },
  pending: { text: 'Pending', cls: 'text-gold bg-gold/10' },
  pending_reply: { text: 'Pending', cls: 'text-gold bg-gold/10' },
  needs_reschedule: { text: 'Reschedule', cls: 'text-apricot bg-apricot/10' },
  rescheduling: { text: 'Reschedule', cls: 'text-apricot bg-apricot/10' },
  completed: { text: 'Done', cls: 'text-tertiary bg-white/5' },
  cancelled: { text: 'Cancelled', cls: 'text-coral bg-coral/10' },
  no_show: { text: 'No-show', cls: 'text-coral bg-coral/10' },
  'no-show': { text: 'No-show', cls: 'text-coral bg-coral/10' },
}

const STATUS_COLORS = {
  confirmed: 'var(--color-emerald)',
  pending: 'var(--color-gold)',
  needs_reschedule: 'var(--color-apricot)',
  cancelled: 'var(--color-coral)',
  completed: 'var(--color-tertiary)',
}

const STATUS_LABELS = {
  confirmed: 'Confirmed',
  pending: 'Pending reply',
  needs_reschedule: 'Needs reschedule',
  cancelled: 'Cancelled',
  completed: 'Completed',
}

function formatDate() {
  const d = new Date()
  return d.toLocaleDateString('en-AU', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
}

function fmtMoney(v) {
  const n = Number(v) || 0
  return `$${n.toLocaleString('en-AU')}`
}

function ScheduleRow({ appt, onPatientClick }) {
  const dot = doctorColors[appt.doctor_id] || 'bg-mint'
  const badge = statusBadge[appt.status] || statusBadge.scheduled

  return (
    <div
      className="flex items-center gap-3 py-2.5 px-3 rounded-lg hover:bg-white/[0.02] transition-all duration-200 ease-out active:scale-95 cursor-pointer group"
      onClick={() => onPatientClick(appt)}
    >
      <span className="text-xs text-tertiary font-mono w-10 flex-shrink-0">{appt.time}</span>
      <span className={`w-2 h-2 rounded-full flex-shrink-0 ${dot}`} />
      <div className="flex-1 min-w-0">
        <p className="text-sm text-primary truncate">{appt.patient_name}</p>
        <p className="text-[11px] text-tertiary truncate">{appt.doctor_name} · {appt.type || 'Consultation'}</p>
      </div>
      <span className={`text-[10px] px-2 py-0.5 rounded-full flex-shrink-0 ${badge.cls}`}>{badge.text}</span>
      <ChevronRight size={14} className="text-tertiary/30 group-hover:text-tertiary transition-colors flex-shrink-0" />
    </div>
  )
}

function InvoiceRow({ row, onChase }) {
  const isOverdue = row.days_overdue > 30
  const daysLabel = row.days_overdue > 0
    ? `${row.days_overdue}d overdue`
    : row.days_overdue === 0
      ? 'due today'
      : `due in ${Math.abs(row.days_overdue)}d`
  return (
    <div className="flex items-center gap-3 py-2 rounded-lg hover:bg-white/[0.02] transition-all duration-200 ease-out group">
      <div className="flex-1 min-w-0 pl-1">
        <p className="text-sm text-primary truncate leading-tight">{row.patient_name}</p>
        <p className={`text-[11px] truncate leading-tight ${isOverdue ? 'text-coral' : 'text-secondary'}`}>{daysLabel}</p>
      </div>
      <span className={`text-sm font-semibold tabular-nums flex-shrink-0 ${isOverdue ? 'text-coral' : 'text-secondary'}`}>
        {fmtMoney(row.amount)}
      </span>
      <button
        onClick={() => onChase(row)}
        className="opacity-0 group-hover:opacity-100 flex items-center gap-1 text-[11px] text-mint font-medium px-2 py-1 rounded-md border border-mint/20 hover:bg-mint/10 transition-all duration-200 ease-out active:scale-95 flex-shrink-0"
      >
        <Send size={10} /> Chase
      </button>
    </div>
  )
}

function LegendPill({ color, label, count, muted, onClick, suffix, testId }) {
  return (
    <button
      type="button"
      onClick={onClick}
      data-testid={testId}
      className={`flex items-center gap-2 text-[11px] transition-all duration-200 ease-out ${onClick ? 'active:scale-95 cursor-pointer' : 'cursor-default'} ${muted ? 'opacity-40 line-through' : 'opacity-100'}`}
    >
      <span
        className="w-2.5 h-2.5 rounded-full flex-shrink-0"
        style={{ backgroundColor: color }}
      />
      <span className="text-secondary">{label}</span>
      {count != null && <span className="text-primary font-semibold tabular-nums">{count}</span>}
      {suffix && <span className="text-tertiary">{suffix}</span>}
    </button>
  )
}

function ReadyRow({ label, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      data-testid="ready-to-assist-row"
      className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-white/[0.03] transition-all duration-200 ease-out active:scale-95 text-left"
    >
      <span className="text-mint text-sm leading-none flex-shrink-0">◎</span>
      <span className="flex-1 text-sm text-primary truncate">{label}</span>
      <ChevronRight size={14} className="text-tertiary/50 flex-shrink-0" />
    </button>
  )
}

function reasonLabel(reason) {
  if (reason === 'sick') return 'sick leave'
  if (reason === 'leave') return 'on leave'
  return 'unavailable'
}

function ConflictCard({ conflicts, onReschedulePatient, onRescheduleAll }) {
  const [expanded, setExpanded] = useState(true)
  const [showAffected, setShowAffected] = useState(false)
  const count = conflicts?.length || 0
  if (count === 0) return null

  const headline = count === 1
    ? `${count} conflict today`
    : `${count} conflicts today`
  const primaryDoctorName = conflicts[0]?.doctor_name || ''
  const parts = primaryDoctorName.trim().split(/\s+/)
  const shortDoctorName = (parts.length >= 3 && /^Dr/i.test(parts[0]))
    ? `${parts[0]} ${parts[parts.length - 1]}`
    : primaryDoctorName

  return (
    <div
      data-testid="conflict-card"
      className="bg-graphite rounded-xl border border-gold/30 p-4 mb-6 animate-[count-up-fade_400ms_ease-out]"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-gold">
          <AlertTriangle size={14} />
          <h3 className="text-xs font-semibold tracking-widest uppercase">
            {headline}
            {!expanded && count === 1 && (
              <span className="text-secondary ml-2 normal-case tracking-normal">· {shortDoctorName}</span>
            )}
          </h3>
        </div>
        <button
          type="button"
          onClick={() => setExpanded(v => !v)}
          data-testid="conflict-card-toggle"
          className="flex items-center gap-1 text-[11px] text-tertiary hover:text-secondary transition-all duration-200 ease-out active:scale-95 px-2 py-1 rounded-md"
        >
          {expanded ? (<><ChevronUp size={12} /> Collapse</>) : (<><ChevronDown size={12} /> Expand</>)}
        </button>
      </div>

      {expanded && (
        <div className="flex flex-col gap-3 mt-3">
          {conflicts.map((c) => {
            const affected = c.affected_appointments || []
            const fullDay = !c.start_time && !c.end_time
            const windowLabel = fullDay ? 'full day' : `${c.start_time}–${c.end_time}`
            return (
              <div
                key={c.unavailability_id}
                data-testid="conflict-tile"
                className="bg-gold/5 border border-gold/20 rounded-lg p-3"
              >
                <div className="flex items-start gap-3">
                  <div className="w-8 h-8 rounded-full bg-gold/10 flex items-center justify-center text-gold flex-shrink-0">
                    <Stethoscope size={14} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-primary">
                      <span className="font-medium">{c.doctor_name}</span>
                      <span className="text-secondary"> unavailable today ({reasonLabel(c.reason)})</span>
                    </p>
                    <p className="text-[11px] text-tertiary mt-0.5">
                      {affected.length} appointment{affected.length === 1 ? '' : 's'} affected · {windowLabel}
                    </p>
                    <div className="flex items-center gap-2 mt-3">
                      <button
                        type="button"
                        data-testid="conflict-view-affected"
                        onClick={() => setShowAffected(v => !v)}
                        className="flex items-center gap-1.5 text-[11px] text-secondary border border-border-subtle rounded-md px-2.5 py-1.5 hover:text-primary hover:border-border-default transition-all duration-200 ease-out active:scale-95"
                      >
                        {showAffected ? 'Hide affected' : 'View affected'}
                      </button>
                      <button
                        type="button"
                        data-testid="conflict-reschedule-all"
                        onClick={() => onRescheduleAll(c)}
                        className="flex items-center gap-1.5 text-[11px] text-graphite bg-mint rounded-md px-2.5 py-1.5 font-medium hover:bg-mint/90 transition-all duration-200 ease-out active:scale-95"
                      >
                        <Bot size={12} /> Reschedule all
                      </button>
                    </div>
                  </div>
                </div>

                {showAffected && affected.length > 0 && (
                  <div
                    data-testid="conflict-affected-list"
                    className="mt-3 pt-3 border-t border-gold/20 flex flex-col divide-y divide-border-subtle/50"
                  >
                    {affected.map((a) => (
                      <div
                        key={a.id}
                        className="flex items-center gap-3 py-2 group"
                      >
                        <span className="text-xs text-tertiary font-mono w-10 flex-shrink-0">{a.time}</span>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm text-primary truncate">{a.patient_name}</p>
                          <p className="text-[11px] text-tertiary truncate">{a.type || 'Consultation'}</p>
                        </div>
                        <button
                          type="button"
                          onClick={() => onReschedulePatient(c, a)}
                          className="flex items-center gap-1 text-[11px] text-graphite bg-mint rounded-md px-2 py-1 font-medium hover:bg-mint/90 transition-all duration-200 ease-out active:scale-95"
                        >
                          <Bot size={10} /> Reschedule
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default function TodayView() {
  const { navigateTo, sendToAgent, trackAction } = useApp()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  // Weekly-trend legend toggles (both on by default)
  const [trendVisible, setTrendVisible] = useState({ this_week: true, last_week: true })

  // Doctor filter for the schedule widget (Set of doctor_ids; empty = all)
  const [doctorFilter, setDoctorFilter] = useState(() => new Set())
  const toggleDoctorFilter = (docId) => {
    setDoctorFilter(prev => {
      const next = new Set(prev)
      if (next.has(docId)) next.delete(docId)
      else next.add(docId)
      return next
    })
  }

  useEffect(() => {
    api.today().then(setData).catch(() => setData(getDemoData())).finally(() => setLoading(false))
  }, [])

  const d = data || getDemoData()

  const handlePatientClick = (appt) => { trackAction('view_patient_from_schedule', appt.patient_name, 'patient', appt.patient_id); navigateTo('patients', { patientId: appt.patient_id, patientName: appt.patient_name }) }
  const handleChase = (row) => { trackAction('chase_payment', row.patient_name, 'patient', row.patient_id); navigateTo('comms', { patientId: row.patient_id, patientName: row.patient_name, compose: true }) }

  const conflicts = d.conflicts || []

  // Convert "Dr Raj Patel" → "Dr Patel" for natural prompt phrasing
  const shortDoctor = (fullName) => {
    if (!fullName) return 'the doctor'
    const parts = fullName.trim().split(/\s+/)
    if (parts.length >= 3 && /^Dr/i.test(parts[0])) {
      return `${parts[0]} ${parts[parts.length - 1]}`
    }
    return fullName
  }

  const handleRescheduleAll = (conflict) => {
    const name = shortDoctor(conflict.doctor_name)
    trackAction('reschedule_all', conflict.doctor_name, 'doctor', null)
    sendToAgent(`${name} is out today — please reschedule all affected patients`)
  }

  const handleReschedulePatient = (conflict, appt) => {
    const name = shortDoctor(conflict.doctor_name)
    trackAction('reschedule_patient', appt.patient_name, 'patient', appt.patient_id)
    sendToAgent(`${name} is out today — please reschedule ${appt.patient_name} (${appt.time})`)
  }

  const handleSuggestion = (action) => {
    if (!action) return
    trackAction('today_suggestion', action.type, null, null)
    if (action.type === 'route') {
      navigateTo(action.view, action.params || null)
    } else if (action.type === 'prompt') {
      sendToAgent(action.text || '')
    }
  }

  // Derive appointment status counts from data (fallback to locally computed)
  const statusCounts = useMemo(() => {
    if (d.appointment_status_counts && Object.keys(d.appointment_status_counts).length > 0) {
      return d.appointment_status_counts
    }
    const counts = { confirmed: 0, pending: 0, needs_reschedule: 0, cancelled: 0, completed: 0 }
    for (const a of d.appointments || []) {
      const s = (a.status || '').toLowerCase()
      if (s === 'scheduled' || s === 'confirmed') counts.confirmed += 1
      else if (s === 'needs_reschedule' || s === 'rescheduling') counts.needs_reschedule += 1
      else if (s === 'cancelled' || s === 'no_show' || s === 'no-show') counts.cancelled += 1
      else if (s === 'completed') counts.completed += 1
      else counts.pending += 1
    }
    return counts
  }, [d])

  const apptSegments = [
    { value: statusCounts.confirmed || 0, color: STATUS_COLORS.confirmed, label: STATUS_LABELS.confirmed },
    { value: statusCounts.pending || 0, color: STATUS_COLORS.pending, label: STATUS_LABELS.pending },
    { value: statusCounts.needs_reschedule || 0, color: STATUS_COLORS.needs_reschedule, label: STATUS_LABELS.needs_reschedule },
    { value: statusCounts.cancelled || 0, color: STATUS_COLORS.cancelled, label: STATUS_LABELS.cancelled },
    { value: statusCounts.completed || 0, color: STATUS_COLORS.completed, label: STATUS_LABELS.completed },
  ]

  const rev = d.revenue_this_week || { paid: 0, outstanding: 0, overdue: 0, total: 0 }
  const revTotal = rev.total || 0
  const pct = (v) => revTotal > 0 ? Math.round((v / revTotal) * 100) : 0
  const revSegments = [
    { value: rev.paid || 0, color: 'var(--color-mint)', label: 'Paid' },
    { value: rev.outstanding || 0, color: 'var(--color-gold)', label: 'Outstanding' },
    { value: rev.overdue || 0, color: 'var(--color-coral)', label: 'Overdue' },
  ]

  const trend = d.weekly_trend || { this_week: [0, 0, 0, 0, 0], last_week: [0, 0, 0, 0, 0], delta: 0 }
  const trendSeries = [
    {
      name: 'this week',
      values: trend.this_week || [],
      color: 'var(--color-mint)',
      dashed: false,
      visible: trendVisible.this_week,
    },
    {
      name: 'last week',
      values: trend.last_week || [],
      color: 'var(--color-tertiary)',
      dashed: true,
      visible: trendVisible.last_week,
    },
  ]
  const thisWeekTotal = (trend.this_week || []).reduce((a, b) => a + b, 0)
  const deltaSign = (trend.delta || 0) >= 0 ? '+' : ''

  const appts = d.appointments || []
  const totalAppts = appts.length
  const filteredAppts = doctorFilter.size === 0
    ? appts
    : appts.filter(a => doctorFilter.has(a.doctor_id))
  const filteredCount = filteredAppts.length
  const invoices = d.invoices_outstanding || []
  const totalOutstanding = d.invoices_total_outstanding || 0
  const suggestions = (d.suggestions || []).slice(0, 3)

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="shimmer w-48 h-2 rounded-full" />
      </div>
    )
  }

  return (
    <div className="h-full p-6 overflow-auto">
      {/* Row 0 — Greeting */}
      <div
        data-testid="today-header"
        className="flex items-end justify-between mb-6"
      >
        <div>
          <h1 className="text-2xl font-semibold text-primary tracking-tight">Good morning</h1>
          <p className="text-sm text-tertiary mt-0.5">{formatDate()}</p>
        </div>
      </div>

      {/* Row 1 — Appointment Status + Invoices */}
      <div className="grid grid-cols-6 gap-6 mb-6">
        {/* W1 — Appointment Status */}
        <div
          data-testid="widget-appt-status"
          className="col-span-3 bg-graphite rounded-xl border border-border-subtle p-4 flex flex-col"
        >
          <h3 className="text-xs font-semibold text-tertiary tracking-widest uppercase mb-3">
            Today's Appointments <span className="text-primary">(</span><span className="text-primary">{totalAppts}</span><span className="text-primary">)</span>
          </h3>
          <div className="flex-1 flex items-center justify-center gap-8">
            <DonutChart
              size={260}
              strokeWidth={26}
              segments={apptSegments}
              centerLabel={
                <div className="flex flex-col items-center">
                  <span className="text-4xl font-semibold text-primary tracking-tight leading-none tabular-nums">{totalAppts}</span>
                  <span className="text-[10px] text-tertiary mt-1.5 tracking-widest uppercase">today</span>
                </div>
              }
            />
            <div className="flex flex-col gap-2">
              {apptSegments.map((seg) => (
                <LegendPill
                  key={seg.label}
                  color={seg.color}
                  label={seg.label}
                  count={seg.value}
                />
              ))}
            </div>
          </div>
        </div>

        {/* W2 — Invoice Follow-up */}
        <div
          data-testid="widget-invoices"
          className="col-span-3 bg-graphite rounded-xl border border-border-subtle p-4"
        >
          <h3 className="text-xs font-semibold text-tertiary tracking-widest uppercase mb-3">
            Invoice Follow-up <span className="text-primary">(</span><span className="text-primary normal-case tracking-normal">{fmtMoney(totalOutstanding)}</span><span className="text-primary normal-case tracking-normal ml-1">outstanding</span><span className="text-primary">)</span>
          </h3>
          {invoices.length === 0 ? (
            <div className="py-6 text-center text-tertiary text-sm">No outstanding invoices</div>
          ) : (
            <div className="flex flex-col">
              {invoices.map((inv) => (
                <InvoiceRow key={inv.id} row={inv} onChase={handleChase} />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Row 2 — Revenue + Weekly Trend */}
      <div className="grid grid-cols-6 gap-6 mb-6">
        {/* W3 — Revenue Snapshot */}
        <div
          data-testid="widget-revenue"
          className="col-span-3 bg-graphite rounded-xl border border-border-subtle p-4 flex flex-col"
        >
          <h3 className="text-xs font-semibold text-tertiary tracking-widest uppercase mb-3">
            Revenue Snapshot <span className="text-primary">(</span><span className="text-primary normal-case tracking-normal">{fmtMoney(revTotal)}</span><span className="text-primary">)</span>
          </h3>
          <div className="flex-1 flex items-center justify-center gap-8">
            <DonutChart
              size={260}
              strokeWidth={26}
              segments={revSegments}
              centerLabel={
                <div className="flex flex-col items-center">
                  <span className="text-2xl font-semibold text-primary tracking-tight leading-none tabular-nums">{fmtMoney(revTotal)}</span>
                  <span className="text-[10px] text-tertiary mt-1.5 tracking-widest uppercase">total</span>
                </div>
              }
            />
            <div className="flex flex-col gap-2">
              <LegendPill color="var(--color-mint)" label="Paid" count={fmtMoney(rev.paid)} suffix={`(${pct(rev.paid)}%)`} />
              <LegendPill color="var(--color-gold)" label="Outstanding" count={fmtMoney(rev.outstanding)} suffix={`(${pct(rev.outstanding)}%)`} />
              <LegendPill color="var(--color-coral)" label="Overdue" count={fmtMoney(rev.overdue)} suffix={`(${pct(rev.overdue)}%)`} />
            </div>
          </div>
        </div>

        {/* W4 — Weekly Appointments Trend */}
        <div
          data-testid="widget-trend"
          className="col-span-3 bg-graphite rounded-xl border border-border-subtle p-4 flex flex-col"
        >
          <div className="flex items-baseline justify-between mb-3">
            <h3 className="text-xs font-semibold text-tertiary tracking-widest uppercase">Weekly Appointments</h3>
            <span className="text-sm font-semibold text-primary tabular-nums">
              {thisWeekTotal}{' '}
              <span className={`text-[11px] font-normal ${trend.delta >= 0 ? 'text-emerald' : 'text-coral'}`}>
                ({deltaSign}{trend.delta} vs last week)
              </span>
            </span>
          </div>
          <div className="flex-1 flex items-stretch min-h-0">
            <LineChart
              height={280}
              labels={['Mon', 'Tue', 'Wed', 'Thu', 'Fri']}
              series={trendSeries}
            />
          </div>
          <div className="flex items-center gap-4 mt-2 px-1">
            <LegendPill
              testId="trend-legend-this-week"
              color="var(--color-mint)"
              label="this week"
              muted={!trendVisible.this_week}
              onClick={() => setTrendVisible(v => ({ ...v, this_week: !v.this_week }))}
            />
            <LegendPill
              testId="trend-legend-last-week"
              color="var(--color-tertiary)"
              label="last week"
              muted={!trendVisible.last_week}
              onClick={() => setTrendVisible(v => ({ ...v, last_week: !v.last_week }))}
            />
          </div>
        </div>
      </div>

      {/* Row 3 — Today's Schedule */}
      <div
        data-testid="widget-schedule"
        className="bg-graphite rounded-xl border border-border-subtle p-4 mb-6"
      >
        <div className="flex items-baseline justify-between mb-3">
          <h3 className="text-xs font-semibold text-tertiary tracking-widest uppercase flex items-center gap-2">
            <Calendar size={12} /> Today's Schedule <span className="text-primary">(</span><span className="text-primary">{filteredCount}{doctorFilter.size > 0 ? ` of ${totalAppts}` : ''}</span><span className="text-primary">)</span>
          </h3>
          {doctorFilter.size > 0 && (
            <button
              onClick={() => setDoctorFilter(new Set())}
              className="text-[10px] text-tertiary hover:text-secondary transition-all duration-200 ease-out active:scale-95"
            >
              Clear
            </button>
          )}
        </div>
        <div className="flex flex-col divide-y divide-border-subtle/50 overflow-y-auto" style={{ maxHeight: 380 }}>
          {filteredAppts.length === 0 ? (
            <div className="py-8 text-center text-tertiary text-sm">
              {doctorFilter.size > 0 ? 'No appointments match this filter' : 'No appointments scheduled today'}
            </div>
          ) : (
            filteredAppts.map((a, i) => (
              <ScheduleRow key={a.id || i} appt={a} onPatientClick={handlePatientClick} />
            ))
          )}
        </div>
        {/* Doctor legend — clickable filter toggles */}
        <div className="flex items-center gap-2 mt-3 px-1 flex-wrap">
          {[
            { id: 'dr-chen', name: 'Dr Chen' },
            { id: 'dr-patel', name: 'Dr Patel' },
            { id: 'dr-kim', name: 'Dr Kim' },
            { id: 'dr-nguyen', name: 'Dr Nguyen' },
          ].map(doc => {
            const isActive = doctorFilter.has(doc.id)
            const anyActive = doctorFilter.size > 0
            const isDimmed = anyActive && !isActive
            return (
              <button
                key={doc.id}
                type="button"
                onClick={() => toggleDoctorFilter(doc.id)}
                className={`flex items-center gap-1.5 text-[10px] px-2 py-1 rounded-md border transition-all duration-200 ease-out active:scale-95 ${
                  isActive
                    ? 'border-mint/40 bg-mint/10 text-primary'
                    : isDimmed
                      ? 'border-border-subtle/50 text-tertiary/40 hover:text-tertiary'
                      : 'border-border-subtle text-tertiary hover:text-secondary hover:border-border-subtle'
                }`}
              >
                <span className={`w-2 h-2 rounded-full ${doctorColors[doc.id]} ${isDimmed ? 'opacity-40' : ''}`} />
                {doc.name}
              </button>
            )
          })}
        </div>
      </div>

      {/* Row 4 — Ready to Assist */}
      {suggestions.length > 0 && (
        <div
          data-testid="widget-ready"
          className="bg-graphite rounded-xl border border-border-subtle p-4"
        >
          <h3 className="text-xs font-semibold text-tertiary tracking-widest uppercase mb-2">Ready to Assist</h3>
          <div className="flex flex-col">
            {suggestions.map((s, i) => (
              <ReadyRow key={i} label={s.label} onClick={() => handleSuggestion(s.action)} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Demo fallback data — matches new API shape
// ---------------------------------------------------------------------------

function getDemoData() {
  return {
    appointments: [
      { id: '1', time: '09:00', patient_id: 'p1', patient_name: 'Sarah Johnson', doctor_name: 'Dr Chen', doctor_id: 'dr-chen', type: 'General', status: 'confirmed' },
      { id: '2', time: '09:30', patient_id: 'p2', patient_name: 'James Wilson', doctor_name: 'Dr Chen', doctor_id: 'dr-chen', type: 'Follow-up', status: 'confirmed' },
      { id: '3', time: '10:00', patient_id: 'p3', patient_name: 'Maria Garcia', doctor_name: 'Dr Patel', doctor_id: 'dr-patel', type: 'New Patient', status: 'pending' },
      { id: '4', time: '10:30', patient_id: 'p4', patient_name: 'Robert MacLeod', doctor_name: 'Dr Chen', doctor_id: 'dr-chen', type: 'General', status: 'confirmed' },
      { id: '5', time: '11:00', patient_id: 'p5', patient_name: 'Emily Davis', doctor_name: 'Dr Patel', doctor_id: 'dr-patel', type: 'Review', status: 'confirmed' },
      { id: '6', time: '11:30', patient_id: 'p6', patient_name: 'Thomas Brown', doctor_name: 'Dr Chen', doctor_id: 'dr-chen', type: 'General', status: 'confirmed' },
      { id: '7', time: '13:30', patient_id: 'p-priya', patient_name: 'Priya Sharma', doctor_name: 'Dr Patel', doctor_id: 'dr-patel', type: 'Follow-up', status: 'pending' },
      { id: '8', time: '14:00', patient_id: 'p7', patient_name: 'Lisa Wang', doctor_name: 'Dr Kim', doctor_id: 'dr-kim', type: 'Paediatric check', status: 'confirmed' },
      { id: '9', time: '14:30', patient_id: 'p8', patient_name: 'Michael Taylor', doctor_name: 'Dr Nguyen', doctor_id: 'dr-nguyen', type: 'General', status: 'needs_reschedule' },
      { id: '10', time: '15:00', patient_id: 'p-aisha', patient_name: 'Aisha Rahman', doctor_name: 'Dr Patel', doctor_id: 'dr-patel', type: 'General', status: 'pending' },
      { id: '11', time: '15:30', patient_id: 'p-david', patient_name: 'David Torres', doctor_name: 'Dr Chen', doctor_id: 'dr-chen', type: 'Follow-up', status: 'cancelled' },
      { id: '12', time: '16:00', patient_id: 'p-emma', patient_name: 'Emma Fitzgerald', doctor_name: 'Dr Kim', doctor_id: 'dr-kim', type: 'General', status: 'confirmed' },
    ],
    tasks: [],
    stats: {
      patients_today: 12,
      revenue_today: 1240,
      no_shows: 0,
      outstanding: 2850,
    },
    appointment_status_counts: {
      confirmed: 7,
      pending: 3,
      needs_reschedule: 1,
      cancelled: 1,
      completed: 0,
    },
    invoices_outstanding: [
      { id: 'inv-1847', patient_id: 'p4', patient_name: 'Robert MacLeod', amount: 175, due_date: '2026-03-09', days_overdue: 42, status: 'overdue' },
      { id: 'inv-1902', patient_id: 'p-aisha', patient_name: 'Aisha Rahman', amount: 420, due_date: '2026-03-30', days_overdue: 21, status: 'overdue' },
      { id: 'inv-1945', patient_id: 'p-priya', patient_name: 'Priya Sharma', amount: 85, due_date: '2026-04-06', days_overdue: 14, status: 'outstanding' },
      { id: 'inv-1978', patient_id: 'p2', patient_name: 'James Wilson', amount: 240, due_date: '2026-04-13', days_overdue: 7, status: 'outstanding' },
      { id: 'inv-1992', patient_id: 'p-emma', patient_name: 'Emma Fitzgerald', amount: 110, due_date: '2026-04-17', days_overdue: 3, status: 'outstanding' },
    ],
    invoices_total_outstanding: 2850,
    revenue_this_week: {
      paid: 8240,
      outstanding: 2850,
      overdue: 420,
      total: 11510,
    },
    weekly_trend: {
      this_week: [9, 12, 11, 10, 5],
      last_week: [8, 10, 8, 9, 4],
      delta: 8,
    },
    suggestions: [
      {
        label: 'Send appointment reminders for tomorrow',
        action: { type: 'prompt', text: 'Send appointment reminders to all patients with appointments tomorrow' },
      },
      {
        label: 'Follow up on 5 outstanding invoices',
        action: { type: 'route', view: 'patients', params: { filter: 'outstanding' } },
      },
      {
        label: 'Check in with patients who flagged concerns',
        action: { type: 'prompt', text: 'Show me patients whose recent notes flagged concerns and draft check-in messages' },
      },
    ],
  }
}
