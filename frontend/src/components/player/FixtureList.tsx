import { useState, useMemo } from 'react'
import type { PlayerEvent, PlayerFixture } from '../../types'
import FixtureRow from './FixtureRow'
import HighlightsView from './HighlightsView'

interface Props {
  fixtures: PlayerFixture[]
  events: PlayerEvent[]
}

const COMP_ABBR: Record<string, string> = {
  'UEFA Champions League': 'UCL',
  'Copa del Rey': 'Copa',
  'Premier League': 'Premier',
  'Bundesliga': 'Bundesliga',
  'Ligue 1': 'Ligue 1',
}

function compLabel(name: string): string {
  return COMP_ABBR[name] ?? name
}

export default function FixtureList({ fixtures, events }: Props) {
  const [view, setView] = useState<'highlights' | 'list'>('highlights')
  const [activeComp, setActiveComp] = useState<string | null>(null)
  const [search, setSearch] = useState('')

  const eventsByFixture = useMemo(() => {
    const map = new Map<number, PlayerEvent[]>()
    for (const e of events) {
      const list = map.get(e.fixture_id)
      if (list) list.push(e)
      else map.set(e.fixture_id, [e])
    }
    return map
  }, [events])

  const competitions = useMemo(() => {
    const seen = new Set<string>()
    const result: string[] = []
    for (const f of fixtures) {
      if (!seen.has(f.competition)) {
        seen.add(f.competition)
        result.push(f.competition)
      }
    }
    return result
  }, [fixtures])

  const DESTACADOS_LIMIT = 15

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()

    // Con búsqueda activa: busca en todos los partidos, ordenados por fecha
    if (q) {
      return [...fixtures]
        .sort((a, b) => new Date(b.played_at).getTime() - new Date(a.played_at).getTime())
        .filter(
          (f) =>
            f.home_team.toLowerCase().includes(q) ||
            f.away_team.toLowerCase().includes(q) ||
            f.competition.toLowerCase().includes(q) ||
            f.stage.toLowerCase().includes(q),
        )
    }

    // Ver todos: sin filtro de competición, ordenados por fecha
    if (activeComp === '__all__') {
      return [...fixtures]
        .sort((a, b) => new Date(b.played_at).getTime() - new Date(a.played_at).getTime())
    }

    // Con filtro de competición: todos los de esa comp ordenados por fecha
    if (activeComp) {
      return [...fixtures]
        .filter((f) => f.competition === activeComp)
        .sort((a, b) => new Date(b.played_at).getTime() - new Date(a.played_at).getTime())
    }

    // Sin filtros ("Destacados"): top N partidos por puntos
    return [...fixtures]
      .sort((a, b) => b.sfa_pts - a.sfa_pts)
      .slice(0, DESTACADOS_LIMIT)
  }, [fixtures, activeComp, search])

  if (fixtures.length === 0) {
    return <div className="empty-state">Sin partidos registrados para esta temporada.</div>
  }

  return (
    <div>
      {/* Tab switcher */}
      <div className="fixture-view-tabs">
        <button
          className={`fixture-view-tab${view === 'highlights' ? ' fixture-view-tab--active' : ''}`}
          onClick={() => setView('highlights')}
        >
          Destacados
        </button>
        <button
          className={`fixture-view-tab${view === 'list' ? ' fixture-view-tab--active' : ''}`}
          onClick={() => setView('list')}
        >
          Lista de partidos
        </button>
      </div>

      {/* Highlights view */}
      {view === 'highlights' && (
        <HighlightsView fixtures={fixtures} events={events} />
      )}

      {/* List view */}
      {view === 'list' && (
        <>
          <div className="fixture-controls">
            <div className="filter-bar__group">
              <button
                className={`filter-btn${activeComp === null ? ' filter-btn--active' : ''}`}
                onClick={() => setActiveComp(null)}
              >
                Destacados
              </button>
              <button
                className={`filter-btn${activeComp === '__all__' ? ' filter-btn--active' : ''}`}
                onClick={() => setActiveComp('__all__')}
              >
                Todos
              </button>
              {competitions.map((comp) => (
                <button
                  key={comp}
                  className={`filter-btn${activeComp === comp ? ' filter-btn--active' : ''}`}
                  onClick={() => setActiveComp(activeComp === comp ? null : comp)}
                >
                  {compLabel(comp)}
                </button>
              ))}
            </div>

            <div className="fixture-search-wrapper">
              <svg className="fixture-search-icon" viewBox="0 0 20 20" fill="none">
                <circle cx="8.5" cy="8.5" r="5.5" stroke="currentColor" strokeWidth="1.5" />
                <path d="M14 14l3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
              <input
                className="fixture-search-input"
                type="text"
                placeholder="Buscar equipo o jornada..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
              {search && (
                <button className="fixture-search-clear" onClick={() => setSearch('')} aria-label="Limpiar">
                  ✕
                </button>
              )}
            </div>
          </div>

          {filtered.length === 0 ? (
            <div className="empty-state">No hay partidos que coincidan.</div>
          ) : (
            <div className="fixture-list">
              {filtered.map((f, i) => (
                <div
                  key={f.fixture_id}
                  className="fixture-row-anim"
                  style={{ animationDelay: `${Math.min(i * 35, 350)}ms` }}
                >
                  <FixtureRow fixture={f} events={eventsByFixture.get(f.fixture_id) ?? []} />
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
