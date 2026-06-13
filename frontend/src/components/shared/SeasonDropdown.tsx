import { useEffect, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import type { SeasonItem } from '../../types'
import { getSeasonLabel, isWorldCupSeason } from '../../utils/season'

interface Props {
  items: SeasonItem[]
  value: string
  onChange: (season: string) => void
  includeAll?: boolean
}

export default function SeasonDropdown({
  items,
  value,
  onChange,
  includeAll = true,
}: Props) {
  const allOption: SeasonItem = { season: 'all', is_latest: false }
  const options = includeAll ? [allOption, ...items] : items
  const latestItem = items.find((item) => item.is_latest)
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function onClickOutside(event: MouseEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [open])

  const currentLabel = value === 'all'
    ? 'Total histórico'
    : `${getSeasonLabel(value, items)}${latestItem?.season === value ? ' · Actual' : ''}`
  const isCurrentWorldCup = isWorldCupSeason(value, items)

  function selectSeason(season: string) {
    onChange(season)
    setOpen(false)
  }

  function handleOptionKeyDown(
    event: KeyboardEvent<HTMLLIElement>,
    season: string,
    index: number,
  ) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      selectSeason(season)
      return
    }
    if (event.key === 'Escape') {
      setOpen(false)
      ref.current?.querySelector<HTMLButtonElement>('.season-dropdown__trigger')?.focus()
      return
    }
    if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return
    event.preventDefault()
    const optionElements = event.currentTarget.parentElement
      ?.querySelectorAll<HTMLLIElement>('.season-dropdown__item')
    if (!optionElements) return
    let nextIndex = index
    if (event.key === 'ArrowDown') nextIndex = (index + 1) % optionElements.length
    if (event.key === 'ArrowUp') nextIndex = (index - 1 + optionElements.length) % optionElements.length
    if (event.key === 'Home') nextIndex = 0
    if (event.key === 'End') nextIndex = optionElements.length - 1
    optionElements[nextIndex]?.focus()
  }

  function openWithKeyboard(event: KeyboardEvent<HTMLButtonElement>) {
    if (!['ArrowDown', 'ArrowUp'].includes(event.key)) return
    event.preventDefault()
    setOpen(true)
    requestAnimationFrame(() => {
      const optionElements = ref.current
        ?.querySelectorAll<HTMLLIElement>('.season-dropdown__item')
      if (!optionElements?.length) return
      const index = event.key === 'ArrowUp' ? optionElements.length - 1 : 0
      optionElements[index]?.focus()
    })
  }

  function closeFromTrigger(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key === 'Escape' && open) {
      event.preventDefault()
      setOpen(false)
    }
  }

  return (
    <div className="season-dropdown" ref={ref}>
      <button
        type="button"
        className={[
          'season-dropdown__trigger',
          open ? 'season-dropdown__trigger--open' : '',
          isCurrentWorldCup ? 'season-dropdown__trigger--wc' : '',
        ].filter(Boolean).join(' ')}
        onClick={() => setOpen((current) => !current)}
        onKeyDown={(event) => {
          openWithKeyboard(event)
          closeFromTrigger(event)
        }}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span className="season-dropdown__meta">Temporada</span>
        <span className="season-dropdown__current">{currentLabel}</span>
        <svg
          className="season-dropdown__chevron"
          width="10"
          height="6"
          viewBox="0 0 10 6"
          aria-hidden="true"
        >
          <path
            d="M1 1l4 4 4-4"
            stroke="currentColor"
            strokeWidth="1.5"
            fill="none"
            strokeLinecap="round"
          />
        </svg>
      </button>

      {open && (
        <ul className="season-dropdown__menu" role="listbox" aria-label="Seleccionar temporada">
          {options.map((item, index) => {
            const isWorldCup = item.is_world_cup === true
            const label = item.season === 'all'
              ? 'Todas las temporadas'
              : getSeasonLabel(item.season, items)
            return (
              <li
                key={item.season}
                role="option"
                tabIndex={0}
                aria-selected={value === item.season}
                className={[
                  'season-dropdown__item',
                  value === item.season ? 'season-dropdown__item--active' : '',
                  isWorldCup ? 'season-dropdown__item--wc' : '',
                ].filter(Boolean).join(' ')}
                onClick={() => selectSeason(item.season)}
                onKeyDown={(event) => handleOptionKeyDown(event, item.season, index)}
              >
                <span>{label}</span>
                {isWorldCup && (
                  <small className="season-dropdown__wc-badge">Torneo</small>
                )}
                {item.is_latest && !isWorldCup && (
                  <small className="season-dropdown__latest">Actual</small>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
