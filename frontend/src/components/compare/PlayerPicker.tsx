import { useEffect, useId, useRef, useState } from 'react'
import type { RankedPlayer } from '../../types'
import { fetchRanking } from '../../api/client'

const SEARCH_DEBOUNCE_MS = 300

function initials(name: string) {
  return name.split(' ').map((word) => word[0]).slice(0, 2).join('').toUpperCase()
}

interface Props {
  label: string
  selected: RankedPlayer | null
  onSelect: (player: RankedPlayer) => void
  onClear: () => void
  excludeId?: number
  scope: string
}

export default function PlayerPicker({
  label,
  selected,
  onSelect,
  onClear,
  excludeId,
  scope,
}: Props) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<RankedPlayer[]>([])
  const [searching, setSearching] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const inputId = useId()
  const listId = `${inputId}-results`

  useEffect(() => {
    if (query.trim().length < 2) {
      setResults([])
      setSearching(false)
      return
    }

    let active = true
    setSearching(true)
    const timer = window.setTimeout(() => {
      fetchRanking({ scope, name: query.trim(), limit: 8 })
        .then((data) => {
          if (active) setResults(data.ranking.filter((player) => player.id !== excludeId))
        })
        .catch(() => { if (active) setResults([]) })
        .finally(() => { if (active) setSearching(false) })
    }, SEARCH_DEBOUNCE_MS)

    return () => {
      active = false
      window.clearTimeout(timer)
    }
  }, [excludeId, query, scope])

  useEffect(() => {
    function closeOnOutside(event: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setResults([])
      }
    }
    document.addEventListener('mousedown', closeOnOutside)
    return () => document.removeEventListener('mousedown', closeOnOutside)
  }, [])

  if (selected) {
    return (
      <div className="cmp-chip">
        {selected.photo_url
          ? <img src={selected.photo_url} alt="" className="cmp-chip__photo" />
          : <div className="cmp-chip__avatar" aria-hidden="true">{initials(selected.name)}</div>
        }
        <div className="cmp-chip__info">
          <span className="cmp-chip__name">{selected.name}</span>
          <span className="cmp-chip__sub">
            <span className="pos-badge">{selected.position}</span>
            <span className="cmp-chip__team">{selected.team}</span>
          </span>
        </div>
        <span className="cmp-chip__pts">
          {Math.round(selected.sfa_pts).toLocaleString('es-ES')}
          <span className="cmp-chip__pts-lbl"> pts</span>
        </span>
        <button type="button" className="cmp-chip__clear" onClick={onClear} aria-label={`Quitar a ${selected.name}`}>
          ×
        </button>
      </div>
    )
  }

  const showResults = query.trim().length >= 2 && !searching

  return (
    <div className="cmp-picker" ref={rootRef}>
      <label className="cmp-picker__label" htmlFor={inputId}>{label}</label>
      <div className="cmp-picker__search-row">
        <svg className="cmp-picker__icon" viewBox="0 0 20 20" fill="none" aria-hidden="true">
          <circle cx="8.5" cy="8.5" r="5.5" stroke="currentColor" strokeWidth="1.5" />
          <path d="M14 14l3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
        <input
          id={inputId}
          className="cmp-picker__input"
          type="search"
          placeholder="Buscar jugador"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          autoComplete="off"
          spellCheck={false}
          role="combobox"
          aria-controls={listId}
          aria-expanded={results.length > 0}
          aria-autocomplete="list"
        />
        {searching && <span className="cmp-picker__spinner" aria-label="Buscando" />}
      </div>

      {showResults && results.length === 0 && (
        <div className="cmp-picker__empty" role="status">Sin resultados para “{query}”</div>
      )}

      {results.length > 0 && (
        <div className="cmp-picker__dropdown" id={listId} role="listbox" aria-label={label}>
          {results.map((player) => (
            <button
              type="button"
              role="option"
              aria-selected="false"
              key={player.id}
              className="cmp-picker__result"
              onClick={() => {
                onSelect(player)
                setQuery('')
                setResults([])
              }}
            >
              {player.photo_url
                ? <img src={player.photo_url} alt="" className="cmp-picker__result-photo" />
                : <div className="cmp-picker__result-avatar" aria-hidden="true">{initials(player.name)}</div>
              }
              <span className="cmp-picker__result-info">
                <span className="cmp-picker__result-name">{player.name}</span>
                <span className="cmp-picker__result-meta">{player.team} · #{player.rank}</span>
              </span>
              <span className="cmp-picker__result-pts">{Math.round(player.sfa_pts).toLocaleString('es-ES')}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
