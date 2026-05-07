import { useState, useEffect } from 'react'

function AnimatedCounter({ end, duration = 1200, suffix = '' }) {
  const [val, setVal] = useState(0)
  useEffect(() => {
    const start = Date.now()
    const step = () => {
      const elapsed = Date.now() - start
      const progress = Math.min(elapsed / duration, 1)
      // Ease-out decelerate
      const eased = 1 - Math.pow(1 - progress, 3)
      setVal(Math.round(eased * end))
      if (progress < 1) requestAnimationFrame(step)
    }
    requestAnimationFrame(step)
  }, [end, duration])

  return <>{val}{suffix}</>
}

export default function ImpactCard({ data, onActivateAll, onReviewEach }) {
  if (!data) return null
  const metrics = data.metrics || []

  return (
    <div className="bg-graphite rounded-xl border border-border-subtle overflow-hidden animate-[count-up-fade_400ms_ease-out]">
      {/* Gradient top border */}
      <div className="h-[3px]" style={{ background: 'linear-gradient(135deg, #00D2E5 0%, #D4A8FF 100%)' }} />

      <div className="p-4">
        <div className="grid grid-cols-4 gap-3 mb-4">
          {metrics.map((m, i) => (
            <div key={i} className="text-center">
              <p className="text-primary text-2xl font-bold tracking-tight leading-none">
                <AnimatedCounter end={m.value} suffix={m.suffix || ''} />
              </p>
              <p className="text-tertiary text-[10px] font-medium tracking-widest uppercase mt-1">
                {m.label}
              </p>
            </div>
          ))}
        </div>

        <div className="flex gap-2">
          <button
            onClick={onActivateAll}
            className="flex-1 py-2 text-xs font-medium rounded-lg bg-mint text-inverse hover:bg-mint/90 transition-all duration-200 active:scale-95"
            style={{ boxShadow: '0 0 20px rgba(99,220,190,0.15)' }}
          >
            Activate All
          </button>
          <button
            onClick={onReviewEach}
            className="flex-1 py-2 text-xs font-medium rounded-lg border border-border-subtle text-secondary hover:text-primary hover:border-border-glow transition-all duration-200 active:scale-95"
          >
            Review Each
          </button>
        </div>
      </div>
    </div>
  )
}
