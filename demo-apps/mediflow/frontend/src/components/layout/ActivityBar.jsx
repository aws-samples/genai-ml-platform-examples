import { useApp } from '../../context/AppContext'

export default function ActivityBar() {
  const { activityFeed } = useApp()

  return (
    <div className="h-9 flex-shrink-0 bg-slate border-t border-border-subtle flex items-center px-4 gap-3 overflow-x-auto">
      {activityFeed.map((item, i) => (
        <span
          key={item.id || i}
          className={`
            flex items-center gap-1.5 text-xs whitespace-nowrap flex-shrink-0 px-2 py-1 rounded-full
            transition-all duration-200
            ${item.active
              ? 'text-mint bg-mint/[0.08] font-medium'
              : 'text-tertiary'
            }
          `}
          style={item.active ? {} : { animation: 'cascade-in 250ms ease-out' }}
        >
          {item.icon && <span className="text-[11px]">{item.icon}</span>}
          {item.text}
          {item.active && <span className="text-mint animate-pulse">···</span>}
        </span>
      ))}
      {activityFeed.length > 1 && (
        <span className="text-tertiary/40 text-[10px] flex-shrink-0">→</span>
      )}
    </div>
  )
}
