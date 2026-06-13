import type { CSSProperties, KeyboardEvent } from 'react'
import type { SeasonItem } from '../../types'
import { getSeasonLabel, isWorldCupSeason } from '../../utils/season'

interface Props {
  items: SeasonItem[]
  value: string
  onChange: (season: string) => void
  includeAll?: boolean
}

export default function SeasonSelector({
  items,
  value,
  onChange,
  includeAll = true,
}: Props) {
  const allOption: SeasonItem = { season: 'all', is_latest: false }
  const options = includeAll ? [...items, allOption] : items
  const activeIndex = options.findIndex((option) => option.season === value)

  if (options.length <= 1) return null

  const selectorStyle = {
    '--season-count': options.length,
    '--season-index': Math.max(activeIndex, 0),
  } as CSSProperties
  const isWorldCupActive = isWorldCupSeason(value, items)

  function moveSelection(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
    event.preventDefault()

    let nextIndex = index
    if (event.key === 'ArrowLeft') nextIndex = (index - 1 + options.length) % options.length
    if (event.key === 'ArrowRight') nextIndex = (index + 1) % options.length
    if (event.key === 'Home') nextIndex = 0
    if (event.key === 'End') nextIndex = options.length - 1

    onChange(options[nextIndex].season)
    event.currentTarget.parentElement
      ?.querySelectorAll<HTMLButtonElement>('.season-btn')
      [nextIndex]?.focus()
  }

  return (
    <div
      className={`season-selector${isWorldCupActive ? ' season-selector--wc' : ''}`}
      role="radiogroup"
      aria-label="Temporada de estadísticas"
      style={selectorStyle}
    >
      <div className="season-selector__track" aria-hidden="true" />
      {options.map((item, index) => {
        const isWorldCup = item.is_world_cup === true
        const label = item.season === 'all'
          ? 'Todas'
          : getSeasonLabel(item.season, items)
        const meta = item.season === 'all'
          ? 'Histórico'
          : isWorldCup
            ? 'Mundial'
            : item.is_latest
              ? 'Actual'
              : 'Temporada'
        return (
          <button
            key={item.season}
            type="button"
            role="radio"
            className={[
              'season-btn',
              value === item.season ? 'season-btn--active' : '',
              isWorldCup ? 'season-btn--wc' : '',
            ].filter(Boolean).join(' ')}
            onClick={() => onChange(item.season)}
            onKeyDown={(event) => moveSelection(event, index)}
            aria-checked={value === item.season}
            tabIndex={value === item.season ? 0 : -1}
          >
            <span className="season-btn__label">{label}</span>
            <span className="season-btn__meta">{meta}</span>
          </button>
        )
      })}
    </div>
  )
}
