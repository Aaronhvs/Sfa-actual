import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchRanking, fetchTournamentDashboard } from '../api/client'
import type { RankedPlayer, SeasonItem, TournamentDashboardResponse, TournamentFixture, TournamentFixtureGroup } from '../types'
import {
  isFeaturedTournamentCompetition,
  tournamentCompetitionPriority,
  tournamentDateKey,
  tournamentDateLabel,
} from '../utils/tournaments'
import { ArrowIcon, isFinal, isLive, ScoreRow } from './tournaments/MatchUI'
import './HomeDiscoverSections.css'

const POSITIONS = [
  { code: 'DEL', label: 'Delantero' }, { code: 'EXT', label: 'Extremo' },
  { code: 'MCO', label: 'Mediapunta' }, { code: 'MC', label: 'Centrocampista' },
  { code: 'LAT', label: 'Lateral' }, { code: 'DC', label: 'Defensa central' },
]

const MAX_FIXTURES = 6

type PositionLeader = typeof POSITIONS[number] & { player: RankedPlayer | null }
type Pick = { fixture: TournamentFixture; competition: TournamentFixtureGroup['competition']; score: number }

async function loadPositionLeader(scope: string, position: string, signal: AbortSignal) {
  // The API applies contextual position overrides after pagination. A one-row
  // request can therefore be empty even though this position has scored players.
  let offset = 0
  const limit = 10
  while (!signal.aborted) {
    const result = await fetchRanking({ scope, position, limit, offset, signal })
    const player = result.ranking.find(item => item.position === position)
    if (player) return player
    offset += limit
    if (offset >= result.total) return null
  }
  return null
}

function normalize(value: string) {
  return value.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim()
}

/** Live first, then teams of the SFA top 3, then the biggest competitions; finished games last. */
function selectFixtures(groups: TournamentFixtureGroup[], players: RankedPlayer[]) {
  const teams = new Set(players.map((player) => normalize(player.team)))
  const picks: Pick[] = []
  for (const { competition, fixtures } of groups) {
    for (const fixture of fixtures) {
      const topTeam = teams.has(normalize(fixture.home_team.name)) || teams.has(normalize(fixture.away_team.name))
      if (!topTeam && !isFeaturedTournamentCompetition(competition)) continue
      const score = (isLive(fixture) ? 1000 : 0)
        + (topTeam ? 500 : 0)
        + (isFinal(fixture) ? 0 : 200)
        - tournamentCompetitionPriority(competition)
      picks.push({ fixture, competition, score })
    }
  }
  return picks
    .sort((a, b) => b.score - a.score || a.fixture.played_at.localeCompare(b.fixture.played_at))
    .slice(0, MAX_FIXTURES)
}

function Photo({ url, name }: { url: string | null; name: string }) {
  const [failed, setFailed] = useState(false)
  return (
    <span className="home-leaders__photo">
      {url && !failed
        ? <img src={url} alt="" loading="lazy" decoding="async" onError={() => setFailed(true)} />
        : <span aria-hidden="true">{name.split(' ').map((part) => part[0]).slice(0, 2).join('')}</span>}
    </span>
  )
}

export default function HomeDiscoverSections({ season, topPlayers }: { season: SeasonItem; topPlayers: RankedPlayer[] }) {
  const [leaders, setLeaders] = useState<PositionLeader[]>([])
  const [positionsLoading, setPositionsLoading] = useState(true)
  const [dashboard, setDashboard] = useState<TournamentDashboardResponse | null>(null)
  const [matchesLoading, setMatchesLoading] = useState(true)
  const [matchesError, setMatchesError] = useState(false)
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setPositionsLoading(true)
    void Promise.allSettled(POSITIONS.map((position) => loadPositionLeader(season.key, position.code, controller.signal)))
      .then((results) => {
        if (controller.signal.aborted) return
        setLeaders(results.map((result, index) => ({
          ...POSITIONS[index],
          player: result.status === 'fulfilled' ? result.value : null,
        })))
        setPositionsLoading(false)
      })
    return () => controller.abort()
  }, [season.key])

  useEffect(() => {
    const controller = new AbortController()
    setMatchesLoading(true)
    setMatchesError(false)
    fetchTournamentDashboard(season.season, undefined, controller.signal)
      .then((result) => { if (!controller.signal.aborted) setDashboard(result) })
      .catch(() => { if (!controller.signal.aborted) setMatchesError(true) })
      .finally(() => { if (!controller.signal.aborted) setMatchesLoading(false) })
    return () => controller.abort()
  }, [season.season, retry])

  const groups = dashboard?.groups ?? []
  const picks = selectFixtures(groups, topPlayers)
  const all = groups.flatMap((group) => group.fixtures)
  const liveCount = all.filter(isLive).length
  const selected = dashboard?.selected_date
  const dayLabel = !selected ? 'Partidos'
    : selected === tournamentDateKey(new Date()) ? 'Hoy en el fútbol'
      : `Próxima fecha: ${tournamentDateLabel(selected, false)}`
  const rankingUrl = `/ranking?${new URLSearchParams({ scope: season.key })}`
  const found = leaders.filter((leader): leader is PositionLeader & { player: RankedPlayer } => leader.player != null)

  return (
    <div className="home-discover">
      <section className="home-today" aria-labelledby="home-today-title" aria-busy={matchesLoading}>
        <header className="home-section-head">
          <div>
            <p className="tp-eyebrow">En juego</p>
            <h2 id="home-today-title">{dayLabel}</h2>
            {!matchesLoading && all.length > 0 && (
              <p className="home-section-head__meta">
                {all.length} partidos{liveCount > 0 && <> · <b>{liveCount} en vivo</b></>}
              </p>
            )}
          </div>
          <Link to="/torneos">Todos los partidos <ArrowIcon /></Link>
        </header>

        {matchesLoading ? (
          <div className="home-skel home-skel--matches" role="status"><span className="sr-only">Cargando partidos</span></div>
        ) : matchesError ? (
          <div className="home-state" role="alert">
            <strong>No pudimos consultar el calendario.</strong>
            <button type="button" onClick={() => setRetry((value) => value + 1)}>Reintentar</button>
          </div>
        ) : picks.length === 0 ? (
          <div className="home-state">
            <strong>No hay partidos de las grandes competiciones en esta fecha.</strong>
            <Link to="/torneos">Ver el calendario completo</Link>
          </div>
        ) : (
          <div className="tp-group home-today__list">
            {picks.map(({ fixture, competition }) => (
              <ScoreRow fixture={fixture} competition={competition} season={dashboard?.season ?? season.season} key={fixture.id} />
            ))}
          </div>
        )}
      </section>

      <aside className="home-leaders" aria-labelledby="home-leaders-title" aria-busy={positionsLoading}>
        <h2 id="home-leaders-title">Líderes por posición</h2>
        <p>El mejor de cada puesto por puntos SFA. Un central no compite contra un delantero.</p>
        {positionsLoading ? (
          <div className="home-skel home-skel--leaders" role="status"><span className="sr-only">Cargando líderes por posición</span></div>
        ) : found.length === 0 ? (
          <p className="home-leaders__empty">Todavía no hay líderes para esta temporada.</p>
        ) : (
          <ol>
            {found.map(({ code, label, player }) => (
              <li key={code}>
                <Link to={`${rankingUrl}&position=${code}`} aria-label={`${label}: ${player.name}, ${Math.round(player.sfa_pts).toLocaleString('es-ES')} puntos SFA. Ver ranking de la posición`}>
                  <Photo url={player.photo_url} name={player.name} />
                  <span className="home-leaders__who">
                    <small>{label}</small>
                    <strong>{player.name}</strong>
                  </span>
                  <em>{Math.round(player.sfa_pts).toLocaleString('es-ES')}</em>
                </Link>
              </li>
            ))}
          </ol>
        )}
        <Link to={rankingUrl} className="home-leaders__cta">Ver todas las posiciones <ArrowIcon /></Link>
      </aside>
    </div>
  )
}
