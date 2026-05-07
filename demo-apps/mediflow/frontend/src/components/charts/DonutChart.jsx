/**
 * DonutChart — static SVG donut with optional center label.
 *
 * Props:
 *   size:        number (px) — square
 *   segments:    [{ value: number, color: string, label?: string }]
 *                color should be a CSS value (e.g. 'var(--color-mint)').
 *   centerLabel: React node rendered inside the hole
 *   strokeWidth: ring thickness (px)
 */
export default function DonutChart({
  size = 120,
  segments = [],
  centerLabel = null,
  strokeWidth = 14,
}) {
  const total = segments.reduce((s, seg) => s + (Number(seg.value) || 0), 0)
  const r = (size - strokeWidth) / 2
  const cx = size / 2
  const cy = size / 2
  const circumference = 2 * Math.PI * r

  // All-zero / empty state: flat ring in tertiary
  if (total <= 0) {
    return (
      <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
        <svg width={size} height={size} role="img" aria-label="empty donut">
          <circle
            cx={cx}
            cy={cy}
            r={r}
            fill="none"
            stroke="var(--color-border-subtle)"
            strokeWidth={strokeWidth}
          />
        </svg>
        {centerLabel && (
          <div className="absolute inset-0 flex items-center justify-center">
            {centerLabel}
          </div>
        )}
      </div>
    )
  }

  let offset = 0
  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {/* background ring */}
        <circle
          cx={cx}
          cy={cy}
          r={r}
          fill="none"
          stroke="var(--color-border-subtle)"
          strokeWidth={strokeWidth}
        />
        {segments.map((seg, i) => {
          const value = Number(seg.value) || 0
          if (value <= 0) return null
          const frac = value / total
          const len = frac * circumference
          const circle = (
            <circle
              key={i}
              cx={cx}
              cy={cy}
              r={r}
              fill="none"
              stroke={seg.color}
              strokeWidth={strokeWidth}
              strokeDasharray={`${len} ${circumference - len}`}
              strokeDashoffset={-offset}
              transform={`rotate(-90 ${cx} ${cy})`}
              style={{ transition: 'stroke-dasharray 200ms ease-out' }}
            />
          )
          offset += len
          return circle
        })}
      </svg>
      {centerLabel && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          {centerLabel}
        </div>
      )}
    </div>
  )
}
