import { useApp } from '../../context/AppContext'
import {
  Sun, Calendar, Users, Stethoscope, Mail, Sparkles, Settings,
} from 'lucide-react'

const navItems = [
  { id: 'today', icon: Sun, label: 'Today' },
  { id: 'calendar', icon: Calendar, label: 'Calendar' },
  { id: 'patients', icon: Users, label: 'Patients' },
  { id: 'practitioners', icon: Stethoscope, label: 'Practitioners' },
  { id: 'comms', icon: Mail, label: 'Comms' },
  { id: 'insights', icon: Sparkles, label: 'Insights' },
]

export default function Sidebar() {
  const { activeView, setView, agentHighlight } = useApp()

  return (
    <nav className="relative z-20 w-16 flex-shrink-0 bg-slate flex flex-col items-center py-4 border-r border-border-subtle">
      {/* Navigation */}
      <div className="flex-1 flex flex-col gap-1 w-full px-2">
        {navItems.map(({ id, icon: Icon, label }) => {
          const isActive = activeView === id
          const isInsights = id === 'insights'
          const accent = isInsights ? 'violet' : 'mint'
          const isAgentTarget = agentHighlight?.target === 'nav' && agentHighlight?.id === id
          return (
            <button
              key={id}
              onClick={() => setView(id)}
              className={`
                group relative w-full aspect-square rounded-xl flex items-center justify-center
                transition-all duration-200 active:scale-95
                ${isAgentTarget ? 'agent-blink ring-2 ring-mint/50' : ''}
                ${isActive
                  ? isInsights ? 'bg-violet/10 text-violet' : 'bg-mint/10 text-mint'
                  : isInsights ? 'text-violet/70 hover:text-violet hover:bg-violet/5' : 'text-tertiary hover:text-secondary hover:bg-white/[0.04]'
                }
              `}
              aria-label={label}
            >
              <div className={`absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 bg-${accent} rounded-r-full transition-all duration-200 ${isActive ? 'opacity-100 scale-y-100' : 'opacity-0 scale-y-0'}`} />
              <Icon size={20} strokeWidth={1.5} />
              {/* Tooltip */}
              <div className="absolute left-full ml-3 px-2.5 py-1 bg-ash text-primary text-xs font-medium rounded-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50">
                {label}
              </div>
            </button>
          )
        })}
      </div>

      {/* Settings */}
      <button
        className="w-full px-2 aspect-square flex items-center justify-center text-tertiary hover:text-secondary transition-all duration-200 active:scale-95"
        title="Settings"
      >
        <Settings size={20} strokeWidth={1.5} />
      </button>
    </nav>
  )
}
