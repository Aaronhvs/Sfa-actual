import { useEffect, useMemo, useState } from 'react'
import { fetchTournament, fetchTournaments } from '../api/client'
import type {
  TournamentCompetition,
  TournamentDetailResponse,
  TournamentFixture,
  TournamentTeam,
} from '../types'

type View = 'matches' | 'standings' | 'bracket'
type MatchFilter = 'all' | 'upcoming' | 'results'

const FINAL_STATUSES = new Set(['FT', 'AET', 'PEN'])

function seasonLabel(season: string) {
  const start = Number(season)
  return Number.isFinite(start) ? `${start}/${start + 1}` : season
}

function teamLogo(team: TournamentTeam) {
  return team.external_id == null
    ? null
    : `https://media.api-sports.io/football/teams/${team.external_id}.png`
}

function TeamMark({ team }: { team: TournamentTeam }) {
  const logo = teamLogo(team)
  return logo
    ? <img src={logo} alt="" loading="lazy" decoding="async" />
    : <span aria-hidden="true">{team.name.slice(0, 2).toUpperCase()}</span>
}

function dateKey(value: string) {
  return new Intl.DateTimeFormat('es-ES', {
    weekday: 'long',
    day: '2-digit',
    month: 'long',
  }).format(new Date(value))
}

function timeLabel(value: string) {
  return new Intl.DateTimeFormat('es-ES', {
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

function stageLabel(stage: string, matchday: number | null) {
  if (matchday != null) return `Jornada ${matchday}`
  return stage.replace(/_/g, ' ')
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    NS: 'Programado',
    TBD: 'Por definir',
    PST: 'Aplazado',
    FT: 'Final',
    AET: 'Final prorroga',
    PEN: 'Final penaltis',
    LIVE: 'En juego',
    '1H': 'Primer tiempo',
    HT: 'Descanso',
    '2H': 'Segundo tiempo',
  }
  return labels[status] ?? status
}

function isKnockout(stage: string) {
  const value = stage.toLowerCase().replace(/_/g, ' ')
  return [
    'round', 'octav', 'cuartos', 'quarter', 'semi', 'final', 'playoff',
    'play-off', 'knockout', '32', '16', '8th',
  ].some((token) => value.includes(token))
}

function FixtureRow({ fixture }: { fixture: TournamentFixture }) {
  const finished = FINAL_STATUSES.has(fixture.status)
  return (
    <article className="tn-fixture">
      <div className="tn-fixture__meta">
        <time dateTime={fixture.played_at}>{timeLabel(fixture.played_at)}</time>
        <span>{stageLabel(fixture.stage, fixture.matchday)}</span>
      </div>
      <div className="tn-fixture__teams">
        <div className="tn-fixture__team">
          <TeamMark team={fixture.home_team} />
          <strong>{fixture.home_team.name}</strong>
          <b>{fixture.home_goals ?? '-'}</b>
        </div>
        <div className="tn-fixture__team">
          <TeamMark team={fixture.away_team} />
          <strong>{fixture.away_team.name}</strong>
          <b>{fixture.away_goals ?? '-'}</b>
        </div>
      </div>
      <span className={`tn-fixture__status${finished ? ' tn-fixture__status--final' : ''}`}>
        {statusLabel(fixture.status)}
      </span>
    </article>
  )
}

function CompetitionPicker({
  competitions,
  selected,
  onSelect,
}: {
  competitions: TournamentCompetition[]
  selected: number | null
  onSelect: (id: number) => void
}) {
  return (
    <div className="tn-competition-picker" role="list" aria-label="Competiciones">
      {competitions.map((competition) => (
        <button
          key={competition.id}
          type="button"
          className={competition.id === selected ? 'is-active' : ''}
          onClick={() => onSelect(competition.id)}
          aria-pressed={competition.id === selected}
        >
          <span>{competition.name}</span>
          <small>{competition.completed_fixtures}/{competition.total_fixtures}</small>
        </button>
      ))}
    </div>
  )
}

function MatchList({ fixtures }: { fixtures: TournamentFixture[] }) {
  const [filter, setFilter] = useState<MatchFilter>('all')
  const filtered = fixtures.filter((fixture) => (
    filter === 'all'
    || (filter === 'results' && FINAL_STATUSES.has(fixture.status))
    || (filter === 'upcoming' && !FINAL_STATUSES.has(fixture.status))
  ))
  const groups = filtered.reduce<Map<string, TournamentFixture[]>>((result, fixture) => {
    const key = dateKey(fixture.played_at)
    result.set(key, [...(result.get(key) ?? []), fixture])
    return result
  }, new Map())

  return (
    <section className="tn-panel" aria-label="Partidos">
      <div className="tn-filter" role="group" aria-label="Filtrar partidos">
        {([
          ['all', 'Todos'],
          ['upcoming', 'Proximos'],
          ['results', 'Resultados'],
        ] as const).map(([value, label]) => (
          <button
            key={value}
            type="button"
            className={filter === value ? 'is-active' : ''}
            onClick={() => setFilter(value)}
            aria-pressed={filter === value}
          >
            {label}
          </button>
        ))}
      </div>
      {groups.size === 0 && <div className="tn-empty">No hay partidos en esta vista.</div>}
      {[...groups.entries()].map(([date, items]) => (
        <section className="tn-date-group" key={date}>
          <h3>{date}</h3>
          <div>{items.map((fixture) => <FixtureRow fixture={fixture} key={fixture.id} />)}</div>
        </section>
      ))}
    </section>
  )
}

function Standings({ detail }: { detail: TournamentDetailResponse }) {
  if (detail.standings.length === 0) {
    return <div className="tn-empty">La tabla todavia no esta disponible para esta competicion.</div>
  }
  return (
    <section className="tn-table-wrap" aria-label="Clasificacion">
      <div className="tn-table-meta">Jornada {detail.standings_matchday}</div>
      <table className="tn-table">
        <thead><tr><th>Pos.</th><th>Equipo</th><th>Pts</th></tr></thead>
        <tbody>
          {detail.standings.map((entry) => (
            <tr key={entry.team.id}>
              <td>{String(entry.position).padStart(2, '0')}</td>
              <th scope="row"><TeamMark team={entry.team} /><span>{entry.team.name}</span></th>
              <td>{entry.points}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}

function Bracket({ fixtures }: { fixtures: TournamentFixture[] }) {
  const knockout = fixtures.filter((fixture) => isKnockout(fixture.stage))
  const stages = knockout.reduce<Map<string, TournamentFixture[]>>((result, fixture) => {
    result.set(fixture.stage, [...(result.get(fixture.stage) ?? []), fixture])
    return result
  }, new Map())
  if (stages.size === 0) {
    return <div className="tn-empty">Los cruces apareceran cuando se definan las fases eliminatorias.</div>
  }
  return (
    <div className="tn-bracket">
      {[...stages.entries()].map(([stage, items]) => (
        <section className="tn-bracket__stage" key={stage}>
          <h3>{stage.replace(/_/g, ' ')}</h3>
          {items.map((fixture) => <FixtureRow fixture={fixture} key={fixture.id} />)}
        </section>
      ))}
    </div>
  )
}

export default function TournamentsPage() {
  const [season, setSeason] = useState('')
  const [competitions, setCompetitions] = useState<TournamentCompetition[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [detail, setDetail] = useState<TournamentDetailResponse | null>(null)
  const [view, setView] = useState<View>('matches')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchTournaments()
      .then((catalog) => {
        setSeason(catalog.season)
        setCompetitions(catalog.competitions)
        const preferred = catalog.competitions.find((item) => (
          item.name.toLowerCase().includes('champions')
        )) ?? catalog.competitions[0]
        setSelectedId(preferred?.id ?? null)
      })
      .catch(() => setError('No se pudo cargar la temporada de torneos.'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (selectedId == null || !season) return
    let active = true
    setLoading(true)
    setError(null)
    fetchTournament(selectedId, season)
      .then((result) => { if (active) setDetail(result) })
      .catch(() => { if (active) setError('No se pudo cargar esta competicion.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [selectedId, season])

  const counts = useMemo(() => ({
    played: detail?.competition.completed_fixtures ?? 0,
    upcoming: detail?.competition.upcoming_fixtures ?? 0,
  }), [detail])

  return (
    <main className="tournaments-page">
      <header className="tn-header">
        <div>
          <span>Centro de competiciones</span>
          <h1>Torneos</h1>
        </div>
        {season && <strong>Temporada {seasonLabel(season)}</strong>}
      </header>

      {competitions.length > 0 && (
        <CompetitionPicker
          competitions={competitions}
          selected={selectedId}
          onSelect={(id) => { setSelectedId(id); setView('matches') }}
        />
      )}

      {detail && (
        <section className="tn-overview">
          <div className="tn-overview__identity">
            <span>{detail.competition.country}</span>
            <h2>{detail.competition.name}</h2>
          </div>
          <dl>
            <div><dt>Jugados</dt><dd>{counts.played}</dd></div>
            <div><dt>Pendientes</dt><dd>{counts.upcoming}</dd></div>
          </dl>
        </section>
      )}

      <nav className="tn-tabs" aria-label="Vistas del torneo">
        {([
          ['matches', 'Partidos'],
          ['standings', 'Tabla'],
          ['bracket', 'Cruces'],
        ] as const).map(([value, label]) => (
          <button
            type="button"
            key={value}
            className={view === value ? 'is-active' : ''}
            onClick={() => setView(value)}
            aria-current={view === value ? 'page' : undefined}
          >
            {label}
          </button>
        ))}
      </nav>

      {loading && <div className="tn-loading" role="status"><span>Cargando resultados</span></div>}
      {!loading && error && <div className="tn-empty tn-empty--error" role="alert">{error}</div>}
      {!loading && !error && detail && view === 'matches' && <MatchList fixtures={detail.fixtures} />}
      {!loading && !error && detail && view === 'standings' && <Standings detail={detail} />}
      {!loading && !error && detail && view === 'bracket' && <Bracket fixtures={detail.fixtures} />}
      {!loading && !error && competitions.length === 0 && (
        <div className="tn-empty">Aun no hay competiciones cargadas para la temporada vigente.</div>
      )}
    </main>
  )
}
