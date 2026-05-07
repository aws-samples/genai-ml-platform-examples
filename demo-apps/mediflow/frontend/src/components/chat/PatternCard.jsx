import { useState, useEffect } from 'react'
import { Sparkles } from 'lucide-react'

export default function PatternCard({ data }) {
  if (!data) return null
  const [barWidth, setBarWidth] = useState(0)

  useEffect(() => {
    const t = setTimeout(() => setBarWidth(data.frequency || 0), 100)
    return () => clearTimeout(t)
  }, [data.frequency])

  return (
    <div className="bg-graphite rounded-xl border border-border-subtle border-l-4 border-l-violet p-4 animate-[count-up-fade_400ms_ease-out]">
      <div className="flex items-center gap-2 mb-2">
        <Sparkles size={14} className="text-violet" />
        <span className="text-[11px] font-semibold text-violet tracking-wider uppercase">Pattern</span>
      </div>
      <p className="text-primary text-sm font-medium mb-1">{data.name}</p>
      {data.description && (
        <p className="text-tertiary text-xs italic mb-3">"{data.description}"</p>
      )}
      <div className="space-y-2">
        <div>
          <div className="flex items-center justify-between text-xs mb-1">
            <span className="text-tertiary">Frequency</span>
            <span className="text-primary font-medium">{data.frequency}%</span>
          </div>
          <div className="h-1.5 bg-void rounded-full overflow-hidden">
            <div
              className="h-full bg-violet rounded-full transition-all duration-1000 ease-out"
              style={{ width: `${barWidth}%` }}
            />
          </div>
        </div>
        {data.sessions && (
          <p className="text-xs text-tertiary">
            Sessions: {data.sessions_matched} of {data.sessions}
          </p>
        )}
      </div>
    </div>
  )
}
