import { useEffect, useRef, useState } from 'react'
import { seasonLabel } from '../../utils/season'

interface Props {
  seasons: string[]
  value: string
  onChange: (s: string) => void
  includeAll?: boolean
}

export default function SeasonDropdown({ seasons, value, onChange, includeAll = true }: Props) {
  const options = includeAll ? ['all', ...seasons] : seasons
  const latestSeason = seasons[0]
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [open])

  return (
    <div className="season-dropdown" ref={ref}>
      <button
        className={`season-dropdown__trigger${open ? ' season-dropdown__trigger--open' : ''}`}
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span className="season-dropdown__meta">Temporada</span>
        <span className="season-dropdown__current">
          {value === 'all'
            ? 'Total histórico'
            : `${seasonLabel(value)}${value === latestSeason ? ' · Actual' : ''}`}
        </span>
        <svg className="season-dropdown__chevron" width="10" height="6" viewBox="0 0 10 6" aria-hidden="true">
          <path d="M1 1l4 4 4-4" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round"/>
        </svg>
      </button>

      {open && (
        <ul className="season-dropdown__menu" role="listbox" aria-label="Seleccionar temporada">
          {options.map((s) => (
            <li
              key={s}
              role="option"
              aria-selected={value === s}
              className={`season-dropdown__item${value === s ? ' season-dropdown__item--active' : ''}`}
              onClick={() => { onChange(s); setOpen(false) }}
            >
              <span>{s === 'all' ? 'Todas las temporadas' : seasonLabel(s)}</span>
              {s === latestSeason && (
                <small className="season-dropdown__latest">Actual</small>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
