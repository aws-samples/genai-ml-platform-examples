import { Check, Clock, AlertCircle } from 'lucide-react'

const statusConfig = {
  success: { border: 'border-l-emerald', icon: Check, iconColor: 'text-emerald' },
  pending: { border: 'border-l-gold', icon: Clock, iconColor: 'text-gold' },
  error: { border: 'border-l-coral', icon: AlertCircle, iconColor: 'text-coral' },
}

export default function ActionConfirmation({ data }) {
  if (!data) return null
  const status = data.status || 'success'
  const config = statusConfig[status] || statusConfig.success
  const Icon = config.icon

  return (
    <div className={`bg-graphite rounded-xl border border-border-subtle ${config.border} border-l-4 p-4 animate-[count-up-fade_400ms_ease-out]`}>
      <div className="flex items-center gap-2 mb-2">
        <Icon size={16} className={config.iconColor} />
        <span className="text-primary text-sm font-medium tracking-tight">{data.title}</span>
      </div>
      {data.details?.map((line, i) => (
        <p key={i} className="text-secondary text-xs leading-relaxed">{line}</p>
      ))}
      {data.actions?.length > 0 && (
        <div className="flex gap-2 mt-3">
          {data.actions.map((action, i) => (
            <button key={i} className="text-xs text-mint hover:text-mint/80 font-medium">
              {action}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
