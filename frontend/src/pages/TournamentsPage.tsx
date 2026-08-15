import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchRanking, fetchTournamentDashboard, fetchTournaments } from '../api/client'
import TournamentFixtureRow from '../components/tournaments/TournamentFixtureRow'
import type {
  RankedPlayer,
  TournamentCompetition,
  TournamentDashboardResponse,
  TournamentFixture,
} from '../types'
import {
  FINAL_TOURNAMENT_STATUSES,
  isFeaturedTournamentCompetition,
  LIVE_TOURNAMENT_STATUSES,
  sortTournamentCompetitions,
  tournamentCompetitionLogo,
  tournamentCompetitionPriority,
  tournamentDateLabel,
  tournamentSeasonLabel,
  usesMonochromeTournamentLogo,
} from '../utils/tournaments'

type MatchFilter = 'all' | 'live' | 'upcoming' | 'results'

function filterFixture(fixture: TournamentFixture, filter: MatchFilter) {
  if (filter === 'all') return true
  if (filter === 'live') return LIVE_TOURNAMENT_STATUSES.has(fixture.status)
  if (filter === 'results') return FINAL_TOURNAMENT_STATUSES.has(fixture.status)
  return !FINAL_TOURNAMENT_STATUSES.has(fixture.status)
    && !LIVE_TOURNAMENT_STATUSES.has(fixture.status)
}

function CompetitionList({ competitions, season }: {
  competitions: TournamentCompetition[]
  season: string
}) {
  const sorted = competitions
    .filter(isFeaturedTournamentCompetition)
    .sort((a, b) => (
      tournamentCompetitionPriority(a) - tournamentCompetitionPriority(b)
      || a.name.localeCompare(b.name)
    ))
  return (
    <aside className="trn-leagues" aria-label="Competiciones de la temporada">
      <header><span>Temporada</span><h2>Competiciones</h2></header>
      <nav>
        {sorted.map((competition) => (
          <Link to={`/torneos/${competition.id}?season=${season}`} key={competition.id}>
            <img
              src={tournamentCompetitionLogo(competition)}
              className={usesMonochromeTournamentLogo(competition) ? 'is-monochrome' : undefined}
              alt=""
              loading="lazy"
            />
            <span>{competition.name}</span>
            <small>{competition.country}</small>
          </Link>
        ))}
      </nav>
    </aside>
  )
}

function SeasonTop({ players, season }: { players: RankedPlayer[]; season: string }) {
  return (
    <aside className="trn-season-top" aria-label="Top SFA de la temporada">
      <header><span>Rendimiento actual</span><h2>Top 3 SFA</h2></header>
      {players.length === 0 && <p>El ranking aparecera cuando existan puntos calculados.</p>}
      <ol>
        {players.map((player, index) => (
          <li key={player.id}>
            <Link to={`/player/${player.id}?scope=season-${season}`}>
              <b>{String(index + 1).padStart(2, '0')}</b>
              <span className="trn-season-top__photo">
                {player.photo_url && <img src={player.photo_url} alt="" loading="lazy" />}
              </span>
              <span><strong>{player.name}</strong><small>{player.team}</small></span>
              <em>{Math.round(player.sfa_pts).toLocaleString('es-ES')}</em>
            </Link>
          </li>
        ))}
      </ol>
    </aside>
  )
}

export default function TournamentsPage() {
  const [competitions, setCompetitions] = useState<TournamentCompetition[]>([])
  const [dashboard, setDashboard] = useState<TournamentDashboardResponse | null>(null)
  const [topPlayers, setTopPlayers] = useState<RankedPlayer[]>([])
  const [filter, setFilter] = useState<MatchFilter>('all')
  const [loading, setLoading] = useState(true)
  const [matchesLoading, setMatchesLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([fetchTournaments(), fetchTournamentDashboard()])
      .then(([catalog, result]) => {
        setCompetitions(catalog.competitions)
        setDashboard(result)
        return fetchRanking({ scope: `season-${result.season}`, limit: 3 })
          .then((ranking) => setTopPlayers(ranking.ranking))
          .catch(() => setTopPlayers([]))
      })
      .catch(() => setError('No se pudo cargar el centro de torneos.'))
      .finally(() => setLoading(false))
  }, [])

  const loadDate = (date?: string) => {
    if (!dashboard) return
    setMatchesLoading(true)
    setError(null)
    fetchTournamentDashboard(dashboard.season, date)
      .then(setDashboard)
      .catch(() => setError('No se pudieron cargar los partidos de esta fecha.'))
      .finally(() => setMatchesLoading(false))
  }

  const visibleGroups = useMemo(() => {
    if (!dashboard) return []
    return sortTournamentCompetitions(dashboard.groups)
      .map((group) => ({
        ...group,
        fixtures: group.fixtures.filter((fixture) => filterFixture(fixture, filter)),
      }))
      .filter((group) => group.fixtures.length > 0)
  }, [dashboard, filter])

  if (loading) return <div className="trn-state" role="status">Cargando torneos</div>

  return (
    <main className="trn-page">
      <header className="trn-page__header">
        <div><span>Centro de competiciones</span><h1>Torneos</h1></div>
        {dashboard && <strong>Temporada {tournamentSeasonLabel(dashboard.season)}</strong>}
      </header>
      {error && <div className="trn-alert" role="alert">{error}</div>}

      <div className="trn-dashboard">
        <CompetitionList competitions={competitions} season={dashboard?.season ?? ''} />

        <section className="trn-scoreboard" aria-label="Partidos por fecha">
          <header className="trn-scoreboard__date">
            <button
              type="button"
              onClick={() => dashboard?.previous_date && loadDate(dashboard.previous_date)}
              disabled={!dashboard?.previous_date || matchesLoading}
              aria-label="Fecha anterior con partidos"
            >&#8592;</button>
            <div>
              <span>Fecha seleccionada</span>
              <strong>{dashboard?.selected_date ? tournamentDateLabel(dashboard.selected_date) : 'Sin calendario'}</strong>
            </div>
            <button
              type="button"
              onClick={() => dashboard?.next_date && loadDate(dashboard.next_date)}
              disabled={!dashboard?.next_date || matchesLoading}
              aria-label="Siguiente fecha con partidos"
            >&#8594;</button>
          </header>

          <div className="trn-scoreboard__filters" role="group" aria-label="Filtrar partidos">
            {([['all', 'Todos'], ['live', 'En vivo'], ['upcoming', 'Proximos'], ['results', 'Resultados']] as const)
              .map(([value, label]) => (
                <button type="button" className={filter === value ? 'is-active' : ''} onClick={() => setFilter(value)} key={value}>
                  {label}
                </button>
              ))}
            <button type="button" className="trn-scoreboard__nearest" onClick={() => loadDate()} disabled={matchesLoading}>
              Hoy / proxima
            </button>
          </div>

          <div className={`trn-scoreboard__groups${matchesLoading ? ' is-loading' : ''}`}>
            {visibleGroups.map((group) => (
              <section className="trn-match-group" key={group.competition.id}>
                <Link className="trn-match-group__header" to={`/torneos/${group.competition.id}?season=${dashboard?.season}`}>
                  <img src={tournamentCompetitionLogo(group.competition)} alt="" />
                  <span><strong>{group.competition.name}</strong><small>{group.competition.country}</small></span>
                  <b>Ver torneo &#8594;</b>
                </Link>
                <div>{group.fixtures.map((fixture) => <TournamentFixtureRow fixture={fixture} key={fixture.id} />)}</div>
              </section>
            ))}
            {visibleGroups.length === 0 && (
              <div className="trn-state trn-state--inline">No hay partidos para este filtro y fecha.</div>
            )}
          </div>
        </section>

        <SeasonTop players={topPlayers} season={dashboard?.season ?? ''} />
      </div>
    </main>
  )
}
