import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react'
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
  const [activeIndex, setActiveIndex] = useState(-1)
  const rootRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const optionRefs = useRef<Array<HTMLButtonElement | null>>([])
  const inputId = useId()
  const listId = `${inputId}-results`

  useEffect(() => {
    if (query.trim().length < 2) {
      setResults([])
      setSearching(false)
      setActiveIndex(-1)
      return
    }

    let active = true
    setSearching(true)
    const timer = window.setTimeout(() => {
      fetchRanking({ scope, name: query.trim(), limit: 8 })
        .then((data) => {
          if (active) {
            setResults(data.ranking.filter((player) => player.id !== excludeId))
            setActiveIndex(-1)
          }
        })
        .catch(() => {
          if (active) {
            setResults([])
            setActiveIndex(-1)
          }
        })
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
        setActiveIndex(-1)
      }
    }
    document.addEventListener('mousedown', closeOnOutside)
    return () => document.removeEventListener('mousedown', closeOnOutside)
  }, [])

  const selectPlayer = (player: RankedPlayer) => {
    onSelect(player)
    setQuery('')
    setResults([])
    setActiveIndex(-1)
  }

  const focusOption = (index: number) => {
    if (results.length === 0) return
    const nextIndex = (index + results.length) % results.length
    setActiveIndex(nextIndex)
    window.requestAnimationFrame(() => optionRefs.current[nextIndex]?.focus())
  }

  const handleInputKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowDown' && results.length > 0) {
      event.preventDefault()
      focusOption(0)
    } else if (event.key === 'ArrowUp' && results.length > 0) {
      event.preventDefault()
      focusOption(results.length - 1)
    } else if (event.key === 'Escape') {
      setResults([])
      setActiveIndex(-1)
    }
  }

  const handleOptionKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      focusOption(index + 1)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      focusOption(index - 1)
    } else if (event.key === 'Escape') {
      event.preventDefault()
      setResults([])
      setActiveIndex(-1)
      inputRef.current?.focus()
    }
  }

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
          ref={inputRef}
          id={inputId}
          className="cmp-picker__input"
          type="text"
          inputMode="search"
          placeholder="Buscar jugador"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          autoComplete="off"
          spellCheck={false}
          role="combobox"
          aria-controls={listId}
          aria-expanded={results.length > 0}
          aria-autocomplete="list"
          aria-activedescendant={activeIndex >= 0 ? `${listId}-${results[activeIndex]?.id}` : undefined}
          onKeyDown={handleInputKeyDown}
        />
        {searching && <span className="cmp-picker__spinner" aria-label="Buscando" />}
        {!searching && query && (
          <button
            type="button"
            className="cmp-picker__query-clear"
            onClick={() => {
              setQuery('')
              setResults([])
              inputRef.current?.focus()
            }}
            aria-label="Limpiar busqueda"
          >
            &times;
          </button>
        )}
      </div>

      {showResults && results.length === 0 && (
        <div className="cmp-picker__empty" role="status">Sin resultados para “{query}”</div>
      )}

      {results.length > 0 && (
        <div className="cmp-picker__dropdown" id={listId} role="listbox" aria-label={label}>
          {results.map((player, index) => (
            <button
              id={`${listId}-${player.id}`}
              type="button"
              role="option"
              aria-selected={activeIndex >= 0 && results[activeIndex]?.id === player.id}
              tabIndex={activeIndex === index ? 0 : -1}
              key={player.id}
              ref={(element) => { optionRefs.current[index] = element }}
              className="cmp-picker__result"
              onClick={() => selectPlayer(player)}
              onFocus={() => setActiveIndex(index)}
              onMouseEnter={() => setActiveIndex(index)}
              onKeyDown={(event) => handleOptionKeyDown(event, index)}
            >
              <span className="cmp-picker__result-rank">{String(player.rank).padStart(2, '0')}</span>
              <span className="cmp-picker__result-photo">
                {player.photo_url
                  ? <img src={player.photo_url} alt="" loading="lazy" decoding="async" />
                  : <span aria-hidden="true">{initials(player.name)}</span>
                }
              </span>
              <span className="cmp-picker__result-info">
                <span className="cmp-picker__result-name">{player.name}</span>
                <span className="cmp-picker__result-meta">{player.team}</span>
              </span>
              <span className="cmp-picker__result-score">
                <strong>{Math.round(player.sfa_pts).toLocaleString('es-ES')}</strong>
                <small>PTS</small>
                <span className="cmp-picker__result-ga" aria-label={`${player.goals} goles y ${player.assists} asistencias`}>
                  <b>{player.goals}<i>G</i></b>
                  <b>{player.assists}<i>A</i></b>
                </span>
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
