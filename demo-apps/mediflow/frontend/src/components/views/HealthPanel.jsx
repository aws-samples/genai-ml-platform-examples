import { useState, useEffect } from 'react'
import { Activity, Zap, Clock, DollarSign, TrendingUp, ChevronDown } from 'lucide-react'
import { api } from '../../api/client'

function MetricCard({ label, value, sub, color = 'text-mint', icon: Icon }) {
  return (
    <div className="bg-graphite rounded-xl border border-border-subtle px-4 py-3 flex-1 min-w-[140px]">
      <div className="flex items-center gap-1.5 mb-1">
        {Icon && <Icon size={11} className={color} />}
        <p className="text-tertiary text-[11px] tracking-widest uppercase">{label}</p>
      </div>
      <p className={`text-xl font-semibold tabular-nums ${color}`}>{value}</p>
      {sub && <p className="text-tertiary text-[10px] mt-0.5">{sub}</p>}
    </div>
  )
}

function Sparkline({ data, width = 120, height = 28 }) {
  if (!data || data.length < 2) return null
  const values = data.map(d => d.cost_usd || 0)
  const max = Math.max(...values, 0.001)
  const points = values.map((v, i) =>
    `${(i / (values.length - 1)) * width},${height - (v / max) * (height - 4)}`
  ).join(' ')

  return (
    <svg width={width} height={height} className="opacity-60">
      <polyline
        points={points}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        className="text-gold"
      />
    </svg>
  )
}

export default function HealthPanel() {
  const [metrics, setMetrics] = useState(null)
  const [expanded, setExpanded] = useState(false)

  useEffect(() => {
    api.metricsSummary()
      .then(setMetrics)
      .catch(() => {})
  }, [])

  if (!metrics) return null

  const {
    executions_24h,
    executions_7d,
    success_rate_7d,
    avg_duration_ms_7d,
    total_cost_7d_usd,
    daily_cost,
  } = metrics

  const successColor = success_rate_7d >= 0.9 ? 'text-mint' : success_rate_7d >= 0.7 ? 'text-gold' : 'text-coral'
  const durationSec = (avg_duration_ms_7d / 1000).toFixed(1)

  return (
    <section className="mb-6" data-testid="health-panel">
      <div className="flex items-center gap-2 mb-3">
        <Activity size={14} className="text-mint" />
        <h2 className="text-sm font-semibold text-primary tracking-tight">System Health</h2>
        <span className="text-[10px] text-tertiary tracking-widest uppercase">7-day window</span>
      </div>

      <div className="flex flex-wrap gap-3">
        <MetricCard
          label="Executions"
          value={executions_24h}
          sub={`${executions_7d} last 7d`}
          color="text-mint"
          icon={Zap}
        />
        <MetricCard
          label="Success Rate"
          value={`${Math.round(success_rate_7d * 100)}%`}
          color={successColor}
          icon={TrendingUp}
        />
        <MetricCard
          label="Avg Duration"
          value={`${durationSec}s`}
          color="text-secondary"
          icon={Clock}
        />
        <MetricCard
          label="Cost (7d)"
          value={`$${total_cost_7d_usd.toFixed(2)}`}
          sub={daily_cost?.length > 0 ? <Sparkline data={daily_cost} /> : null}
          color="text-gold"
          icon={DollarSign}
        />
      </div>

      {daily_cost?.length > 0 && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="mt-2 flex items-center gap-1 text-[11px] text-tertiary hover:text-secondary transition-colors"
        >
          <ChevronDown size={12} className={`transition-transform ${expanded ? 'rotate-180' : ''}`} />
          {expanded ? 'Hide' : 'Show'} daily breakdown
        </button>
      )}

      {expanded && daily_cost?.length > 0 && (
        <div className="mt-2 bg-graphite rounded-xl border border-border-subtle px-4 py-3 animate-[count-up-fade_200ms_ease-out]">
          <div className="grid grid-cols-[1fr_auto_auto] gap-x-4 gap-y-1 text-[11px]">
            <span className="text-tertiary font-semibold">Date</span>
            <span className="text-tertiary font-semibold text-right">Cost</span>
            <span className="text-tertiary font-semibold text-right">Runs</span>
            {daily_cost.map(d => (
              <div key={d.date} className="contents">
                <span className="text-secondary tabular-nums">{d.date}</span>
                <span className="text-gold tabular-nums text-right">${d.cost_usd.toFixed(4)}</span>
                <span className="text-secondary tabular-nums text-right">{d.executions}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  )
}
