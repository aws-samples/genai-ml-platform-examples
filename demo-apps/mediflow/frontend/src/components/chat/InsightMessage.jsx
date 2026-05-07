import { Sparkles } from 'lucide-react'

export default function InsightMessage({ data }) {
  if (!data) return null

  return (
    <div className="bg-graphite rounded-xl border border-border-subtle border-l-4 border-l-violet p-4 animate-[count-up-fade_400ms_ease-out]"
      style={{ boxShadow: '0 0 20px rgba(167,139,250,0.05)' }}
    >
      <div className="flex items-start gap-2">
        <Sparkles size={16} className="text-violet mt-0.5 flex-shrink-0" />
        <div>
          <p className="text-secondary text-sm leading-relaxed">{data.message}</p>
          {data.action && (
            <button className="mt-3 text-sm font-medium text-violet hover:text-violet/80 flex items-center gap-1 transition-all duration-200 active:scale-95">
              {data.action}
              <span className="text-violet/50">→</span>
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
