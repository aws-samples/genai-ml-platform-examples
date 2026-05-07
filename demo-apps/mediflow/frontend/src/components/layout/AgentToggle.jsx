import { useEffect, useState } from 'react'
import { Bot } from 'lucide-react'
import { useApp } from '../../context/AppContext'

// Module-level flag: the first-load nudge fires once per session, not every time
// the toggle remounts (e.g. after the user closes the panel again).
let hasNudgedThisSession = false

export default function AgentToggle() {
  const { agentPanelOpen, agentPanelWidth, agentState, toggleAgentPanel } = useApp()
  const [nudging, setNudging] = useState(!hasNudgedThisSession)

  useEffect(() => {
    if (hasNudgedThisSession) return
    hasNudgedThisSession = true
    const t = setTimeout(() => setNudging(false), 1500)
    return () => clearTimeout(t)
  }, [])

  const isActive = agentState === 'listening' || agentState === 'thinking' || agentState === 'acting'
  const isInsight = agentState === 'insight_ready'

  let colorClasses = 'text-secondary hover:text-primary'
  let shadowClass = ''
  let pulseClass = ''

  if (isInsight) {
    colorClasses = 'text-violet'
    shadowClass = 'shadow-[0_0_8px_rgba(212,168,255,0.35)]'
  } else if (isActive || nudging) {
    colorClasses = 'text-mint'
    shadowClass = 'shadow-[0_0_8px_rgba(0,210,229,0.35)]'
    pulseClass = 'animate-pulse'
  }

  // Tab slides between viewport right edge (closed) and panel's left edge (open).
  // Same 300ms ease-out curve as the panel wrapper so they move together.
  const rightStyle = agentPanelOpen ? { right: agentPanelWidth } : { right: 0 }

  return (
    <button
      onClick={toggleAgentPanel}
      aria-label={agentPanelOpen ? 'Close assistant' : 'Open assistant'}
      title={agentPanelOpen ? 'Close Assistant' : 'Open Assistant'}
      style={{ top: '40%', ...rightStyle }}
      className={`
        fixed z-40 w-7 h-20 rounded-l-lg bg-slate border border-r-0 border-border-subtle
        flex items-center justify-center
        transition-all duration-300 ease-out
        active:scale-95 hover:-translate-x-0.5
        ${colorClasses} ${shadowClass}
      `}
    >
      <Bot size={20} strokeWidth={1.5} className={pulseClass} />
    </button>
  )
}
