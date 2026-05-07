import { useState, useEffect, useRef, useCallback } from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { api } from '../../api/client'
import { useApp } from '../../context/AppContext'
import HealthPanel from './HealthPanel'
import {
  Sparkles, Zap, Brain, Heart, ArrowRight, Play, Check,
  Clock, Users, Timer, MessageSquare, Calendar, Stethoscope,
  Power, X, Loader2, CheckCircle2, AlertCircle, CalendarPlus, FileText,
  ChevronDown, RotateCw, Activity,
} from 'lucide-react'

/* ─── Type Badge ─────────────────────────────────────── */
function TypeBadge({ scheduled, cadence, time }) {
  if (scheduled) {
    const cadenceLabel = humaniseCadence(cadence, time)
    return (
      <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase tracking-wider bg-mint/15 text-mint flex items-center gap-1">
        <Timer size={9} /> Scheduled{cadenceLabel ? ` · ${cadenceLabel}` : ''}
      </span>
    )
  }
  return (
    <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase tracking-wider bg-violet/15 text-violet flex items-center gap-1">
      <Brain size={9} /> Ad-hoc
    </span>
  )
}

function humaniseCadence(cadence, time) {
  if (!cadence) return ''
  const timeLabel = time ? ` ${time}` : ''
  switch (cadence) {
    case 'daily': return `Daily${timeLabel}`
    case 'weekdays': return `Weekdays${timeLabel}`
    case 'weekly': return `Weekly${timeLabel}`
    case 'monthly': return `Monthly${timeLabel}`
    default: return cadence
  }
}

/* ─── NEW Badge ──────────────────────────────────────── */
function NewBadge() {
  return (
    <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full uppercase tracking-wider bg-violet/15 text-violet new-badge-pulse">
      New
    </span>
  )
}

/* ─── Memory type icon ────────────────────────────────── */
function MemoryIcon({ type }) {
  const icons = {
    preference: <Heart size={12} className="text-coral" />,
    behavioral: <Calendar size={12} className="text-gold" />,
    medical_context: <Stethoscope size={12} className="text-mint" />,
    communication: <MessageSquare size={12} className="text-periwinkle" />,
  }
  return icons[type] || <Brain size={12} className="text-violet" />
}

/* ─── Seen-items tracker (localStorage) ───────────────── */
const SEEN_KEY = 'mediflow-seen-improvements'

function getSeenIds() {
  try {
    return new Set(JSON.parse(localStorage.getItem(SEEN_KEY) || '[]'))
  } catch { return new Set() }
}

function markAllSeen(ids) {
  const existing = getSeenIds()
  ids.forEach(id => existing.add(id))
  localStorage.setItem(SEEN_KEY, JSON.stringify([...existing]))
}

/* ─── Sort by impact ─────────────────────── */
function sortByImpact(skills) {
  return [...skills].sort((a, b) => {
    const aScore = (a.occurrence_count || 0) + (a.scheduled ? 20 : 0)
    const bScore = (b.occurrence_count || 0) + (b.scheduled ? 20 : 0)
    if (bScore !== aScore) return bScore - aScore
    return (a.name || '').localeCompare(b.name || '')
  })
}

/* ─── Schedule helpers ────────────────────────────────── */
const CADENCE_OPTIONS = [
  { value: 'daily', label: 'Every day' },
  { value: 'weekdays', label: 'Weekdays' },
  { value: 'weekly', label: 'Every week' },
  { value: 'monthly', label: 'Every month' },
]

const TIME_OPTIONS = (() => {
  const opts = []
  for (let h = 7; h <= 18; h++) {
    for (const m of ['00', '30']) {
      if (h === 18 && m === '30') continue
      const hh = h.toString().padStart(2, '0')
      const label = `${h > 12 ? h - 12 : h}:${m} ${h >= 12 ? 'PM' : 'AM'}`
      opts.push({ value: `${hh}:${m}`, label })
    }
  }
  return opts
})()

function nextRunText(cadence, time) {
  const [hh, mm] = (time || '08:00').split(':').map(Number)
  const now = new Date()
  const next = new Date(now)
  next.setHours(hh, mm, 0, 0)
  if (next <= now) next.setDate(next.getDate() + 1)
  if (cadence === 'weekdays') {
    while (next.getDay() === 0 || next.getDay() === 6) next.setDate(next.getDate() + 1)
  }
  const dayDiff = Math.floor((next - now) / 86400000)
  const dayLabel = dayDiff === 0 ? 'Today' : dayDiff === 1 ? 'Tomorrow' : next.toLocaleDateString('en-AU', { weekday: 'short', month: 'short', day: 'numeric' })
  const timeLabel = `${hh > 12 ? hh - 12 : hh}:${mm.toString().padStart(2, '0')} ${hh >= 12 ? 'PM' : 'AM'}`
  return `${dayLabel} at ${timeLabel}`
}

/* ─── Skill Row (compact) ───────────────────────── */
function SkillRow({ skill, isNew, onEnable, onRun, onClick, index }) {
  const [justEnabled, setJustEnabled] = useState(false)
  const isEnabled = skill.status === 'enabled'
  const isScheduled = !!skill.scheduled

  const handleEnable = (e) => {
    e.stopPropagation()
    setJustEnabled(true)
    onEnable(skill)
    setTimeout(() => setJustEnabled(false), 800)
  }

  const handleRun = (e) => {
    e.stopPropagation()
    onRun(skill)
  }

  return (
    <div
      onClick={onClick}
      className={`
        bg-graphite rounded-xl border border-l-4 px-4 py-3
        transition-all duration-200 ease-out cascade-item cursor-pointer
        ${isEnabled
          ? 'border-border-subtle border-l-mint opacity-100 hover:border-border-glow'
          : 'border-border-subtle/50 border-l-ash opacity-60 hover:opacity-80'
        }
        ${justEnabled ? 'animate-[enable-glow_800ms_ease-out]' : ''}
      `}
      style={{ animationDelay: `${index * 60}ms` }}
      data-testid={`skill-row-${skill.id}`}
      data-scheduled={isScheduled ? '1' : '0'}
      data-enabled={isEnabled ? '1' : '0'}
    >
      <div className="flex items-center gap-3">
        {/* Icon */}
        <div className={`w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0
          ${isEnabled ? (isScheduled ? 'bg-mint/10' : 'bg-violet/10') : 'bg-ash/50'}`}>
          {isScheduled
            ? <Zap size={14} className={isEnabled ? 'text-mint' : 'text-tertiary'} />
            : <Brain size={14} className={isEnabled ? 'text-violet' : 'text-tertiary'} />
          }
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className={`text-sm font-medium truncate ${isEnabled ? 'text-primary' : 'text-secondary'}`}>
              {skill.name}
            </p>
            {isNew && <NewBadge />}
          </div>
          <p className="text-tertiary text-xs truncate">{skill.description}</p>
          <div className="flex items-center gap-2 mt-1">
            <TypeBadge
              scheduled={isScheduled}
              cadence={skill.schedule_cadence}
              time={skill.schedule_time}
            />
            {skill.occurrence_count > 0 && (
              <span className="text-[10px] text-secondary">
                Observed {skill.occurrence_count} times
              </span>
            )}
          </div>
        </div>

        {/* Actions — Enable toggle is stable (rightmost); Run now is conditional */}
        <div className="flex items-center gap-2 flex-shrink-0">
          {isEnabled && isScheduled && (
            <button
              onClick={handleRun}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg
                bg-mint/10 text-mint text-xs font-semibold border border-mint/20
                hover:bg-mint/20 transition-all duration-200 ease-out active:scale-95"
            >
              <Play size={11} /> Run now
            </button>
          )}
          <button
            onClick={handleEnable}
            aria-pressed={isEnabled}
            aria-label={isEnabled ? 'Disable skill' : 'Enable skill'}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold
              transition-all duration-200 ease-out active:scale-95
              ${isEnabled
                ? 'bg-mint text-inverse hover:bg-mint/90'
                : 'bg-ash text-tertiary border border-border-subtle hover:text-secondary hover:border-border-glow'
              }`}
          >
            <Power size={11} /> {isEnabled ? 'ON' : 'OFF'}
          </button>
        </div>
      </div>
    </div>
  )
}

/* ─── Skill Detail Modal ────────────────────────── */
function SkillDetailModal({ skill, isNew, onClose, onEnable, onRun, onSchedule, onAddSchedule }) {
  const isEnabled = skill.status === 'enabled'
  const isScheduled = !!skill.scheduled
  const [cadence, setCadence] = useState(skill.schedule_cadence || 'daily')
  const [time, setTime] = useState(skill.schedule_time || '08:00')
  const [justEnabled, setJustEnabled] = useState(false)
  const [modalTab, setModalTab] = useState('details')
  const { agentPanelOpen } = useApp()

  useEffect(() => {
    const handleKey = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [onClose])

  const handleCadenceChange = (newCadence) => {
    setCadence(newCadence)
    onSchedule?.(skill, { cadence: newCadence, time })
  }

  const handleTimeChange = (newTime) => {
    setTime(newTime)
    onSchedule?.(skill, { cadence, time: newTime })
  }

  const handleEnable = () => {
    setJustEnabled(true)
    onEnable(skill)
    setTimeout(() => setJustEnabled(false), 800)
  }

  const handleRun = () => {
    onClose()
    setTimeout(() => onRun(skill), 150)
  }

  const accentColor = isScheduled ? 'mint' : 'violet'

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center overlay-scrim"
      style={{
        backgroundColor: 'rgba(11, 13, 17, 0.88)',
        right: agentPanelOpen ? '380px' : '0',
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
      data-testid="skill-detail-modal"
    >
      <div className="w-full max-w-lg max-h-[85vh] flex flex-col bg-slate rounded-2xl border border-border-subtle
        shadow-2xl overlay-panel overflow-hidden mx-4">

        {/* Header */}
        <div className="flex items-start justify-between p-5 pb-3">
          <div className="flex items-center gap-2.5 flex-1 min-w-0">
            <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0
              ${isScheduled ? 'bg-mint/10' : 'bg-violet/10'}`}>
              {isScheduled
                ? <Zap size={16} className="text-mint" />
                : <Brain size={16} className="text-violet" />
              }
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h2 className="text-base font-semibold text-primary truncate">{skill.name}</h2>
                {isNew && <NewBadge />}
              </div>
              <div className="flex items-center gap-2 mt-0.5">
                <TypeBadge
                  scheduled={isScheduled}
                  cadence={skill.schedule_cadence}
                  time={skill.schedule_time}
                />
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            className="ml-3 p-1.5 rounded-lg text-tertiary hover:text-secondary hover:bg-ash
              transition-all duration-200 ease-out active:scale-95"
          >
            <X size={16} />
          </button>
        </div>

        {/* Tab bar */}
        <div className="flex gap-1 px-5 pb-2">
          {['details', 'history'].map(tab => (
            <button
              key={tab}
              onClick={() => setModalTab(tab)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all duration-200 ease-out
                ${modalTab === tab
                  ? `bg-${accentColor}/10 text-${accentColor} border border-${accentColor}/20`
                  : 'text-tertiary hover:text-secondary hover:bg-ash'
                }`}
            >
              {tab === 'details' ? 'Details' : 'History'}
              {tab === 'history' && skill.usage_count > 0 && (
                <span className="ml-1.5 text-[10px] opacity-60">({skill.usage_count})</span>
              )}
            </button>
          ))}
        </div>

        {/* Scrollable content */}
        <div className="flex-1 overflow-auto px-5 pb-5 space-y-4" key={modalTab}>

          {modalTab === 'history' && <ExecutionHistoryTab skill={skill} />}

          {modalTab === 'details' && <>

          {/* Description */}
          <p className="text-secondary text-sm leading-relaxed">
            {skill.trigger_description || skill.description}
          </p>

          {/* What I Learned */}
          {(skill.pattern_description || skill.example_scenario) && (
            <div className={`bg-void/50 rounded-xl border-l-2 border-${accentColor}/30 px-4 py-3`}>
              <p className="text-[10px] font-semibold text-tertiary tracking-widest uppercase mb-2">
                What I learned
              </p>
              <p className="text-secondary text-xs leading-relaxed">
                {skill.pattern_description || 'Detected repeated pattern in agent interactions.'}
              </p>
              {skill.occurrence_count > 0 && (
                <p className="text-tertiary text-[11px] mt-1.5">
                  Observed {skill.occurrence_count} times
                </p>
              )}
              {skill.example_scenario && (
                <div className="mt-2 pt-2 border-t border-border-subtle">
                  <p className="text-[10px] font-semibold text-tertiary tracking-widest uppercase mb-1">
                    Example
                  </p>
                  <p className="text-secondary text-xs italic">"{skill.example_scenario}"</p>
                </div>
              )}
            </div>
          )}

          {/* Schedule editor — only for scheduled skills */}
          {isScheduled ? (
            <div className="bg-void/50 rounded-xl px-4 py-3">
              <p className="text-[10px] font-semibold text-tertiary tracking-widest uppercase mb-3">
                Schedule
              </p>
              <div className="flex items-center gap-4 flex-wrap">
                <label className="flex items-center gap-2 text-xs text-secondary">
                  <span className="text-tertiary">Runs:</span>
                  <select
                    value={cadence}
                    onChange={(e) => handleCadenceChange(e.target.value)}
                    className="bg-ash text-primary text-xs rounded-lg px-2.5 py-1.5
                      border border-border-subtle focus:border-border-active
                      outline-none transition-colors cursor-pointer"
                  >
                    {CADENCE_OPTIONS.map(o => (
                      <option key={o.value} value={o.value}>{o.label}</option>
                    ))}
                  </select>
                </label>
                <label className="flex items-center gap-2 text-xs text-secondary">
                  <span className="text-tertiary">At:</span>
                  <select
                    value={time}
                    onChange={(e) => handleTimeChange(e.target.value)}
                    className="bg-ash text-primary text-xs rounded-lg px-2.5 py-1.5
                      border border-border-subtle focus:border-border-active
                      outline-none transition-colors cursor-pointer"
                  >
                    {TIME_OPTIONS.map(o => (
                      <option key={o.value} value={o.value}>{o.label}</option>
                    ))}
                  </select>
                </label>
              </div>
              <p className="text-tertiary text-[11px] mt-2 flex items-center gap-1">
                <Clock size={10} /> Next run: {nextRunText(cadence, time)}
              </p>
            </div>
          ) : (
            <div className="bg-void/50 rounded-xl border-l-2 border-violet/30 px-4 py-3">
              <p className="text-[10px] font-semibold text-tertiary tracking-widest uppercase mb-2">
                Ad-hoc skill
              </p>
              <p className="text-secondary text-xs leading-relaxed mb-3">
                This skill runs when invoked from chat — it isn't on a schedule.
              </p>
              <button
                onClick={() => onAddSchedule?.(skill)}
                data-testid="add-schedule-button"
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg
                  bg-violet/10 text-violet text-xs font-semibold border border-violet/20
                  hover:bg-violet/20 transition-all duration-200 ease-out active:scale-95"
              >
                <CalendarPlus size={12} /> Add schedule
              </button>
            </div>
          )}

          </>}
        </div>

        {/* Footer actions */}
        <div className={`px-5 py-4 border-t border-border-subtle flex items-center gap-3
          ${justEnabled ? 'animate-[enable-glow_800ms_ease-out]' : ''}`}>
          <button
            onClick={handleEnable}
            aria-pressed={isEnabled}
            className={`flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg
              text-sm font-semibold transition-all duration-200 ease-out active:scale-95
              ${isEnabled
                ? 'bg-mint text-inverse hover:bg-mint/90'
                : 'bg-ash text-tertiary border border-border-subtle hover:text-secondary hover:border-border-glow'
              }`}
          >
            <Power size={14} /> {isEnabled ? 'Enabled' : 'Enable'}
          </button>
          {isEnabled && isScheduled && (
            <button
              onClick={handleRun}
              data-testid="run-now-button"
              className="flex items-center gap-2 px-5 py-2.5 rounded-lg
                bg-mint/10 text-mint text-sm font-semibold border border-mint/20
                hover:bg-mint/20 transition-all duration-200 ease-out active:scale-95"
            >
              <Play size={14} /> Run now
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

/* ─── Execution History Tab ────────────────────────── */
function ExecutionHistoryTab({ skill }) {
  const [executions, setExecutions] = useState(null)
  const [expanded, setExpanded] = useState(null)
  const [detail, setDetail] = useState(null)

  useEffect(() => {
    api.skillHistory(skill.id).then(data => setExecutions(data.executions || []))
  }, [skill.id])

  const toggleExpand = async (execId) => {
    if (expanded === execId) {
      setExpanded(null)
      setDetail(null)
      return
    }
    setExpanded(execId)
    const data = await api.skillHistoryDetail(skill.id, execId)
    setDetail(data)
  }

  if (executions === null) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 size={16} className="animate-spin text-tertiary" />
      </div>
    )
  }

  if (executions.length === 0) {
    return (
      <div className="text-center py-8">
        <Clock size={20} className="mx-auto text-tertiary mb-2 opacity-50" />
        <p className="text-tertiary text-xs">No executions yet</p>
        <p className="text-tertiary text-[11px] mt-1 opacity-60">
          Run this skill to see its history here
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {executions.map((exec, i) => (
        <div key={exec.id} className="cascade-item" style={{ '--i': i }}>
          <button
            onClick={() => toggleExpand(exec.id)}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg bg-void/50
              hover:bg-ash transition-all duration-200 ease-out text-left group"
          >
            <StatusBadge status={exec.status} />
            <div className="flex-1 min-w-0">
              <p className="text-xs text-secondary truncate">
                {formatExecDate(exec.started_at)}
              </p>
              {exec.summary && (
                <p className="text-[11px] text-tertiary truncate mt-0.5">{exec.summary}</p>
              )}
            </div>
            <div className="flex items-center gap-2 text-[11px] text-tertiary flex-shrink-0">
              {exec.items_total > 0 && (
                <span>
                  {exec.items_succeeded}/{exec.items_total}
                </span>
              )}
              {exec.duration_ms && (
                <span>{formatDuration(exec.duration_ms)}</span>
              )}
              <ChevronDown
                size={12}
                className={`transition-transform duration-200 ${expanded === exec.id ? 'rotate-180' : ''}`}
              />
            </div>
          </button>

          {expanded === exec.id && (
            <div className="ml-4 mt-1 mb-2 space-y-1 content-enter">
              {!detail ? (
                <div className="flex items-center gap-2 px-3 py-2">
                  <Loader2 size={12} className="animate-spin text-tertiary" />
                  <span className="text-[11px] text-tertiary">Loading items...</span>
                </div>
              ) : (detail.items || []).length === 0 ? (
                <p className="text-[11px] text-tertiary px-3 py-2">No item-level detail recorded</p>
              ) : (
                detail.items.map((item, j) => (
                  <div key={item.id} className="flex items-center gap-2 px-3 py-1.5 rounded-md">
                    {item.status === 'success'
                      ? <CheckCircle2 size={11} className="text-mint flex-shrink-0" />
                      : item.status === 'failed'
                        ? <AlertCircle size={11} className="text-coral flex-shrink-0" />
                        : <Clock size={11} className="text-tertiary flex-shrink-0" />
                    }
                    <span className="text-[11px] text-secondary truncate flex-1">
                      {item.entity_name || `Item ${j + 1}`}
                    </span>
                    {item.duration_ms && (
                      <span className="text-[10px] text-tertiary">{formatDuration(item.duration_ms)}</span>
                    )}
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

function StatusBadge({ status }) {
  const config = {
    completed: { icon: CheckCircle2, color: 'text-mint', bg: 'bg-mint/10' },
    partial: { icon: AlertCircle, color: 'text-gold', bg: 'bg-gold/10' },
    failed: { icon: AlertCircle, color: 'text-coral', bg: 'bg-coral/10' },
    running: { icon: Loader2, color: 'text-mint', bg: 'bg-mint/10', spin: true },
  }
  const c = config[status] || config.completed
  const Icon = c.icon
  return (
    <div className={`w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0 ${c.bg}`}>
      <Icon size={12} className={`${c.color} ${c.spin ? 'animate-spin' : ''}`} />
    </div>
  )
}

function formatExecDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  const diff = now - d
  if (diff < 60000) return 'Just now'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function formatDuration(ms) {
  if (ms < 1000) return `${ms}ms`
  const s = Math.round(ms / 1000)
  if (s < 60) return `${s}s`
  return `${Math.floor(s / 60)}m ${s % 60}s`
}

/* ─── Execution Overlay ──────────────────────────────── */
function ExecutionOverlay({ skill, onClose, onError }) {
  const [results, setResults] = useState([])
  const [status, setStatus] = useState('resolving') // resolving | awaiting_approval | running | complete | error
  const [totalItems, setTotalItems] = useState(0)
  const [completedItems, setCompletedItems] = useState(0)
  const [currentTool, setCurrentTool] = useState(null)
  const [summary, setSummary] = useState(null)
  const [approvalData, setApprovalData] = useState(null) // { items, execution_id, ... }
  const [selectedItems, setSelectedItems] = useState(new Set())
  const controllerRef = useRef(null)
  const resultsEndRef = useRef(null)

  useEffect(() => {
    resultsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [results])

  function handleSSEEvent(event, data) {
    switch (event) {
      case 'start':
        if (data.item_count) setTotalItems(data.item_count)
        break
      case 'skill_approval': {
        setApprovalData(data)
        setSelectedItems(new Set((data.items || []).map(it => it.id)))
        setStatus('awaiting_approval')
        break
      }
      case 'awaiting_approval':
        break
      case 'section':
        setResults(prev => [...prev, { section: data.label }])
        break
      case 'progress': {
        if (data.total) setTotalItems(data.total)
        setCompletedItems(data.executed || 0)
        setCurrentTool(null)
        setResults(prev => [...prev, {
          success: true,
          text: data.entity_name || `Item ${data.executed}`,
          detail: data.entity_flag || null,
          time: `${(Math.random() * 0.4 + 0.1).toFixed(1)}s`,
        }])
        break
      }
      case 'action': {
        setCurrentTool(data.tool || 'processing')
        setResults(prev => [...prev, {
          action: true,
          text: data.tool || 'processing',
        }])
        break
      }
      case 'complete':
        setStatus('complete')
        break
      case 'summary':
        setSummary(data.content)
        break
      case 'warning':
        setResults(prev => [...prev, { action: true, text: data.message }])
        break
      case 'error':
        setStatus('error')
        onError?.(data.error || 'Run failed')
        setResults(prev => [...prev, {
          success: false,
          text: data.error || 'Run failed',
          time: '',
        }])
        break
    }
  }

  useEffect(() => {
    const ctrl = api.executeSkillSSE(skill.id, handleSSEEvent)
    controllerRef.current = ctrl
    return () => ctrl?.abort()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleApprove = () => {
    if (!approvalData) return
    const allItems = approvalData.items || []
    const excluded = allItems.filter(it => !selectedItems.has(it.id)).map(it => it.id)
    setStatus('running')
    setTotalItems(selectedItems.size)
    setResults([])
    const ctrl = api.approveSkill(
      skill.id,
      approvalData.execution_id,
      'approve',
      excluded,
      handleSSEEvent,
    )
    controllerRef.current = ctrl
  }

  const handleReject = () => {
    if (!approvalData) return
    fetch(`/api/skills/${skill.id}/approve/${approvalData.execution_id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'reject' }),
    }).catch(() => {})
    onClose()
  }

  const toggleItem = (id) => {
    setSelectedItems(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center overlay-scrim"
      style={{ backgroundColor: 'rgba(11, 13, 17, 0.92)' }}>
      <div className="w-full max-w-2xl max-h-[85vh] flex flex-col bg-slate rounded-2xl border border-border-subtle
        shadow-2xl overlay-panel overflow-hidden">

        {/* Header */}
        <div className="flex items-start justify-between p-6 pb-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <Zap size={16} className="text-mint" />
              <h2 className="text-lg font-semibold text-primary truncate">{skill.name}</h2>
              <TypeBadge scheduled cadence={skill.schedule_cadence} time={skill.schedule_time} />
            </div>
            <p className="text-sm text-tertiary">{skill.description}</p>
          </div>
          <button
            onClick={() => { controllerRef.current?.abort(); onClose() }}
            className="ml-4 p-1.5 rounded-lg text-tertiary hover:text-secondary hover:bg-ash
              transition-all duration-200 ease-out active:scale-95"
          >
            <X size={16} />
          </button>
        </div>

        {/* Approval card */}
        {status === 'awaiting_approval' && approvalData && (
          <div className="flex-1 overflow-auto px-6 pb-2 min-h-0">
            <div className="bg-void/50 rounded-xl border border-violet/20 p-4">
              <div className="flex items-center gap-2 mb-3">
                <Users size={14} className="text-violet" />
                <span className="text-xs font-semibold text-primary">
                  {approvalData.item_count} items ready
                </span>
                <span className="text-[10px] text-tertiary ml-auto">
                  {selectedItems.size} selected
                </span>
              </div>
              <div className="space-y-1 max-h-[320px] overflow-auto">
                {(approvalData.items || []).map((item) => (
                  <label
                    key={item.id}
                    className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-ash/50
                      cursor-pointer transition-all duration-150"
                  >
                    <input
                      type="checkbox"
                      checked={selectedItems.has(item.id)}
                      onChange={() => toggleItem(item.id)}
                      className="w-3.5 h-3.5 rounded border-border-subtle accent-mint"
                    />
                    <div className="flex-1 min-w-0">
                      <span className="text-xs text-primary">{item.label || item.id}</span>
                      {item.detail && (
                        <span className="text-[11px] text-tertiary ml-2">— {item.detail}</span>
                      )}
                    </div>
                  </label>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Results cascade (running/complete/error states) */}
        {(status === 'running' || status === 'complete' || status === 'error') && (
          <div className="flex-1 overflow-auto px-6 pb-2 min-h-0">
            <div className="bg-void/50 rounded-xl border border-border-subtle p-3 min-h-[200px] max-h-[380px] overflow-auto">
              {results.length === 0 && status === 'running' && (
                <div className="flex items-center justify-center h-32 text-tertiary text-sm gap-2">
                  <Loader2 size={14} className="animate-spin" /> Starting execution...
                </div>
              )}
              {results.map((r, i) => (
                r.section ? (
                  <div
                    key={i}
                    className="flex items-center gap-2 px-3 pt-3 pb-1 cascade-up-item"
                    style={{ animationDelay: `${i * 100}ms` }}
                  >
                    <div className="h-px flex-1 bg-border-subtle" />
                    <span className="text-[10px] font-semibold text-tertiary tracking-widest uppercase">
                      {r.section}
                    </span>
                    <div className="h-px flex-1 bg-border-subtle" />
                  </div>
                ) : r.action ? (
                  <div
                    key={i}
                    className="flex items-center gap-2 px-3 py-1.5 cascade-up-item"
                    style={{ animationDelay: `${i * 60}ms` }}
                  >
                    <Loader2 size={10} className="animate-spin text-mint/60 flex-shrink-0" />
                    <span className="text-[11px] text-tertiary">{r.text}</span>
                  </div>
                ) : (
                  <div
                    key={i}
                    className="flex items-center gap-3 px-3 py-2 rounded-lg cascade-up-item"
                    style={{ animationDelay: `${i * 100}ms` }}
                  >
                    {r.success
                      ? <CheckCircle2 size={14} className="text-mint flex-shrink-0" />
                      : <AlertCircle size={14} className="text-coral flex-shrink-0" />
                    }
                    <span className={`text-xs flex-1 ${r.success ? 'text-secondary' : 'text-coral'}`}>
                      {r.text}
                      {r.detail && (
                        <span className="text-tertiary ml-2">— {r.detail}</span>
                      )}
                    </span>
                    {r.time && (
                      <span className="text-[10px] text-tertiary tabular-nums flex-shrink-0">{r.time}</span>
                    )}
                  </div>
                )
              ))}
              <div ref={resultsEndRef} />
            </div>

            {/* Summary report */}
            {summary && (
              <div className="mt-3 bg-void/30 rounded-xl border border-mint/10 p-4 cascade-up-item">
                <div className="flex items-center gap-2 mb-2">
                  <FileText size={12} className="text-mint" />
                  <span className="text-[10px] font-semibold text-mint tracking-widest uppercase">Report</span>
                </div>
                <div className="text-xs text-secondary leading-relaxed prose prose-invert prose-xs max-w-none
                  prose-headings:text-primary prose-headings:text-xs prose-headings:font-semibold prose-headings:mt-3 prose-headings:mb-1
                  prose-p:my-1 prose-ul:my-1 prose-li:my-0.5 prose-strong:text-primary">
                  <Markdown remarkPlugins={[remarkGfm]}>{summary}</Markdown>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Resolving state */}
        {status === 'resolving' && (
          <div className="flex-1 flex items-center justify-center px-6">
            <div className="flex items-center gap-2 text-tertiary text-sm">
              <Loader2 size={14} className="animate-spin text-mint" /> Resolving items...
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="px-6 py-4 border-t border-border-subtle flex items-center justify-between">
          {status === 'awaiting_approval' ? (
            <>
              <span className="text-xs text-tertiary">
                Deselect items to exclude from this run
              </span>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleReject}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-ash text-secondary text-xs font-semibold
                    border border-border-subtle hover:text-primary transition-all duration-200 ease-out active:scale-95"
                >
                  Cancel
                </button>
                <button
                  onClick={handleApprove}
                  disabled={selectedItems.size === 0}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-mint text-inverse text-xs font-semibold
                    hover:bg-mint/90 transition-all duration-200 ease-out active:scale-95
                    disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Play size={12} /> Approve & Run ({selectedItems.size})
                </button>
              </div>
            </>
          ) : (
            <>
              <div className="flex items-center gap-4 text-xs">
                <span className={`font-medium ${status === 'complete' ? 'text-mint' : 'text-secondary'}`}>
                  {status === 'complete'
                    ? `${completedItems} completed`
                    : status === 'running'
                      ? `${completedItems}${totalItems ? '/' + totalItems : ''} processed`
                      : ''
                  }
                </span>
                {currentTool && status === 'running' && (
                  <span className="text-tertiary flex items-center gap-1.5 truncate max-w-[200px]">
                    <Loader2 size={10} className="animate-spin text-mint flex-shrink-0" />
                    {currentTool}
                  </span>
                )}
                {status === 'complete' && (
                  <span className="text-tertiary flex items-center gap-1">
                    <Clock size={11} />
                    ~{Math.max(1, completedItems * 2)} min saved
                  </span>
                )}
              </div>
              {status === 'complete' ? (
                <button
                  onClick={onClose}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-mint text-inverse text-xs font-semibold
                    hover:bg-mint/90 transition-all duration-200 ease-out active:scale-95"
                >
                  <Check size={12} /> Done
                </button>
              ) : status === 'error' ? (
                <button
                  onClick={onClose}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-coral/10 text-coral text-xs font-semibold
                    hover:bg-coral/20 transition-all duration-200 ease-out active:scale-95"
                >
                  Close
                </button>
              ) : (
                <span className="flex items-center gap-2 text-xs text-mint">
                  <Loader2 size={12} className="animate-spin" /> Running...
                </span>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

/* ─── Patient Memory Row ──────────────────────────────── */
function PatientMemoryRow({ patient, onClick, index }) {
  const topMemory = patient.memories?.[0]
  return (
    <button
      onClick={onClick}
      className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg
        hover:bg-ash/50 transition-all duration-200 ease-out active:scale-95 text-left cascade-item"
      style={{ animationDelay: `${index * 60}ms` }}
    >
      <div className="w-8 h-8 rounded-full bg-violet/10 flex items-center justify-center flex-shrink-0">
        <Brain size={14} className="text-violet" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p className="text-primary text-sm font-medium truncate">{patient.patient_name}</p>
          <span className="text-[10px] text-tertiary">{patient.memory_count} memories</span>
        </div>
        {topMemory && (
          <div className="flex items-center gap-1.5 mt-0.5">
            <MemoryIcon type={topMemory.type} />
            <p className="text-tertiary text-xs truncate">{topMemory.content}</p>
          </div>
        )}
      </div>
      <ArrowRight size={14} className="text-tertiary flex-shrink-0" />
    </button>
  )
}

/* ─── Pipeline Status Strip ──────────────────────────── */
function PipelineStatusStrip({ onComplete }) {
  const { addActivity } = useApp()
  const [state, setState] = useState(null)
  const [running, setRunning] = useState(false)
  const pollRef = useRef(null)

  const fetchStatus = useCallback(() => {
    api.pipelineStatus().then(setState).catch(() => {})
  }, [])

  useEffect(() => {
    fetchStatus()
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [fetchStatus])

  useEffect(() => {
    if (running) {
      pollRef.current = setInterval(() => {
        api.pipelineStatus().then(s => {
          setState(s)
          if (s.status !== 'running') {
            setRunning(false)
            clearInterval(pollRef.current)
            pollRef.current = null
            if (s.status === 'completed') {
              addActivity({
                id: `pipeline-done-${Date.now()}`,
                text: `Analysis complete — ${s.skills_generated} skills, ${s.patterns_detected} patterns`,
                active: false,
                icon: '✦',
              })
              onComplete?.()
            }
          }
        })
      }, 3000)
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [running, addActivity, onComplete])

  const handleRun = () => {
    setRunning(true)
    setState(s => ({ ...s, status: 'running', current_stage: 'Detecting patterns', stage_index: 0 }))
    addActivity({
      id: `pipeline-start-${Date.now()}`,
      text: 'Analysing patterns...',
      active: true,
      icon: '◎',
    })
    api.runAnalysis().then(result => {
      setState(s => ({
        ...s,
        status: result.status === 'failed' ? 'failed' : result.status === 'cancelled' ? 'cancelled' : 'completed',
        patterns_detected: result.patterns_detected || s?.patterns_detected || 0,
        skills_generated: result.skills_generated || s?.skills_generated || 0,
        memories_generated: result.memories_generated || s?.memories_generated || 0,
        last_run_at: new Date().toISOString(),
        error_message: result.error || null,
        current_stage: null,
      }))
      setRunning(false)
      if (result.status === 'complete' || result.status === 'completed') {
        addActivity({
          id: `pipeline-done-${Date.now()}`,
          text: `Analysis complete — ${result.skills_generated || 0} skills, ${result.patterns_detected || 0} patterns`,
          active: false,
          icon: '✦',
        })
        onComplete?.()
      }
    }).catch(err => {
      setState(s => ({ ...s, status: 'failed', error_message: err.message, current_stage: null }))
      setRunning(false)
    })
  }

  const handleCancel = () => {
    api.cancelAnalysis().catch(() => {})
    addActivity({
      id: `pipeline-cancel-${Date.now()}`,
      text: 'Analysis cancelled',
      active: false,
      icon: '✕',
    })
  }

  const isRunning = state?.status === 'running' || running

  function timeAgo(iso) {
    if (!iso) return null
    const diff = Date.now() - new Date(iso).getTime()
    const mins = Math.floor(diff / 60000)
    if (mins < 1) return 'just now'
    if (mins < 60) return `${mins}m ago`
    const hrs = Math.floor(mins / 60)
    if (hrs < 24) return `${hrs}h ago`
    return `${Math.floor(hrs / 24)}d ago`
  }

  function formatEta(ms) {
    if (!ms) return null
    const secs = Math.round(ms / 1000)
    if (secs < 60) return `~${secs}s`
    return `~${Math.round(secs / 60)}m`
  }

  const PIPELINE_STEPS = ['Detecting patterns', 'Extracting context', 'Generating skills', 'Detecting memories']

  return (
    <div className="mb-5 bg-graphite rounded-xl border border-border-subtle px-4 py-3 space-y-2.5">
      {/* Top row: status + actions */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 text-xs">
          {isRunning ? (
            <>
              <Loader2 size={13} className="text-mint animate-spin" />
              <span className="text-mint font-medium">Running analysis</span>
              {state?.last_duration_ms && (
                <span className="text-tertiary">· ETA {formatEta(state.last_duration_ms)}</span>
              )}
            </>
          ) : state?.status === 'failed' ? (
            <>
              <AlertCircle size={13} className="text-coral" />
              <span className="text-coral font-medium">Last run failed</span>
            </>
          ) : state?.status === 'cancelled' ? (
            <>
              <X size={13} className="text-tertiary" />
              <span className="text-tertiary font-medium">Cancelled</span>
            </>
          ) : state?.last_run_at ? (
            <>
              <Activity size={13} className="text-violet" />
              <span className="text-secondary">
                Last analysis: <span className="text-primary font-medium">{timeAgo(state.last_run_at)}</span>
                {' · '}
                {state.patterns_detected} patterns, {state.skills_generated} new skills
                {state.skills_skipped ? <span className="text-tertiary"> ({state.skills_skipped} skipped)</span> : ''}
              </span>
            </>
          ) : (
            <>
              <Activity size={13} className="text-tertiary" />
              <span className="text-tertiary">No analysis run yet</span>
            </>
          )}
        </div>

        <div className="flex-1" />

        {state?.auto_enabled && state?.schedule_time && !isRunning && (
          <span className="text-[10px] text-tertiary flex items-center gap-1 px-2 py-0.5 rounded-full bg-void/50">
            <Clock size={9} /> Auto: Daily {state.schedule_time}
          </span>
        )}

        {isRunning && (
          <button
            onClick={handleCancel}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold
              transition-all duration-200 ease-out active:scale-95
              bg-coral/10 text-coral hover:bg-coral/20 border border-coral/20"
          >
            <X size={12} />
            Cancel
          </button>
        )}

        {!isRunning && (
          <button
            onClick={handleRun}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold
              transition-all duration-200 ease-out active:scale-95
              bg-mint/10 text-mint hover:bg-mint/20 border border-mint/20"
          >
            <RotateCw size={12} />
            Run Analysis
          </button>
        )}
      </div>

      {/* Pipeline steps (visible while running) */}
      {isRunning && (
        <div className="flex items-center gap-1">
          {PIPELINE_STEPS.map((step, i) => {
            const activeIndex = state?.stage_index ?? 0
            const isActive = i === activeIndex
            const isDone = i < activeIndex
            return (
              <div key={step} className="flex items-center gap-1 flex-1 min-w-0">
                <div className={`
                  flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-medium w-full
                  transition-all duration-300
                  ${isActive ? 'bg-mint/10 text-mint border border-mint/20' : ''}
                  ${isDone ? 'text-mint/60' : ''}
                  ${!isActive && !isDone ? 'text-tertiary/50' : ''}
                `}>
                  {isActive ? (
                    <Loader2 size={10} className="animate-spin flex-shrink-0" />
                  ) : isDone ? (
                    <CheckCircle2 size={10} className="flex-shrink-0" />
                  ) : (
                    <span className="w-2.5 h-2.5 rounded-full border border-current opacity-40 flex-shrink-0" />
                  )}
                  <span className="truncate">{step}</span>
                </div>
                {i < PIPELINE_STEPS.length - 1 && (
                  <ArrowRight size={10} className={`flex-shrink-0 ${isDone ? 'text-mint/40' : 'text-tertiary/20'}`} />
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

/* ─── Pipeline History ───────────────────────────────── */
function PipelineHistory({ refreshKey }) {
  const [runs, setRuns] = useState(null)
  const [expanded, setExpanded] = useState(false)

  useEffect(() => {
    api.pipelineRuns().then(d => setRuns(d.runs)).catch(() => {})
  }, [refreshKey])

  if (!runs || runs.length === 0) return null

  function formatDate(iso) {
    if (!iso) return '—'
    const d = new Date(iso)
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) +
      ' ' + d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
  }

  function formatDuration(ms) {
    if (!ms) return '—'
    const secs = Math.round(ms / 1000)
    if (secs < 60) return `${secs}s`
    return `${Math.floor(secs / 60)}m ${secs % 60}s`
  }

  const statusColors = {
    completed: 'text-mint',
    failed: 'text-coral',
    cancelled: 'text-tertiary',
    running: 'text-mint animate-pulse',
  }

  return (
    <div className="mb-5">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-xs text-tertiary hover:text-secondary transition-colors mb-2"
      >
        <ChevronDown size={12} className={`transition-transform duration-200 ${expanded ? '' : '-rotate-90'}`} />
        <Clock size={11} />
        <span>Pipeline History</span>
        <span className="text-[10px] opacity-60">({runs.length} runs)</span>
      </button>

      {expanded && (
        <div className="bg-graphite rounded-xl border border-border-subtle overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border-subtle text-tertiary">
                <th className="text-left px-3 py-2 font-medium">Date</th>
                <th className="text-left px-3 py-2 font-medium">Duration</th>
                <th className="text-left px-3 py-2 font-medium">Status</th>
                <th className="text-right px-3 py-2 font-medium">Patterns</th>
                <th className="text-right px-3 py-2 font-medium">Skills</th>
                <th className="text-right px-3 py-2 font-medium">Skipped</th>
                <th className="text-right px-3 py-2 font-medium">Memories</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle">
              {runs.map(run => (
                <tr key={run.id} className="text-secondary hover:bg-void/30 transition-colors">
                  <td className="px-3 py-2 text-primary">{formatDate(run.started_at)}</td>
                  <td className="px-3 py-2">{formatDuration(run.duration_ms)}</td>
                  <td className={`px-3 py-2 font-medium capitalize ${statusColors[run.status] || 'text-tertiary'}`}>
                    {run.status}
                  </td>
                  <td className="px-3 py-2 text-right">{run.patterns_detected || 0}</td>
                  <td className="px-3 py-2 text-right">{run.skills_generated || 0}</td>
                  <td className="px-3 py-2 text-right text-tertiary">{run.skills_skipped || 0}</td>
                  <td className="px-3 py-2 text-right">{run.memories_generated || 0}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

/* ─── Main Insights View ──────────────────────────────── */
export default function InsightsView() {
  const { trackAction, navigateTo, addActivity, setScreenContext } = useApp()
  const [skills, setSkills] = useState(null)
  const [memories, setMemories] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [executingSkill, setExecutingSkill] = useState(null)
  const [detailSkill, setDetailSkill] = useState(null)
  const [newIds, setNewIds] = useState(new Set())
  const [runError, setRunError] = useState(null)
  const [historyKey, setHistoryKey] = useState(0)
  const seenTimerRef = useRef(null)

  useEffect(() => {
    loadData()
    return () => { if (seenTimerRef.current) clearTimeout(seenTimerRef.current) }
  }, [])

  function loadData() {
    setLoading(true)
    setLoadError(null)
    setHistoryKey(k => k + 1)
    Promise.all([
      api.skills().then(d => d.skills).catch(err => { setLoadError(err.message || 'Failed to load skills'); return null }),
      api.memoriesSummary().catch(() => getDemoMemories()),
    ]).then(([sk, mem]) => {
      setSkills(sk)
      setMemories(mem)
      setLoading(false)
    })
  }

  const sk = skills || []
  const mem = memories || getDemoMemories()

  const sortedSkills = sortByImpact(sk)

  useEffect(() => {
    if (sortedSkills.length === 0) return
    const seen = getSeenIds()
    const fresh = new Set()
    sortedSkills.forEach(s => {
      if (!seen.has(s.id)) fresh.add(s.id)
    })
    setNewIds(fresh)
    if (fresh.size > 0) {
      seenTimerRef.current = setTimeout(() => {
        markAllSeen(sortedSkills.map(s => s.id))
        setNewIds(new Set())
      }, 5000)
    }
  }, [sortedSkills.length]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (detailSkill) {
      setScreenContext({
        modalOpen: 'skill-detail',
        skillId: detailSkill.id,
        skillName: detailSkill.name,
        skillScheduled: detailSkill.scheduled,
        skillDescription: detailSkill.description,
      })
    } else {
      setScreenContext(null)
    }
  }, [detailSkill, setScreenContext])

  const handleEnable = (skill) => {
    trackAction('enable_skill', skill.name, 'skill', skill.id)
    const wasEnabled = skill.status === 'enabled'
    // Optimistic update
    setSkills(prev => (prev || []).map(s => s.id === skill.id
      ? { ...s, status: wasEnabled ? 'pending_review' : 'enabled' }
      : s))
    if (detailSkill?.id === skill.id) {
      setDetailSkill({ ...detailSkill, status: wasEnabled ? 'pending_review' : 'enabled' })
    }
    markAllSeen([skill.id])
    setNewIds(prev => {
      const next = new Set(prev); next.delete(skill.id); return next
    })
    if (!wasEnabled) {
      api.enableSkill(skill.id).catch(err => {
        setSkills(prev => (prev || []).map(s => s.id === skill.id ? { ...s, status: 'pending_review' } : s))
      })
    } else {
      api.disableSkill(skill.id).catch(err => {
        setSkills(prev => (prev || []).map(s => s.id === skill.id ? { ...s, status: 'enabled' } : s))
      })
    }
    addActivity({
      id: `enable-${skill.id}-${Date.now()}`,
      text: wasEnabled ? `Disabled: ${skill.name}` : `Enabled: ${skill.name}`,
      active: true,
      icon: wasEnabled ? '◦' : '✦',
    })
  }

  const handleRun = (skill) => {
    if (skill.status !== 'enabled') {
      setRunError(`Enable ${skill.name} first before running.`)
      setTimeout(() => setRunError(null), 4000)
      return
    }
    trackAction('run_skill', skill.name, 'skill', skill.id)
    setDetailSkill(null)
    setExecutingSkill(skill)
    addActivity({
      id: `run-${skill.id}-${Date.now()}`,
      text: `Running: ${skill.name}`,
      active: true,
      icon: '◎',
    })
  }

  const handleSchedule = (skill, updates) => {
    api.scheduleSkill(skill.id, updates).catch(() => {})
    setSkills(prev => (prev || []).map(s => s.id === skill.id
      ? { ...s, schedule_cadence: updates.cadence ?? s.schedule_cadence, schedule_time: updates.time ?? s.schedule_time, scheduled: 1 }
      : s))
    if (detailSkill?.id === skill.id) {
      setDetailSkill({ ...detailSkill,
        schedule_cadence: updates.cadence ?? detailSkill.schedule_cadence,
        schedule_time: updates.time ?? detailSkill.schedule_time,
        scheduled: 1,
      })
    }
  }

  const handleAddSchedule = (skill) => {
    const updates = { cadence: 'daily', time: '08:00' }
    handleSchedule(skill, updates)
  }

  const handleRunComplete = () => {
    if (executingSkill) {
      addActivity({
        id: `done-${executingSkill.id}-${Date.now()}`,
        text: `Completed: ${executingSkill.name}`,
        active: false,
        icon: '✓',
      })
    }
    setExecutingSkill(null)
    loadData()
  }

  const handlePatientClick = (patient) => {
    trackAction('view_patient_memories', patient.patient_name, 'patient', patient.patient_id)
    navigateTo('patients', { patientId: patient.patient_id, tab: 'memory' })
  }

  const openDetail = (skill) => {
    trackAction('view_skill_detail', skill.name, 'skill', skill.id)
    setDetailSkill(skill)
  }

  return (
    <div className="h-full overflow-auto">
      <div className="p-6 max-w-5xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-semibold text-primary tracking-tight flex items-center gap-2">
            <Sparkles size={22} className="text-violet" />
            Insights
          </h1>
          <p className="text-sm text-tertiary mt-1">What I learned from analysing your practice</p>
        </div>

        {/* Pipeline Status */}
        <PipelineStatusStrip onComplete={loadData} />

        {/* Pipeline History */}
        <PipelineHistory refreshKey={historyKey} />

        {/* System Health Metrics */}
        <HealthPanel />

        {/* Inline run error */}
        {runError && (
          <div className="mb-4 bg-coral/10 border border-coral/30 rounded-xl px-4 py-3 flex items-center gap-2 text-coral text-sm
            animate-[count-up-fade_300ms_ease-out]">
            <AlertCircle size={14} /> {runError}
          </div>
        )}

        {/* Skills Section */}
        <section className="mb-8" data-testid="skills-section">
          <div className="flex items-center gap-2 mb-4">
            <Sparkles size={16} className="text-mint" />
            <h2 className="text-sm font-semibold text-primary tracking-tight">
              Skills
            </h2>
            <span className="text-[10px] text-tertiary tracking-widest uppercase">
              {sortedSkills.length === 1 ? '1 skill' : `${sortedSkills.length} skills`}
            </span>
          </div>

          {loading ? (
            <div className="space-y-2" data-testid="skills-loading">
              {[1,2,3].map(i => (
                <div key={i} className="bg-graphite rounded-xl border border-border-subtle/50 px-4 py-3 h-[76px] animate-pulse" />
              ))}
            </div>
          ) : loadError ? (
            <div className="bg-coral/5 rounded-xl border border-coral/30 p-5 flex items-start gap-3" data-testid="skills-error">
              <AlertCircle size={16} className="text-coral flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-primary text-sm font-medium">Couldn't load skills</p>
                <p className="text-tertiary text-xs mt-1">{loadError}</p>
                <button
                  onClick={loadData}
                  className="mt-3 flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-ash text-secondary text-xs font-semibold
                    border border-border-subtle hover:text-primary transition-all duration-200 ease-out active:scale-95"
                >
                  Retry
                </button>
              </div>
            </div>
          ) : sortedSkills.length === 0 ? (
            <div className="bg-graphite rounded-xl border border-border-subtle p-8 text-center" data-testid="skills-empty">
              <Sparkles size={24} className="text-mint/30 mx-auto mb-2" />
              <p className="text-tertiary text-sm">No skills learned yet. Run the analysis pipeline to discover patterns.</p>
            </div>
          ) : (
            <div className="space-y-2">
              {sortedSkills.map((skill, i) => (
                <SkillRow
                  key={skill.id}
                  skill={skill}
                  isNew={newIds.has(skill.id)}
                  onEnable={handleEnable}
                  onRun={handleRun}
                  onClick={() => openDetail(skill)}
                  index={i}
                />
              ))}
            </div>
          )}
        </section>

        {/* Patient Memories Section */}
        <section>
          <div className="flex items-center gap-2 mb-4">
            <Heart size={16} className="text-coral" />
            <h2 className="text-sm font-semibold text-primary tracking-tight">
              Patient Memories
            </h2>
            <span className="text-[10px] text-tertiary tracking-widest uppercase">
              {mem.total_memories || 0} things about {mem.patient_count || 0} patients
            </span>
          </div>

          {mem.type_counts && Object.keys(mem.type_counts).length > 0 && (
            <div className="flex items-center gap-3 mb-4 flex-wrap">
              {Object.entries(mem.type_counts).map(([type, count]) => (
                <div key={type} className="flex items-center gap-1.5 bg-graphite rounded-lg px-2.5 py-1.5
                  border border-border-subtle text-xs text-secondary">
                  <MemoryIcon type={type} />
                  <span className="capitalize">{type.replace(/_/g, ' ')}</span>
                  <span className="text-tertiary">({count})</span>
                </div>
              ))}
            </div>
          )}

          {(!mem.patients || mem.patients.length === 0) ? (
            <div className="bg-graphite rounded-xl border border-border-subtle p-8 text-center">
              <Heart size={24} className="text-coral/30 mx-auto mb-2" />
              <p className="text-tertiary text-sm">No patient memories recorded yet.</p>
            </div>
          ) : (
            <div className="bg-graphite rounded-xl border border-border-subtle divide-y divide-border-subtle">
              {mem.patients.slice(0, 12).map((patient, i) => (
                <PatientMemoryRow
                  key={patient.patient_id}
                  patient={patient}
                  onClick={() => handlePatientClick(patient)}
                  index={i}
                />
              ))}
              {mem.patients.length > 12 && (
                <div className="px-3 py-2 text-center">
                  <p className="text-xs text-tertiary">+ {mem.patients.length - 12} more patients</p>
                </div>
              )}
            </div>
          )}
        </section>
      </div>

      {/* Detail Modal */}
      {detailSkill && (
        <SkillDetailModal
          skill={detailSkill}
          isNew={newIds.has(detailSkill.id)}
          onClose={() => setDetailSkill(null)}
          onEnable={handleEnable}
          onRun={handleRun}
          onSchedule={handleSchedule}
          onAddSchedule={handleAddSchedule}
        />
      )}

      {/* Execution Overlay */}
      {executingSkill && (
        <ExecutionOverlay
          skill={executingSkill}
          onClose={handleRunComplete}
          onError={(err) => {
            setRunError(err)
            setTimeout(() => setRunError(null), 4000)
          }}
        />
      )}
    </div>
  )
}

function getDemoMemories() {
  return {
    total_memories: 0,
    patient_count: 0,
    type_counts: {},
    patients: [],
  }
}
