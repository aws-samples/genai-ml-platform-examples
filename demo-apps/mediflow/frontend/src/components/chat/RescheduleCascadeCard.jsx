import { useEffect, useRef, useState } from 'react'
import { Check, Loader2, Send, Users, Search, CalendarCheck, MessageSquare, MailCheck } from 'lucide-react'

/**
 * RescheduleCascadeCard — shown when the agent bulk-reschedules all patients
 * for a doctor (sick day / leave). Matches script Segment 2 beats: brief
 * "agent is working" (linear checklist lights up), then a cascade of per-patient
 * reschedule rows fanning in with 100ms stagger.
 *
 * Timing floors (actual times may stretch if rows cascade longer than the floor):
 *  - Minimum 1.5s between each node lighting up
 *  - Step 4 (Drafting) stays active while rows cascade (100ms each)
 *  - Step 5 (Notify) lights 30% slower than a normal step (~1.95s after step 4)
 */

const STEP_STAGGER = 1500                        // minimum gap between node lights
const ROW_STAGGER = 100
const TAIL_DELAY = 300                           // beat after rows finish before step 4 closes
const NOTIFY_STEP_DURATION = Math.round(STEP_STAGGER * 1.3) // Send-notifications is 30% slower than a normal step

function StepNode({ state, icon: Icon, label, detail }) {
  const done = state === 'done'
  const active = state === 'active'
  return (
    <div
      className={`flex items-start gap-2.5 py-1 transition-all duration-200 ease-out ${
        state === 'pending' ? 'opacity-40' : 'opacity-100'
      }`}
    >
      <div
        className={`mt-0.5 w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 transition-all duration-200 ease-out
          ${done ? 'bg-mint/20 text-mint' : ''}
          ${active ? 'bg-mint/10 text-mint' : ''}
          ${state === 'pending' ? 'bg-graphite text-tertiary border border-border-subtle' : ''}
        `}
      >
        {done ? <Check size={12} strokeWidth={3} /> : active ? <Loader2 size={12} className="animate-spin" /> : <Icon size={11} />}
      </div>
      <div className="flex-1 min-w-0">
        <div className={`text-xs font-medium leading-tight ${done || active ? 'text-primary' : 'text-tertiary'}`}>
          {label}
        </div>
        {detail && (
          <div className="text-[11px] text-tertiary leading-tight mt-0.5">{detail}</div>
        )}
      </div>
    </div>
  )
}

function EntryRow({ entry, visible, index }) {
  return (
    <div
      className={`flex items-center gap-2 text-[11px] leading-tight py-0.5 pl-3 transition-all duration-200 ease-out ${
        visible ? 'opacity-100 translate-x-0' : 'opacity-0 -translate-x-1 pointer-events-none h-0'
      }`}
      style={{ transitionDelay: visible ? `${index * 30}ms` : '0ms' }}
    >
      <Check size={10} className="text-mint flex-shrink-0" strokeWidth={3} />
      <span className="text-secondary truncate flex-1 min-w-0">
        {entry.patient_name}
      </span>
      <span className="text-tertiary whitespace-nowrap">
        → {entry.new_doctor_name?.replace(/^Dr\s+/, 'Dr ')} · {entry.new_time}
      </span>
    </div>
  )
}

export default function RescheduleCascadeCard({ data, onComplete }) {
  const [phase, setPhase] = useState(0)           // 0..4 (which step is "latest active")
  const [visibleRows, setVisibleRows] = useState(0)
  const [rowsExpanded, setRowsExpanded] = useState(true)
  const completeFiredRef = useRef(false)

  if (!data) return null
  const {
    doctor_name = 'Doctor',
    doctor_id,
    total_affected = 0,
    doctors_considered = 0,
    messages_drafted = 0,
    entries = [],
  } = data
  const rows = entries.filter(e => e.new_time)

  useEffect(() => {
    const timers = []
    // Steps light up at a 1.5s-minimum cadence. Step 4 becomes active
    // the instant step 3 completes — rows then cascade inside its active
    // window (natural length = rows.length * ROW_STAGGER, min STEP_STAGGER).
    timers.push(setTimeout(() => setPhase(1), 0))
    timers.push(setTimeout(() => setPhase(2), STEP_STAGGER))
    timers.push(setTimeout(() => setPhase(3), STEP_STAGGER * 2))

    // Rows cascade starts the moment step 4 becomes active (= step 3 done).
    const rowsStart = STEP_STAGGER * 2
    rows.forEach((_, i) => {
      timers.push(setTimeout(() => setVisibleRows(n => Math.max(n, i + 1)), rowsStart + i * ROW_STAGGER))
    })
    const rowsDuration = rows.length * ROW_STAGGER
    // Step 4 stays active for at least STEP_STAGGER; if rows take longer,
    // we extend it (never shorten the floor).
    const step4ActiveFor = Math.max(STEP_STAGGER, rowsDuration + TAIL_DELAY)
    const step4DoneAt = rowsStart + step4ActiveFor
    timers.push(setTimeout(() => setPhase(4), step4DoneAt))

    // Send notifications is 30% slower than a normal step.
    timers.push(setTimeout(() => setPhase(5), step4DoneAt + NOTIFY_STEP_DURATION))
    return () => timers.forEach(clearTimeout)
  }, [rows.length])

  // Signal animation complete when final phase reached
  useEffect(() => {
    if (phase >= 5 && onComplete && !completeFiredRef.current) {
      completeFiredRef.current = true
      onComplete()
    }
  }, [phase, onComplete])

  const stepState = (idx) => {
    if (phase > idx) return 'done'
    if (phase === idx - 0.5 || phase === idx) return 'active'
    return phase >= idx ? 'done' : 'pending'
  }

  // Simpler per-step state resolver
  const s1 = phase >= 1 ? 'done' : 'active'
  const s2 = phase >= 2 ? 'done' : phase >= 1 ? 'active' : 'pending'
  const s3 = phase >= 3 ? 'done' : phase >= 2 ? 'active' : 'pending'
  const s4 = phase >= 4 ? 'done' : phase >= 3 ? 'active' : 'pending'
  const s5 = phase >= 5 ? 'done' : phase >= 4 ? 'active' : 'pending'

  const progress = phase >= 5 ? rows.length : visibleRows
  const progressPct = rows.length ? Math.round((progress / rows.length) * 100) : 0

  return (
    <div
      className="bg-graphite rounded-xl border border-border-subtle overflow-hidden
        animate-[count-up-fade_400ms_ease-out] transition-all duration-200 ease-out"
      data-testid="reschedule-cascade-card"
    >
      {/* Header */}
      <div className="px-4 py-3 border-b border-border-subtle">
        <div className="text-xs font-semibold text-primary leading-tight">
          {doctor_name} sick-day · reschedule all
        </div>
        <div className="text-[11px] text-tertiary mt-0.5">
          {total_affected} affected · {doctors_considered} alternate doctors
        </div>
      </div>

      {/* Steps */}
      <div className="px-4 py-3 space-y-0.5">
        <StepNode state={s1} icon={Users} label={`Identified ${total_affected} affected patients`} />
        <StepNode state={s2} icon={Search} label={`Checked availability across ${doctors_considered} doctors`} />
        <StepNode
          state={s3}
          icon={CalendarCheck}
          label={`Matched ${rows.length} slots`}
          detail={s3 === 'done' || s3 === 'active' ? 'context-aware' : null}
        />
        <StepNode
          state={s4}
          icon={MessageSquare}
          label="Drafting personalised messages"
          detail={s4 === 'active' && rows.length ? `${visibleRows}/${rows.length}` : null}
        />

        {/* Entries cascade under Step 4 */}
        {s4 !== 'pending' && rows.length > 0 && (
          <div className="ml-[26px] pl-2 border-l border-border-subtle py-1 space-y-0.5">
            {rows.map((e, i) => (
              <EntryRow
                key={e.appointment_id || i}
                entry={e}
                index={i}
                visible={i < visibleRows}
              />
            ))}
            {rows.length > visibleRows && (
              <div className="text-[11px] text-tertiary pl-3 py-0.5">
                {rows.length - visibleRows} more to go…
              </div>
            )}
          </div>
        )}

        <StepNode state={s5} icon={MailCheck} label="Send notifications" detail={s5 === 'done' ? `${messages_drafted} SMS sent` : null} />
      </div>

      {/* Progress bar */}
      <div className="px-4 pb-3">
        <div className="h-1 bg-ash rounded-full overflow-hidden">
          <div
            className="h-full bg-mint transition-all duration-300 ease-out"
            style={{ width: `${progressPct}%` }}
          />
        </div>
        <div className="text-[11px] text-tertiary mt-1.5 text-right">
          {progress} of {rows.length}
        </div>
      </div>
    </div>
  )
}
