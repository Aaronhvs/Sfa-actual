import './RankMove.css'

/** Small up/down caret for places gained or lost over the last 7 days; nothing when unchanged. */
export default function RankMove({ change, className = '' }: { change: number | null | undefined; className?: string }) {
  if (!change) return null
  const up = change > 0
  const places = Math.abs(change)
  const label = `${up ? 'Sube' : 'Baja'} ${places} ${places === 1 ? 'puesto' : 'puestos'} en los últimos 7 días`
  return (
    <svg className={`sfa-rank-move is-${up ? 'up' : 'down'} ${className}`.trim()} viewBox="0 0 10 6" role="img" aria-label={label}>
      <title>{label}</title>
      <path d={up ? 'M5 0 10 6H0Z' : 'M0 0h10L5 6Z'} />
    </svg>
  )
}
