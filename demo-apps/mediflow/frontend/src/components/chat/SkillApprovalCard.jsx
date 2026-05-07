import { Bot, X, ArrowRight, Users } from 'lucide-react'

/**
 * SkillApprovalCard — rich chat card shown when the agent stages an ad-hoc
 * batch skill and waits for the receptionist to approve before acting.
 *
 * Design reference: DESIGN.md §Approval card. Approve button uses the
 * agent-bg-mint convention with the Bot icon (TASK-046 convention); both
 * buttons carry active:scale-95 for press feedback.
 */
export default function SkillApprovalCard({ data, onApprove, onCancel, disabled }) {
  if (!data) return null

  const {
    skill_id,
    name,
    description,
    trigger_description,
    items = [],
    item_count = 0,
  } = data

  const sample = items.slice(0, 3)
  const extra = Math.max(0, (item_count || items.length) - sample.length)

  return (
    <div
      className="bg-graphite rounded-xl border border-border-subtle overflow-hidden
        animate-[count-up-fade_400ms_ease-out] transition-all duration-200 ease-out"
    >
      {/* Header */}
      <div className="flex items-center gap-2 px-4 pt-3 pb-2">
        <Bot size={14} className="text-mint" />
        <p className="text-sm font-semibold text-primary tracking-tight">
          Ready to run: {name}
        </p>
      </div>

      <div className="h-px bg-border-subtle" />

      {/* Body */}
      <div className="px-4 py-3 space-y-3">
        <p className="text-xs text-secondary leading-relaxed">
          {description || trigger_description}
        </p>

        {/* Recipient summary */}
        {(items.length > 0 || item_count > 0) && (
          <div className="bg-void/50 rounded-lg border-l-2 border-mint/30 px-3 py-2 space-y-1.5">
            <div className="flex items-center gap-1.5">
              <Users size={11} className="text-mint" />
              <span className="text-[10px] font-semibold text-tertiary uppercase tracking-wider">
                {item_count || items.length} item{(item_count || items.length) === 1 ? '' : 's'}
              </span>
            </div>
            {sample.length > 0 && (
              <ul className="space-y-0.5">
                {sample.map((it, i) => (
                  <li key={i} className="text-xs text-secondary">
                    <span className="text-tertiary">•</span> {it.label}
                    {it.detail && <span className="text-tertiary"> · {it.detail}</span>}
                  </li>
                ))}
                {extra > 0 && (
                  <li className="text-xs text-tertiary italic">…and {extra} more</li>
                )}
              </ul>
            )}
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="px-4 pb-3 flex items-center gap-2">
        <button
          onClick={() => onApprove?.(skill_id, data)}
          disabled={disabled}
          className="flex-1 flex items-center justify-center gap-1.5 px-4 py-2 rounded-lg
            bg-mint text-inverse text-xs font-semibold
            hover:bg-mint/90 transition-all duration-200 ease-out active:scale-95
            disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Bot size={12} /> Approve &amp; Run <ArrowRight size={12} />
        </button>
        <button
          onClick={() => onCancel?.(skill_id, data)}
          disabled={disabled}
          className="flex items-center justify-center gap-1.5 px-4 py-2 rounded-lg
            bg-ash text-secondary text-xs font-semibold border border-border-subtle
            hover:text-primary hover:border-border-glow transition-all duration-200 ease-out active:scale-95
            disabled:opacity-50"
        >
          <X size={12} /> Cancel
        </button>
      </div>
    </div>
  )
}
