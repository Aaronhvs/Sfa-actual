import type { ReactNode } from 'react'

export interface CompareMetric {
  label: string
  a: number | null
  b: number | null
  format?: (value: number) => string
  lowerIsBetter?: boolean
}

function defaultFormat(value: number) {
  return value.toLocaleString('es-ES', { maximumFractionDigits: 1 })
}

export function ComparisonRow({ metric }: { metric: CompareMetric }) {
  const { label, a, b, format = defaultFormat, lowerIsBetter = false } = metric
  const aValue = a ?? 0
  const bValue = b ?? 0
  const comparable = a !== null && b !== null
  const visualA = comparable && lowerIsBetter ? Math.abs(bValue) : Math.abs(aValue)
  const visualB = comparable && lowerIsBetter ? Math.abs(aValue) : Math.abs(bValue)
  const visualTotal = visualA + visualB
  const aShare = visualTotal > 0 ? visualA / visualTotal * 100 : 50
  const bShare = 100 - aShare
  const aWins = comparable && (lowerIsBetter ? aValue < bValue : aValue > bValue)
  const bWins = comparable && (lowerIsBetter ? bValue < aValue : bValue > aValue)

  return (
    <div className="cmp-metric-row">
      <span className="cmp-metric-row__label">{label}</span>
      <div className="cmp-metric-row__values">
        <span className={`cmp-metric-row__value cmp-metric-row__value--a${aWins ? ' cmp-metric-row__value--winner' : ''}`}>
          {a === null ? '-' : format(a)}
        </span>
        <span className={`cmp-metric-row__value cmp-metric-row__value--b${bWins ? ' cmp-metric-row__value--winner' : ''}`}>
          {b === null ? '-' : format(b)}
        </span>
      </div>
      <span className="cmp-metric-row__track" aria-hidden="true">
        <span className="cmp-metric-row__fill-a" style={{ width: `${aShare}%` }} />
        <span className="cmp-metric-row__fill-b" style={{ width: `${bShare}%` }} />
      </span>
    </div>
  )
}

export function StatSection({
  title,
  eyebrow,
  metrics,
  children,
  className = '',
}: {
  title: string
  eyebrow?: string
  metrics?: CompareMetric[]
  children?: ReactNode
  className?: string
}) {
  const visibleMetrics = metrics?.filter((metric) => metric.a !== null || metric.b !== null) ?? []
  if (visibleMetrics.length === 0 && !children) return null

  return (
    <section className={`cmp-stat-section ${className}`.trim()}>
      <header className="cmp-stat-section__header">
        <h2>{title}</h2>
        {eyebrow && <span>{eyebrow}</span>}
      </header>
      <div className="cmp-stat-section__body">
        {children}
        {visibleMetrics.map((metric) => <ComparisonRow key={metric.label} metric={metric} />)}
      </div>
    </section>
  )
}
