import { useEffect, useRef, useState } from 'react'

/**
 * LineChart — SVG line chart with draw-in via stroke-dashoffset.
 *
 * Props:
 *   height:  number (px)
 *   labels:  string[]                               x-axis labels (e.g. ['Mon','Tue',...])
 *   series:  [{ name, values[], color, dashed?, visible? }]
 *            color should be a CSS value (e.g. 'var(--color-mint)')
 */
export default function LineChart({
  height = 140,
  labels = [],
  series = [],
}) {
  const ref = useRef(null)
  const [width, setWidth] = useState(600)

  // Observe parent width for responsive sizing
  useEffect(() => {
    if (!ref.current) return
    const el = ref.current
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const w = entry.contentRect.width
        if (w > 0) setWidth(w)
      }
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const visibleSeries = series.filter(s => s.visible !== false && (s.values || []).length > 0)
  const allOff = series.length > 0 && visibleSeries.length === 0

  // Empty state — everything hidden
  if (allOff) {
    return (
      <div ref={ref} style={{ height }} className="flex items-center justify-center text-xs text-tertiary">
        Toggle a series on to see the trend
      </div>
    )
  }

  // If no series at all or no values, render an empty grid
  const yMaxRaw = Math.max(
    1,
    ...series.flatMap(s => (s.values || []).map(v => Number(v) || 0)),
  )
  // add 10% headroom, round up to a clean integer
  const yMax = Math.max(1, Math.ceil(yMaxRaw * 1.1))

  const padX = 28
  const padTop = 12
  const padBottom = 24
  const innerW = Math.max(1, width - padX * 2)
  const innerH = Math.max(1, height - padTop - padBottom)
  const n = labels.length || (series[0]?.values?.length ?? 0) || 1
  const stepX = n > 1 ? innerW / (n - 1) : innerW

  const xOf = (i) => padX + i * stepX
  const yOf = (v) => padTop + innerH - ((Number(v) || 0) / yMax) * innerH

  const buildPath = (values) => {
    if (!values || values.length === 0) return ''
    return values
      .map((v, i) => `${i === 0 ? 'M' : 'L'} ${xOf(i).toFixed(1)} ${yOf(v).toFixed(1)}`)
      .join(' ')
  }

  // Gridlines: 4 horizontal ticks
  const ticks = 4
  const gridLines = []
  for (let t = 0; t <= ticks; t++) {
    const y = padTop + (innerH * t) / ticks
    gridLines.push(y)
  }

  return (
    <div ref={ref} className="w-full" style={{ height }}>
      <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
        {/* horizontal grid */}
        {gridLines.map((y, i) => (
          <line
            key={`g-${i}`}
            x1={padX}
            x2={width - padX}
            y1={y}
            y2={y}
            stroke="var(--color-border-subtle)"
            strokeWidth={1}
          />
        ))}

        {/* series paths */}
        {series.map((s, si) => {
          const values = s.values || []
          if (values.length === 0) return null
          const d = buildPath(values)
          const visible = s.visible !== false
          const pathLen = Math.max(
            1,
            // rough estimate: sum of segment lengths
            values.slice(1).reduce((acc, _, i) => {
              const dx = xOf(i + 1) - xOf(i)
              const dy = yOf(values[i + 1]) - yOf(values[i])
              return acc + Math.sqrt(dx * dx + dy * dy)
            }, 0),
          )
          return (
            <g key={`s-${si}`}>
              <path
                d={d}
                fill="none"
                stroke={s.color}
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeDasharray={s.dashed ? '4 4' : `${pathLen} ${pathLen}`}
                style={{
                  strokeDashoffset: s.dashed ? 0 : 0,
                  opacity: visible ? 1 : 0,
                  transition: 'opacity 200ms ease-out',
                  animation: s.dashed ? undefined : `sparkline-draw 600ms ease-out both`,
                }}
              />
              {/* Dots for non-dashed series, only when visible */}
              {!s.dashed && visible && values.map((v, i) => (
                <circle
                  key={`d-${si}-${i}`}
                  cx={xOf(i)}
                  cy={yOf(v)}
                  r={2.5}
                  fill={s.color}
                  style={{ transition: 'opacity 200ms ease-out' }}
                />
              ))}
            </g>
          )
        })}

        {/* x-axis labels */}
        {labels.map((lbl, i) => (
          <text
            key={`l-${i}`}
            x={xOf(i)}
            y={height - 6}
            textAnchor="middle"
            fontSize={10}
            fill="var(--color-tertiary)"
          >
            {lbl}
          </text>
        ))}
      </svg>
    </div>
  )
}
