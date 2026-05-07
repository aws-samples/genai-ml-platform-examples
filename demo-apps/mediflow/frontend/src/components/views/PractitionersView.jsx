import { useState, useEffect, useRef } from 'react'
import { api } from '../../api/client'
import { useApp } from '../../context/AppContext'
import { Search, Clock, Users, Calendar, TrendingUp, AlertTriangle, Plus, X } from 'lucide-react'

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
  'no-show': 'bg-gold/10 text-gold',
}

const doctorAccent = {
  'dr-chen': 'mint',
  'dr-patel': 'periwinkle',
  'dr-kim': 'apricot',
  'dr-nguyen': 'violet',
}

function formatWorkingDays(days) {
  if (!days || !Array.isArray(days)) return ''
  const abbrevs = { Monday: 'Mon', Tuesday: 'Tue', Wednesday: 'Wed', Thursday: 'Thu', Friday: 'Fri' }
  return days.map(d => abbrevs[d] || d.slice(0, 3)).join(', ')
}

export default function PractitionersView() {
  const { navigateTo, setScreenContext, uiCommand, clearUiCommand, agentHighlight, trackAction } = useApp()
  const [doctors, setDoctors] = useState([])
  const [selected, setSelected] = useState(null)
  const [detail, setDetail] = useState(null)
  const [detailTab, setDetailTab] = useState('schedule')
  const [search, setSearch] = useState('')

  // Fetch doctors list
  useEffect(() => {
    api.doctors()
      .then(d => setDoctors(d.doctors || []))
      .catch(() => setDoctors(getDemoDoctors()))
  }, [])

  // Fetch doctor detail when selected
  useEffect(() => {
    if (selected) {
      api.doctor(selected)
        .then(setDetail)
        .catch(() => {
          const d = getDemoDoctors().find(d => d.id === selected)
          setDetail(d ? { ...d, ...getDemoDetail() } : null)
        })
    }
  }, [selected])

  // Update screen context for agent awareness
  useEffect(() => {
    if (detail) {
      setScreenContext({ doctorId: detail.id, doctorName: detail.name, specialty: detail.specialty, tab: detailTab })
    } else {
      setScreenContext(null)
    }
  }, [detail, detailTab, setScreenContext])

  // Handle agent UI commands
  useEffect(() => {
    if (!uiCommand) return
    if (uiCommand.command === 'select_doctor') {
      setSelected(uiCommand.doctor_id)
      clearUiCommand()
    } else if (uiCommand.command === 'set_doctor_tab') {
      if (uiCommand.doctor_id) setSelected(uiCommand.doctor_id)
      if (uiCommand.tab) setDetailTab(uiCommand.tab)
      clearUiCommand()
    }
    // Form-driving commands (open_time_off_form, fill_time_off_form,
    // submit_time_off_form) are consumed inside AvailabilityTab.
  }, [uiCommand, clearUiCommand])

  const filtered = doctors.filter(d =>
    !search || d.name.toLowerCase().includes(search.toLowerCase()) || d.specialty.toLowerCase().includes(search.toLowerCase())
  )
  const list = filtered.length ? filtered : getDemoDoctors()

  return (
    <div className="h-full flex">
      {/* Doctor List */}
      <div className="w-[320px] flex-shrink-0 bg-slate border-r border-border-subtle flex flex-col">
        <div className="p-3">
          <div className="flex items-center gap-2 bg-ash rounded-xl px-3 py-2 border border-border-subtle focus-within:border-border-active transition-colors">
            <Search size={14} className="text-tertiary flex-shrink-0" />
            <input
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search practitioners..."
              className="flex-1 bg-transparent text-sm text-primary placeholder:text-tertiary outline-none"
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {list.map(d => {
            const isActive = selected === d.id
            const initials = d.name.replace('Dr ', '').split(' ').map(w => w[0]).join('').toUpperCase()
            const accent = doctorAccent[d.id] || 'mint'
            const isListHighlighted = agentHighlight?.target === 'list_item' && agentHighlight?.id === d.id
            return (
              <button
                key={d.id}
                onClick={() => { setSelected(d.id); trackAction('view_doctor_detail', d.name, 'doctor', d.id) }}
                className={`w-full text-left px-3 py-3 flex items-center gap-3 border-l-2 transition-all
                  ${isListHighlighted ? 'agent-blink' : ''}
                  ${isActive
                    ? 'bg-mint/5 border-l-mint'
                    : 'border-l-transparent hover:bg-white/[0.02]'
                  }`}
              >
                <div className="w-10 h-10 rounded-xl flex items-center justify-center text-xs font-semibold flex-shrink-0" style={avatarStyle(d.name)}>
                  {initials}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-primary text-sm font-medium truncate">{d.name}</p>
                  <p className="text-tertiary text-xs">{d.specialty}</p>
                  <p className="text-tertiary/60 text-[10px] mt-0.5">{formatWorkingDays(d.working_days)}</p>
                </div>
                <div className="flex flex-col items-end gap-1 flex-shrink-0">
                  {d.appointments_today > 0 && (
                    <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-${accent}/10 text-${accent}`}>
                      {d.appointments_today} today
                    </span>
                  )}
                </div>
              </button>
            )
          })}
        </div>
      </div>

      {/* Detail */}
      <div className="flex-1 overflow-auto p-6">
        {!selected || !detail ? (
          <div className="h-full flex items-center justify-center text-tertiary text-sm">
            Select a practitioner to view details
          </div>
        ) : (
          <div key={selected} className="content-enter">
            {/* Header */}
            <div className="flex items-start gap-4 mb-5">
              <div className="w-14 h-14 rounded-2xl flex items-center justify-center text-lg font-semibold" style={avatarStyle(detail.name)}>
                {detail.name.replace('Dr ', '').split(' ').map(w => w[0]).join('').toUpperCase()}
              </div>
              <div>
                <h2 className="text-xl font-semibold text-primary tracking-tight">{detail.name}</h2>
                <p className="text-secondary text-sm">{detail.specialty}</p>
                <div className="flex items-center gap-4 mt-1 text-xs text-tertiary">
                  <span className="flex items-center gap-1"><Clock size={11} /> {detail.hours_start} – {detail.hours_end}</span>
                  <span className="flex items-center gap-1"><Calendar size={11} /> {formatWorkingDays(detail.working_days)}</span>
                  <span className="text-tertiary/60">{detail.consultation_duration_mins}min consultations</span>
                </div>
              </div>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-3 gap-3 mb-5">
              <StatCard
                label="This Week"
                value={detail.schedule?.length || 0}
                sub="appointments"
                icon={Calendar}
              />
              <StatCard
                label="This Month"
                value={detail.patients_this_month || 0}
                sub="patients seen"
                icon={Users}
              />
              <StatCard
                label="No-show Rate"
                value={`${detail.no_show_rate || 0}%`}
                sub="all time"
                icon={TrendingUp}
                alert={detail.no_show_rate > 10}
              />
            </div>

            {/* Action buttons */}
            <div className="flex items-center gap-2 mb-5">
              <button
                onClick={() => { trackAction('view_doctor_calendar', detail.name, 'doctor', detail.id); navigateTo('calendar', { doctorId: detail.id }) }}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-mint bg-mint/10 hover:bg-mint/15 transition-all duration-200 active:scale-95"
              >
                <Calendar size={12} /> View Calendar
              </button>
            </div>

            {/* Tabs */}
            <div className="flex gap-6 border-b border-border-subtle mb-4">
              {['schedule', 'patients', 'availability'].map(tab => (
                <button
                  key={tab}
                  onClick={() => setDetailTab(tab)}
                  data-testid={`practitioner-tab-${tab}`}
                  className={`pb-2 text-sm font-medium capitalize border-b-2 transition-all duration-200 ease-out active:scale-95
                    ${detailTab === tab
                      ? 'text-mint border-mint'
                      : 'text-tertiary border-transparent hover:text-secondary'
                    }`}
                >
                  {tab}
                </button>
              ))}
            </div>

            {/* Tab content */}
            <div key={detailTab} className="content-enter space-y-2">
              {detailTab === 'schedule' && (
                (detail.schedule || []).length === 0 ? (
                  <p className="text-tertiary text-sm py-4 text-center">No appointments this week</p>
                ) : (
                  (detail.schedule || []).map((a, i) => (
                    <div key={i} className="bg-graphite rounded-xl border border-border-subtle p-3 flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <Calendar size={14} className="text-tertiary" />
                        <div>
                          <p className="text-sm text-primary">{a.date} at {a.time}</p>
                          <p className="text-xs text-tertiary">
                            {a.patient_id ? (
                              <button
                                type="button"
                                onClick={() => navigateTo('patients', { patientId: a.patient_id, patientName: a.patient_name })}
                                className="text-mint hover:text-mint/80 transition-all duration-200 ease-out active:scale-95"
                              >
                                {a.patient_name}
                              </button>
                            ) : (
                              <span>{a.patient_name}</span>
                            )}
                            {' · '}{a.type}
                          </p>
                        </div>
                      </div>
                      <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase tracking-wider ${statusPill[a.status] || ''}`}>
                        {a.status}
                      </span>
                    </div>
                  ))
                )
              )}

              {detailTab === 'patients' && (
                (detail.patients || []).length === 0 ? (
                  <p className="text-tertiary text-sm py-4 text-center">No patient history</p>
                ) : (
                  (detail.patients || []).map((p, i) => {
                    const name = `${p.first_name} ${p.last_name}`
                    const initials = `${(p.first_name || '')[0]}${(p.last_name || '')[0]}`.toUpperCase()
                    return (
                      <button
                        key={i}
                        type="button"
                        onClick={() => p.id && navigateTo('patients', { patientId: p.id, patientName: name })}
                        disabled={!p.id}
                        className="w-full text-left bg-graphite rounded-xl border border-border-subtle p-3 flex items-center gap-3 transition-all duration-200 ease-out active:scale-95 hover:border-border-glow disabled:cursor-default"
                      >
                        <div className="w-8 h-8 rounded-full flex items-center justify-center text-[10px] font-semibold flex-shrink-0" style={avatarStyle(name)}>
                          {initials}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm text-primary truncate">{name}</p>
                          <p className="text-xs text-tertiary">Last seen: {p.last_seen || 'N/A'}</p>
                        </div>
                      </button>
                    )
                  })
                )
              )}
              {detailTab === 'availability' && (
                <AvailabilityTab
                  doctor={detail}
                  onRefresh={() => {
                    // Re-fetch the doctor detail so recurring hours persist across reloads
                    api.doctor(detail.id).then(setDetail).catch(() => {})
                  }}
                />
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function AvailabilityTab({ doctor, onRefresh }) {
  const { uiCommand, clearUiCommand, agentHighlight } = useApp()
  const DAY_ORDER = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
  const [unavailability, setUnavailability] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [editingRecurring, setEditingRecurring] = useState(false)
  const [addingTimeOff, setAddingTimeOff] = useState(false)

  // Recurring-schedule edit form state
  const [editDays, setEditDays] = useState(() => new Set(doctor.working_days || []))
  const [editStart, setEditStart] = useState(doctor.hours_start || '09:00')
  const [editEnd, setEditEnd] = useState(doctor.hours_end || '17:00')
  const [editDuration, setEditDuration] = useState(doctor.consultation_duration_mins || 30)

  // Add-time-off form state
  const today = new Date().toISOString().slice(0, 10)
  const [toStart, setToStart] = useState(today)
  const [toEnd, setToEnd] = useState(today)
  const [toReason, setToReason] = useState('sick')
  const [toPartial, setToPartial] = useState(false)
  const [toStartTime, setToStartTime] = useState('12:00')
  const [toEndTime, setToEndTime] = useState('14:00')
  const [toNote, setToNote] = useState('')
  const [formError, setFormError] = useState('')
  const submitTimeOffRef = useRef(null)

  const fetchUnavail = () => {
    const start = today
    const endD = new Date()
    endD.setDate(endD.getDate() + 90)
    const end = endD.toISOString().slice(0, 10)
    setLoading(true)
    api.doctorAvailabilityWindow(doctor.id, start, end)
      .then((body) => {
        setUnavailability(body.unavailability || [])
        setError('')
      })
      .catch(() => {
        setError('Could not load time off')
        setUnavailability([])
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchUnavail()
    setEditDays(new Set(doctor.working_days || []))
    setEditStart(doctor.hours_start || '09:00')
    setEditEnd(doctor.hours_end || '17:00')
    setEditDuration(doctor.consultation_duration_mins || 30)
    setEditingRecurring(false)
    setAddingTimeOff(false)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [doctor.id])

  // Accept agent-driven form commands: open / fill / submit.
  useEffect(() => {
    if (!uiCommand) return
    if (uiCommand.doctor_id && uiCommand.doctor_id !== doctor.id) return

    if (uiCommand.command === 'open_time_off_form') {
      setAddingTimeOff(true)
      clearUiCommand()
    } else if (uiCommand.command === 'fill_time_off_form') {
      const f = uiCommand.fields || {}
      if (f.start_date) setToStart(f.start_date)
      if (f.end_date) setToEnd(f.end_date)
      if (f.reason) setToReason(f.reason)
      if (typeof f.note === 'string') setToNote(f.note)
      if (f.partial !== undefined) setToPartial(!!f.partial)
      if (f.start_time) setToStartTime(f.start_time)
      if (f.end_time) setToEndTime(f.end_time)
      clearUiCommand()
    } else if (uiCommand.command === 'submit_time_off_form') {
      // Defer to next tick so any preceding fill_time_off_form render lands first
      clearUiCommand()
      setTimeout(() => { submitTimeOffRef.current?.() }, 50)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uiCommand, doctor.id])

  const toggleDay = (day) => {
    setEditDays(prev => {
      const next = new Set(prev)
      if (next.has(day)) next.delete(day)
      else next.add(day)
      return next
    })
  }

  const saveRecurring = async () => {
    try {
      await api.patchDoctor(doctor.id, {
        working_days: DAY_ORDER.filter(d => editDays.has(d)),
        hours_start: editStart,
        hours_end: editEnd,
        consultation_duration_mins: Number(editDuration) || 30,
      })
      setEditingRecurring(false)
      onRefresh?.()
    } catch {
      setError('Could not save schedule')
    }
  }

  const submitTimeOff = async () => {
    setFormError('')
    try {
      const body = {
        start_date: toStart,
        end_date: toEnd || toStart,
        reason: toReason,
        created_by: 'user',
      }
      if (toPartial) {
        body.start_time = toStartTime
        body.end_time = toEndTime
      }
      if (toNote) body.note = toNote
      await api.createDoctorUnavailability(doctor.id, body)
      setAddingTimeOff(false)
      setToStart(today); setToEnd(today); setToReason('sick')
      setToPartial(false); setToStartTime('12:00'); setToEndTime('14:00'); setToNote('')
      fetchUnavail()
    } catch {
      setFormError('Could not save — please check the form and try again')
    }
  }

  // Expose latest submitTimeOff through a ref so the ui-command effect
  // doesn't close over stale state.
  submitTimeOffRef.current = submitTimeOff

  const clearRow = async (row) => {
    try {
      await api.deleteDoctorUnavailability(doctor.id, row.id)
      fetchUnavail()
    } catch {
      setError('Could not clear time off')
    }
  }

  return (
    <div data-testid="availability-tab" className="flex flex-col gap-5">
      {/* Recurring schedule */}
      <section className="bg-graphite rounded-xl border border-border-subtle p-4">
        <div className="flex items-center justify-between mb-3">
          <h4 className="text-xs font-semibold text-tertiary tracking-widest uppercase">Recurring schedule</h4>
          {!editingRecurring && (
            <button
              type="button"
              data-testid="recurring-edit-btn"
              onClick={() => { setEditingRecurring(true); trackAction('edit_recurring_schedule', detail?.name || '', 'doctor', selected) }}
              className="text-[11px] text-mint border border-mint/20 rounded-md px-2 py-1 hover:bg-mint/10 transition-all duration-200 ease-out active:scale-95"
            >
              Edit
            </button>
          )}
        </div>

        {!editingRecurring ? (
          <div className="flex flex-col gap-1 text-sm">
            <p className="text-primary">
              {formatWorkingDays(doctor.working_days)}
              <span className="text-tertiary"> · {doctor.hours_start} – {doctor.hours_end}</span>
            </p>
            <p className="text-tertiary text-xs">{doctor.consultation_duration_mins} min consultations</p>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap gap-1.5">
              {DAY_ORDER.map(day => {
                const active = editDays.has(day)
                return (
                  <button
                    key={day}
                    type="button"
                    onClick={() => toggleDay(day)}
                    className={`text-[11px] px-2.5 py-1 rounded-md border transition-all duration-200 ease-out active:scale-95
                      ${active
                        ? 'border-mint/40 bg-mint/10 text-primary'
                        : 'border-border-subtle text-tertiary hover:text-secondary'}`}
                  >
                    {day.slice(0, 3)}
                  </button>
                )
              })}
            </div>
            <div className="flex items-center gap-3 flex-wrap">
              <label className="text-[11px] text-tertiary flex items-center gap-1.5">
                Start
                <input
                  type="time"
                  value={editStart}
                  onChange={e => setEditStart(e.target.value)}
                  className="bg-ash border border-border-subtle rounded px-2 py-1 text-sm text-primary"
                />
              </label>
              <label className="text-[11px] text-tertiary flex items-center gap-1.5">
                End
                <input
                  type="time"
                  value={editEnd}
                  onChange={e => setEditEnd(e.target.value)}
                  className="bg-ash border border-border-subtle rounded px-2 py-1 text-sm text-primary"
                />
              </label>
              <label className="text-[11px] text-tertiary flex items-center gap-1.5">
                Duration
                <input
                  type="number"
                  min={5}
                  max={240}
                  step={5}
                  value={editDuration}
                  onChange={e => setEditDuration(e.target.value)}
                  className="bg-ash border border-border-subtle rounded px-2 py-1 text-sm text-primary w-16"
                /> min
              </label>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                data-testid="recurring-save-btn"
                onClick={saveRecurring}
                className="text-[11px] text-graphite bg-mint px-3 py-1 rounded-md font-medium hover:bg-mint/90 transition-all duration-200 ease-out active:scale-95"
              >
                Save
              </button>
              <button
                type="button"
                data-testid="recurring-cancel-btn"
                onClick={() => {
                  setEditingRecurring(false)
                  setEditDays(new Set(doctor.working_days || []))
                  setEditStart(doctor.hours_start || '09:00')
                  setEditEnd(doctor.hours_end || '17:00')
                  setEditDuration(doctor.consultation_duration_mins || 30)
                }}
                className="text-[11px] text-tertiary border border-border-subtle rounded-md px-3 py-1 hover:text-primary transition-all duration-200 ease-out active:scale-95"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </section>

      {/* Time off */}
      <section className="bg-graphite rounded-xl border border-border-subtle p-4">
        <div className="flex items-center justify-between mb-3">
          <h4 className="text-xs font-semibold text-tertiary tracking-widest uppercase">Time off</h4>
          {!addingTimeOff && (
            <button
              type="button"
              data-testid="add-time-off-btn"
              onClick={() => { setAddingTimeOff(true); trackAction('add_time_off', detail?.name || '', 'doctor', selected) }}
              className={`flex items-center gap-1 text-[11px] text-mint border border-mint/20 rounded-md px-2 py-1 hover:bg-mint/10 transition-all duration-200 ease-out active:scale-95
                ${agentHighlight?.target === 'button' && agentHighlight?.id === 'add-time-off' ? 'agent-blink ring-2 ring-mint/50' : ''}`}
            >
              <Plus size={11} /> Add time off
            </button>
          )}
        </div>

        {loading ? (
          <div className="py-4 flex items-center justify-center">
            <div className="shimmer w-32 h-2 rounded-full" />
          </div>
        ) : (unavailability || []).length === 0 ? (
          <p data-testid="time-off-empty" className="text-tertiary text-sm py-2">No time off scheduled</p>
        ) : (
          <div className="flex flex-col divide-y divide-border-subtle/50">
            {unavailability.map(row => (
              <TimeOffRow key={row.id} row={row} onClear={() => clearRow(row)} />
            ))}
          </div>
        )}

        {addingTimeOff && (
          <div data-testid="time-off-form" className="mt-4 pt-4 border-t border-border-subtle flex flex-col gap-3">
            <div className="flex items-center gap-3 flex-wrap">
              <label className="text-[11px] text-tertiary flex items-center gap-1.5">
                From
                <input
                  type="date"
                  value={toStart}
                  onChange={e => {
                    setToStart(e.target.value)
                    if (new Date(toEnd) < new Date(e.target.value)) setToEnd(e.target.value)
                  }}
                  className="bg-ash border border-border-subtle rounded px-2 py-1 text-sm text-primary"
                />
              </label>
              <label className="text-[11px] text-tertiary flex items-center gap-1.5">
                To
                <input
                  type="date"
                  value={toEnd}
                  onChange={e => setToEnd(e.target.value)}
                  className="bg-ash border border-border-subtle rounded px-2 py-1 text-sm text-primary"
                />
              </label>
              <label className="text-[11px] text-tertiary flex items-center gap-1.5">
                Reason
                <select
                  value={toReason}
                  onChange={e => setToReason(e.target.value)}
                  data-testid="time-off-reason"
                  className="bg-ash border border-border-subtle rounded px-2 py-1 text-sm text-primary"
                >
                  <option value="sick">sick</option>
                  <option value="leave">leave</option>
                  <option value="other">other</option>
                </select>
              </label>
            </div>
            <label className="text-[11px] text-tertiary flex items-center gap-1.5">
              <input
                type="checkbox"
                checked={toPartial}
                onChange={e => setToPartial(e.target.checked)}
                data-testid="time-off-partial"
              />
              Partial day
            </label>
            {toPartial && (
              <div className="flex items-center gap-3">
                <label className="text-[11px] text-tertiary flex items-center gap-1.5">
                  Start
                  <input
                    type="time"
                    value={toStartTime}
                    onChange={e => setToStartTime(e.target.value)}
                    className="bg-ash border border-border-subtle rounded px-2 py-1 text-sm text-primary"
                  />
                </label>
                <label className="text-[11px] text-tertiary flex items-center gap-1.5">
                  End
                  <input
                    type="time"
                    value={toEndTime}
                    onChange={e => setToEndTime(e.target.value)}
                    className="bg-ash border border-border-subtle rounded px-2 py-1 text-sm text-primary"
                  />
                </label>
              </div>
            )}
            <input
              type="text"
              placeholder="Optional note"
              value={toNote}
              onChange={e => setToNote(e.target.value)}
              className="bg-ash border border-border-subtle rounded px-2 py-1.5 text-sm text-primary placeholder:text-tertiary"
            />
            {formError && (
              <p data-testid="time-off-form-error" className="text-[11px] text-coral">{formError}</p>
            )}
            <div className="flex items-center gap-2">
              <button
                type="button"
                data-testid="time-off-save"
                onClick={submitTimeOff}
                className="text-[11px] text-graphite bg-mint px-3 py-1 rounded-md font-medium hover:bg-mint/90 transition-all duration-200 ease-out active:scale-95"
              >
                Add
              </button>
              <button
                type="button"
                onClick={() => setAddingTimeOff(false)}
                className="text-[11px] text-tertiary border border-border-subtle rounded-md px-3 py-1 hover:text-primary transition-all duration-200 ease-out active:scale-95"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </section>

      {error && (
        <p className="text-[11px] text-coral">{error}</p>
      )}
    </div>
  )
}


function TimeOffRow({ row, onClear }) {
  const todayIso = new Date().toISOString().slice(0, 10)
  const sameDay = row.start_date === row.end_date
  const isToday = row.start_date === todayIso && sameDay
  const reasonText = row.reason === 'sick' ? 'Sick leave'
    : row.reason === 'leave' ? 'Leave' : 'Other'

  const dateLabel = isToday
    ? 'Today'
    : sameDay
      ? formatDateShort(row.start_date)
      : `${formatDateShort(row.start_date)} – ${formatDateShort(row.end_date)}`
  const windowLabel = (row.start_time && row.end_time)
    ? `${row.start_time} – ${row.end_time}`
    : sameDay ? 'full day' : 'full days'

  return (
    <div data-testid="time-off-row" className="flex items-center gap-3 py-2.5 group">
      <span className="text-gold text-sm leading-none">●</span>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-primary">
          {dateLabel}
          <span className="text-secondary"> · {reasonText}</span>
          {row.note && <span className="text-tertiary"> · {row.note}</span>}
        </p>
        <p className="text-[11px] text-tertiary">{windowLabel}</p>
      </div>
      <button
        type="button"
        data-testid="time-off-clear"
        onClick={onClear}
        className="flex items-center gap-1 text-[11px] text-tertiary border border-border-subtle rounded-md px-2 py-1 hover:text-coral hover:border-coral/30 transition-all duration-200 ease-out active:scale-95"
      >
        <X size={10} /> Clear
      </button>
    </div>
  )
}


function formatDateShort(iso) {
  if (!iso) return ''
  try {
    const d = new Date(iso + 'T00:00:00')
    return d.toLocaleDateString('en-AU', { month: 'short', day: 'numeric' })
  } catch {
    return iso
  }
}


function StatCard({ label, value, sub, icon: Icon, alert }) {
  return (
    <div className="bg-graphite rounded-xl border border-border-subtle p-3">
      <div className="flex items-center gap-2 mb-1.5">
        <Icon size={12} className={alert ? 'text-gold' : 'text-tertiary'} />
        <span className="text-[10px] text-tertiary uppercase tracking-wider">{label}</span>
      </div>
      <p className={`text-lg font-semibold ${alert ? 'text-gold' : 'text-primary'}`}>{value}</p>
      <p className="text-[10px] text-tertiary">{sub}</p>
    </div>
  )
}

function getDemoDoctors() {
  return [
    { id: 'dr-chen', name: 'Dr Sarah Chen', specialty: 'General Practice', working_days: ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'], hours_start: '09:00', hours_end: '17:00', consultation_duration_mins: 30, appointments_today: 8 },
    { id: 'dr-patel', name: 'Dr Raj Patel', specialty: 'General Practice', working_days: ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'], hours_start: '08:30', hours_end: '16:30', consultation_duration_mins: 30, appointments_today: 6 },
    { id: 'dr-kim', name: 'Dr Joon Kim', specialty: 'Paediatrics', working_days: ['Monday', 'Wednesday', 'Friday'], hours_start: '09:00', hours_end: '15:00', consultation_duration_mins: 45, appointments_today: 4 },
    { id: 'dr-nguyen', name: 'Dr Mai Nguyen', specialty: "Women's Health", working_days: ['Tuesday', 'Thursday', 'Friday'], hours_start: '10:00', hours_end: '18:00', consultation_duration_mins: 30, appointments_today: 5 },
  ]
}

function getDemoDetail() {
  return {
    schedule: [
      { date: '2026-04-08', time: '09:00', patient_name: 'David Thompson', type: 'standard', status: 'scheduled' },
      { date: '2026-04-08', time: '09:30', patient_name: 'Margaret Wilson', type: 'follow_up', status: 'completed' },
      { date: '2026-04-08', time: '10:30', patient_name: 'Ben O\'Sullivan', type: 'standard', status: 'scheduled' },
      { date: '2026-04-09', time: '09:00', patient_name: 'Priya Sharma', type: 'telehealth', status: 'scheduled' },
      { date: '2026-04-10', time: '14:00', patient_name: 'Daniel Brown', type: 'standard', status: 'scheduled' },
    ],
    patients_this_month: 24,
    no_show_rate: 4.2,
    patients: [
      { first_name: 'David', last_name: 'Thompson', last_seen: '2026-04-07' },
      { first_name: 'Margaret', last_name: 'Wilson', last_seen: '2026-04-04' },
      { first_name: 'Priya', last_name: 'Sharma', last_seen: '2026-03-28' },
      { first_name: 'Ben', last_name: "O'Sullivan", last_seen: '2026-03-25' },
      { first_name: 'Sophie', last_name: 'Martin', last_seen: '2026-03-20' },
    ],
  }
}
