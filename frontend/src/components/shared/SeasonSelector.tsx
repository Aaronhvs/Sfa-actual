import type { CSSProperties, KeyboardEvent } from 'react'
import { seasonLabel } from '../../utils/season'

interface Props {
  seasons: string[]
  value: string
  onChange: (s: string) => void
  includeAll?: boolean
}

export default function SeasonSelector({ seasons, value, onChange, includeAll = true }: Props) {
  const options = includeAll ? [...seasons, 'all'] : seasons
  const activeIdx = options.indexOf(value)

  if (options.length <= 1) return null

  const selectorStyle = {
    '--season-count': options.length,
    '--season-index': Math.max(activeIdx, 0),
  } as CSSProperties

  function moveSelection(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
    event.preventDefault()

    let nextIndex = index
    if (event.key === 'ArrowLeft') nextIndex = (index - 1 + options.length) % options.length
    if (event.key === 'ArrowRight') nextIndex = (index + 1) % options.length
    if (event.key === 'Home') nextIndex = 0
    if (event.key === 'End') nextIndex = options.length - 1

    onChange(options[nextIndex])
    event.currentTarget.parentElement
      ?.querySelectorAll<HTMLButtonElement>('.season-btn')
      [nextIndex]?.focus()
  }

  return (
    <div
      className="season-selector"
      role="radiogroup"
      aria-label="Temporada de estadísticas"
      style={selectorStyle}
    >
      <div className="season-selector__track" aria-hidden="true" />
      {options.map((s, i) => (
        <button
          key={s}
          type="button"
          role="radio"
          className={`season-btn${value === s ? ' season-btn--active' : ''}`}
          onClick={() => onChange(s)}
          onKeyDown={(event) => moveSelection(event, i)}
          aria-checked={value === s}
          tabIndex={value === s ? 0 : -1}
        >
          <span className="season-btn__label">
            {s === 'all' ? 'Todas' : seasonLabel(s)}
          </span>
          <span className="season-btn__meta">
            {s === 'all' ? 'Histórico' : i === 0 ? 'Actual' : 'Temporada'}
          </span>
        </button>
      ))}
    </div>
  )
}
